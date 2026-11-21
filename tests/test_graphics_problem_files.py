"""Graphics status foreground and independent missing-file visibility."""
import asyncio
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS

spec = importlib.util.spec_from_file_location('problem_files_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class ProblemFilesTests(unittest.IsolatedAsyncioTestCase):
    async def test_red_in_all_modes_selected_or_not_and_visibility_key(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
            root = Path(directory)
            (root / 'folder').mkdir()
            (root / 'known.txt').write_text('known')
            (root / 'unknown.txt').write_text('new')
            Image.new('RGB', (16, 16), 'blue').save(root / 'unknown.png')
            fs = VirtualFS({'files': {}})
            for filename in ('known.txt', 'missing.png', 'missing.txt'):
                fs.db.add_scanned_file(str(root / filename), 'md5:01234567890123456789012345678901', 5)
            with patch.object(tui, 'HISTORY_PATH', root / 'history.llog'):
                browser = tui.DriveBrowser(fs, path=directory, input=pipe, output=DummyOutput())
            browser.image_previews = False
            browser.graphics_mode = True
            browser.directory_has_media = lambda *args: True
            for mode in (1, 2, 3):
                browser.display_mode = mode
                browser.refresh(update_info=False)
                for filename in ('unknown.txt', 'unknown.png', 'missing.png', 'missing.txt'):
                    index = next(i for i, row in enumerate(browser.rows) if row['name'] == filename)
                    for selected in (index, -1):
                        browser.selected = selected
                        content = browser.control.create_content(100, 30)
                        _, y, _, media = browser.grid_positions[index]
                        fragments = content.get_line(y + browser.icon_lines if media else y)
                        red = any('fg:#ff5555' in style for style, text in fragments if text.strip())
                        self.assertEqual(red, filename.startswith('missing'), filename)
                known = next(row for row in browser.rows if row['name'] == 'known.txt')
                self.assertFalse(known['problem_file'])
            task = asyncio.create_task(browser.app.run_async(set_exception_handler=False))
            try:
                await asyncio.sleep(.05)
                pipe.send_text('\x15')
                await asyncio.sleep(.05)
                self.assertFalse(browser.show_problem_files)
                names = {row['name'] for row in browser.rows}
                self.assertTrue({'known.txt', 'folder', 'unknown.txt', 'unknown.png'} <= names)
                self.assertFalse({'missing.txt', 'missing.png'} & names)
                browser.toggle_graphics()
                self.assertNotIn('missing.txt', {row['name'] for row in browser.rows})
                self.assertIn('unknown.txt', {row['name'] for row in browser.rows})
                pipe.send_text('\x15')
                await asyncio.sleep(.05)
                self.assertTrue({'unknown.txt', 'unknown.png', 'missing.png'} <= {row['name'] for row in browser.rows})
            finally:
                browser.app.exit()
                await task
