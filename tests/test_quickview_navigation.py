"""Quick View keys select duplicate rows without traversing metadata."""
import asyncio
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS

spec = importlib.util.spec_from_file_location('quickview_navigation_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class QuickViewNavigationTests(unittest.IsolatedAsyncioTestCase):
    async def test_arrow_selection_focus_and_duplicate_jump(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
            root = Path(directory)
            for name in ('first.txt', 'second.txt'):
                (root / name).write_text('content')
            with patch.object(tui, 'HISTORY_PATH', root / 'history.llog'):
                browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                           input=pipe, output=DummyOutput())
            browser.image_previews = False
            browser.info.text = 'Metadata\nMore metadata\nfirst\nSpacer\nsecond'
            browser.info_paths = {2: str(root / 'first.txt'), 4: str(root / 'second.txt')}
            browser.app.layout.focus(browser.info)
            task = asyncio.create_task(browser.app.run_async(set_exception_handler=False))
            async def key(value):
                pipe.send_text(value)
                await asyncio.sleep(.04)
            try:
                await asyncio.sleep(.04)
                await key('\x1b[B')
                self.assertEqual(browser.selected_path(), str(root / 'first.txt'))
                await key('\x1b[B')
                self.assertEqual(browser.selected_path(), str(root / 'second.txt'))
                await key('\x1b[B')
                self.assertEqual(browser.info.buffer.document.cursor_position_row, 4)
                await key('\x1b[A')
                self.assertEqual(browser.info.buffer.document.cursor_position_row, 2)
                await key('\x1b[D')
                self.assertTrue(browser.app.layout.has_focus(browser.control))
                browser.app.layout.focus(browser.info)
                browser.move_info_duplicate('last')
                self.assertEqual(browser.info.buffer.document.cursor_position_row, 4)
                browser.move_info_duplicate('first')
                browser.move_info_duplicate(10)
                self.assertEqual(browser.info.buffer.document.cursor_position_row, 4)
                browser.move_info_duplicate(-10)
                self.assertEqual(browser.info.buffer.document.cursor_position_row, 2)
                await key('\x1b[C')
                self.assertEqual(browser.current_name(), 'first.txt')
                browser.info_paths = {}
                browser.info.text = 'one\ntwo\nthree'
                browser.info.buffer.cursor_position = 0
                browser.app.layout.focus(browser.info)
                await key('\x1b[B')
                self.assertEqual(browser.info.buffer.document.cursor_position_row, 1)
            finally:
                browser.app.exit()
                await task
