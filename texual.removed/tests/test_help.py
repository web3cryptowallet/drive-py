"""Help opens in both contexts and closes without triggering parent shortcuts."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rich.text import Text
from textual.app import App
from textual.widgets import DataTable, Static
from vfs import VirtualFS
from views.HelpScreen import HelpScreen
from views.ScannerScreen import ScannerScreen, BucketMap


class HelpTests(unittest.IsolatedAsyncioTestCase):
    async def test_main_help_legend_modes_and_close_restore_navigation(self):
        spec = importlib.util.spec_from_file_location(
            'tui_help', Path(__file__).resolve().parents[1] / 'drive-tui.py')
        tui = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tui)
        with tempfile.TemporaryDirectory() as directory:
            fs = VirtualFS({'files': {str(Path(directory) / 'known'): {'hash:3'}}})
            with patch.object(tui, 'VFS', fs), patch(
                    'vfs.filesystem.os.getcwd', return_value=directory):
                app = tui.DemoApp()
                async with app.run_test(size=(80, 24)) as pilot:
                    table = app.query_one('#files', DataTable)
                    await pilot.pause()
                    selected = table.cursor_row
                    self.assertFalse(app.query('Footer'))
                    for mode, expected in ((1, 'not in database'),
                                           (2, 'Yellow names'), (3, '* New')):
                        app.display_mode = mode
                        await pilot.press('h')
                        self.assertIsInstance(app.screen, HelpScreen)
                        content = app.screen.query_one('#help-content', Static).render().plain
                        self.assertIn('Legend', content)
                        self.assertIn(expected, content)
                        self.assertIn('Ctrl+X', content)
                        self.assertIn('Apply button', content)
                        self.assertGreater(app.screen.query_one('#help-scroll').max_scroll_y, 0)
                        await pilot.press('escape')
                        self.assertNotIsInstance(app.screen, HelpScreen)
                        self.assertEqual(fs.pwd(), directory)
                        self.assertEqual(table.cursor_row, selected)
                    await pilot.press('h', 'h')
                    self.assertNotIsInstance(app.screen, HelpScreen)
                    while fs.pwd() != '/':
                        fs.enter('..')
                    for mode, expected in ((1, 'not in database'),
                                           (2, 'Yellow names'), (3, '* New')):
                        app.display_mode = mode
                        app.refresh_list()
                        await pilot.pause()
                        quick = app.query_one('#quick', DataTable)
                        info = '\n'.join(Text.from_markup(str(quick.get_row_at(i)[0])).plain
                                         for i in range(quick.row_count))
                        self.assertIn(expected, info)
                        self.assertIn('Ctrl+X', info)
                        self.assertIn('Apply button', info)
                        await pilot.press('h')
                        content = app.screen.query_one('#help-content', Static).render().plain
                        self.assertIn(content, info)
                        await pilot.press('escape')
                        self.assertEqual(fs.pwd(), '/')

    async def test_scanner_help_scrolling_and_close_preserve_scanner(self):
        with tempfile.TemporaryDirectory() as directory:
            fs = VirtualFS({'files': {}})
            app = App()
            async with app.run_test(size=(80, 24)) as pilot:
                scanner = ScannerScreen(fs, directory)
                app.push_screen(scanner)
                await pilot.pause(.2)
                selected = scanner.query_one(BucketMap).selected
                self.assertFalse(scanner.query('#scan-help'))
                await pilot.press('h')
                await pilot.pause()  # Let mount focus/layout settle before testing scrolling.
                self.assertIsInstance(app.screen, HelpScreen)
                content = app.screen.query_one('#help-content', Static).render().plain
                for text in ('1 / 2 / 3', 'Shift+1', 'Symbols', 'D Directory',
                             'MB/s–PB/s', 'All', 'horizontal position is preserved'):
                    self.assertIn(text, content)
                scroll = app.screen.query_one('#help-scroll')
                self.assertGreater(scroll.max_scroll_y, 0)
                scroll.scroll_to(y=scroll.max_scroll_y, animate=False)
                await pilot.pause()
                self.assertGreater(scroll.scroll_y, 0)
                self.assertFalse(scanner.stop.is_set())
                await pilot.press('escape')
                self.assertIs(app.screen, scanner)
                self.assertFalse(scanner.stop.is_set())
                self.assertEqual(scanner.query_one(BucketMap).selected, selected)
                scanner.query_one('#scan-limit').focus()
                await pilot.press('h')
                self.assertIsInstance(app.screen, HelpScreen)
                await pilot.click('#help-close')
                self.assertIs(app.screen, scanner)
                await pilot.press('escape')
                await pilot.pause()
                scanner.worker_thread.join(2)
                self.assertTrue(scanner.stop.is_set())
