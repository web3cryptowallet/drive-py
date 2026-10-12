"""Exercise directory status rendering and keyboard navigation in Textual."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from textual.widgets import DataTable
from vfs import VirtualFS

spec = importlib.util.spec_from_file_location('drive_tui_listing', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class ListingTests(unittest.IsolatedAsyncioTestCase):
    async def test_startup_colors_monochrome_and_new_file_info(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'known').write_text('abc')
            (root / 'new[1]').write_text('abc')
            (root / 'new-dir').mkdir()
            fs = VirtualFS({'files': {str(root / 'known'): {'hash:3'},
                                       str(root / 'deleted'): {'old:3'}}})
            with patch.object(tui, 'VFS', fs), patch('vfs.filesystem.os.getcwd', return_value=directory):
                app = tui.DemoApp()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    table = app.query_one('#files', DataTable)
                    self.assertEqual(fs.pwd(), directory)
                    self.assertEqual(app.display_mode, 1)
                    for name, indicator in [('known', 'green'), ('new[1]', 'dark_orange'),
                                            ('new-dir', 'dark_orange'), ('deleted', 'red')]:
                        label = table.get_row(name)[0]
                        self.assertEqual(label.style, '#ffffff')
                        self.assertTrue(label.plain.startswith('●'))
                        self.assertEqual(label.spans[0].style, indicator)
                    table.move_cursor(row=table.get_row_index('new[1]'))
                    await pilot.pause()
                    await pilot.press('n')
                    await pilot.pause()
                    self.assertEqual(app.display_mode, 2)
                    for name, color, indicator in [('known', 'white', 'green'),
                                                  ('new[1]', 'yellow', 'green'),
                                                  ('new-dir', 'yellow', 'green'),
                                                  ('deleted', 'red', 'red')]:
                        label = table.get_row(name)[0]
                        self.assertEqual(label.style, color)
                        self.assertTrue(label.plain.startswith('●'))
                        self.assertEqual(label.spans[0].style, indicator)
                    await pilot.press('n')
                    await pilot.pause()
                    self.assertEqual(app.display_mode, 3)
                    for name in ('known', 'new[1]', 'new-dir', 'deleted'):
                        self.assertEqual(table.get_row(name)[0].style, 'white')
                        self.assertNotIn('●', table.get_row(name)[0].plain)
                        self.assertEqual(table.get_row(name)[0].spans, [])
                    self.assertTrue(table.get_row('new[1]')[0].plain.startswith('*'))
                    self.assertTrue(table.get_row('deleted')[0].plain.startswith('!'))
                    self.assertEqual(table.cursor_row, table.get_row_index('new[1]'))
                    await pilot.press('enter')
                    await pilot.pause()
                    self.assertEqual(app.quickData['name'], 'new[1]')
                    self.assertEqual(app.quickData['info']['dups'], [])
                    await pilot.press('n')
                    self.assertEqual(app.display_mode, 1)
                    self.assertEqual(table.get_row('new[1]')[0].style, '#ffffff')
                    self.assertEqual(table.get_row('new[1]')[0].spans[0].style, 'dark_orange')
                    self.assertTrue(table.get_row('new[1]')[0].plain.startswith('●'))
