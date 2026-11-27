"""Real terminal input for Files incremental name search."""
import asyncio
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS

spec = importlib.util.spec_from_file_location('filename_search_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class FilenameSearchTests(unittest.IsolatedAsyncioTestCase):
    async def test_incremental_search_cycles_and_keeps_shortcuts_literal(self):
        with tempfile.TemporaryDirectory() as folder, create_pipe_input() as pipe:
            root = Path(folder)
            for name in ('alpha.txt', 'Alpine.txt', 'bqjx.txt', 'zebra.txt'):
                (root / name).write_text('x')
            (root / 'target-dir').mkdir()
            (root / 'media').mkdir()
            (root / 'mnt').mkdir()
            with patch.object(tui, 'HISTORY_PATH', root / 'history.llog'):
                browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=folder,
                                           input=pipe, output=DummyOutput())
            task = asyncio.create_task(browser.app.run_async(set_exception_handler=False))
            async def send(text):
                pipe.send_text(text)
                await asyncio.sleep(.07)
            try:
                await asyncio.sleep(.04)
                await send('\x13al')
                view = browser.screen_stack[-1][0]
                self.assertIsInstance(view, tui.FilenameSearchView)
                render = view.search.window.render_info
                self.assertEqual(render.window_height, 1)
                self.assertLessEqual(render.window_width, browser.app.output.get_size().columns // 2)
                positions = browser.app.renderer._last_screen.visible_windows_to_write_positions
                position = positions[view.search.window]
                self.assertLessEqual(position.xpos + position.width,
                                     browser.app.output.get_size().columns // 2)
                self.assertIn(browser.info.window, positions)
                files_position = positions[browser.files]
                self.assertEqual(position.ypos, files_position.ypos + files_position.height)
                self.assertNotIn(browser.filename_slider_window, positions)
                first = browser.current_name()
                self.assertIn(first, ('alpha.txt', 'Alpine.txt'))
                await send('\x13')
                self.assertNotEqual(browser.current_name(), first)
                await send('\x1b[A')
                self.assertEqual(browser.current_name(), first)
                await send('\x15m')
                self.assertEqual(browser.current_name(), 'media')
                await send('n')
                self.assertEqual(browser.current_name(), 'mnt')
                await send('\x7f')
                self.assertEqual(browser.current_name(), 'media')
                await send('n\x15')
                self.assertEqual(view.search.text, '')
                self.assertEqual(browser.current_name(), 'mnt')
                await send('m')
                self.assertEqual(browser.current_name(), 'media')
                await send('\x15bqjx')
                self.assertEqual(view.search.text, 'bqjx')
                self.assertEqual(browser.current_name(), 'bqjx.txt')
                self.assertFalse(task.done())
                await send('missing')
                self.assertEqual(view.status, 'No matching name')
                self.assertEqual(browser.current_name(), 'bqjx.txt')
                with patch.object(browser, 'open', side_effect=AssertionError('search must not open')):
                    await send('\r')
                self.assertTrue(browser.screen_stack)
                self.assertEqual(browser.current_name(), 'bqjx.txt')
                # Newly created exact match wins over existing prefix matches.
                (root / 'al').write_text('new')
                with patch.object(browser, 'open', wraps=browser.open) as opened:
                    await send('\x15al\r')
                    opened.assert_called_once_with()
                self.assertFalse(browser.screen_stack)
                self.assertEqual(browser.current_name(), 'al')
                self.assertTrue(any(row['name'] == 'al' for row in browser.rows))
                await send('\x13ebra\r')
                self.assertEqual(browser.current_name(), 'zebra.txt')
                await send('\x13target\r')
                self.assertEqual(browser.vfs.pwd(), str(root / 'target-dir'))
                self.assertFalse(browser.screen_stack)
                self.assertIsNone(browser.filename_search)
                self.assertIn(browser.filename_slider_window,
                              browser.app.renderer._last_screen.visible_windows_to_write_positions)
                self.assertTrue(browser.app.layout.has_focus(browser.control))
            finally:
                browser.app.exit()
                await task
