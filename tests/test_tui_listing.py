"""Exercise directory status rendering and keyboard navigation in Textual."""
import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from textual.widgets import DataTable
from vfs import VirtualFS
from views.ScannerScreen import ScannerScreen

spec = importlib.util.spec_from_file_location('drive_tui_listing', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class ListingTests(unittest.IsolatedAsyncioTestCase):
    async def test_metadata_columns_fit_with_long_names_and_resize(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = ['very-long-filename-' * 10 + str(i) for i in range(40)]
            fs = VirtualFS({'files': {str(root / name): {'hash:1234567'} for name in names}})
            with patch.object(tui, 'VFS', fs), patch(
                    'vfs.filesystem.os.getcwd', return_value=directory):
                app = tui.DemoApp()
                async with app.run_test(size=(80, 24)) as pilot:
                    await pilot.pause()
                    table = app.query_one('#files', DataTable)
                    for size in ((80, 24), (120, 42), (80, 24)):
                        await pilot.resize_terminal(*size)
                        await pilot.pause()
                        columns = table.ordered_columns
                        self.assertEqual([column.label.plain for column in columns],
                                         ['Name', 'Size', 'Dups'])
                        widths = [column.get_render_width(table) for column in columns]
                        self.assertLessEqual(sum(widths), table.scrollable_content_region.width)
                        self.assertEqual(table.max_scroll_x, 0)
                        self.assertTrue(all(column.label.justify == 'left' for column in columns))
                        for name in names:
                            label, file_size, dups = table.get_row(name)
                            self.assertIn(name, label.plain)
                            self.assertEqual(file_size.justify, 'left')
                            self.assertEqual(dups.justify, 'left')
                            self.assertEqual(file_size.plain, file_size.plain.lstrip())
                            self.assertGreaterEqual(columns[1].width, file_size.cell_len)
                            self.assertGreaterEqual(columns[2].width, dups.cell_len)
                    # Switching to a shorter listing refits widths and keeps navigation intact.
                    fs.cwd = fs.db.get_root()
                    app.refresh_list()
                    await pilot.pause()
                    self.assertLessEqual(sum(column.get_render_width(table)
                                             for column in table.ordered_columns),
                                         table.scrollable_content_region.width)

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

    async def test_heavy_scan_tracks_new_file_and_main_circle_turns_green(self):
        for backend in ('memory', 'sqlite'):
            with self.subTest(backend=backend), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / 'disk'
                root.mkdir()
                known, fresh = root / 'known', root / 'new'
                known.write_bytes(b'abc')
                fresh.write_bytes(b'new file')
                known_hash = 'md5:' + hashlib.md5(b'abc').hexdigest()
                fs = VirtualFS({'files': {str(known): {known_hash + ':3'}}},
                               db_type=backend, rebuild_db=True,
                               **({'db_path': str(Path(directory) / 'vfs.db')}
                                  if backend == 'sqlite' else {}))
                if backend == 'sqlite':
                    self.addCleanup(fs.db.conn.close)
                with patch.object(tui, 'VFS', fs), patch(
                        'vfs.filesystem.os.getcwd', return_value=str(root)):
                    app = tui.DemoApp()
                    async with app.run_test(size=(80, 24)) as pilot:
                        await pilot.pause()
                        table = app.query_one('#files', DataTable)
                        self.assertEqual(table.get_row('new')[0].spans[0].style, 'dark_orange')
                        self.assertIsNone(fs.db.get_child(fs.get_cwd(), 'new'))
                        table.move_cursor(row=table.get_row_index('new'))
                        await pilot.press('s')
                        scanner = app.screen
                        self.assertIsInstance(scanner, ScannerScreen)
                        for _ in range(30):
                            await pilot.pause(.1)
                            if scanner.controls.modes == (False, False, False):
                                break
                        self.assertEqual(scanner.model.entries[str(fresh)].state, 'verified')
                        await pilot.press('escape')
                        await pilot.pause()
                        scanner.worker_thread.join(2)
                        label = table.get_row('new')[0]
                        self.assertTrue(label.plain.startswith('●'))
                        self.assertEqual(label.spans[0].style, 'green')
                        self.assertEqual(table.cursor_row, table.get_row_index('new'))
                        stored = fs.db.get_child(fs.get_cwd(), 'new')
                        expected = 'md5:' + hashlib.md5(b'new file').hexdigest()
                        self.assertEqual(stored.info['hash'], expected)
                        self.assertEqual(stored.info['state'], 'verified')
                        self.assertEqual(stored.size, 8)
                        self.assertIn(str(fresh), fs.get_hash_dups(stored.info['hashinfo']))
                        self.assertEqual(fs.db.get_child(fs.get_cwd(), 'known').info['hash'], known_hash)
                        # Repeated completion cannot inflate sizes or duplicate indexes.
                        before = fs.db.get_root().size
                        self.assertFalse(fs.db.add_scanned_file(str(fresh), expected, 8))
                        self.assertEqual(fs.db.get_root().size, before)
                        if backend == 'sqlite':
                            reopened = VirtualFS({}, db_type='sqlite', db_path=str(Path(directory) / 'vfs.db'))
                            self.addCleanup(reopened.db.conn.close)
                            self.assertEqual(reopened.get_from_path(str(fresh)).info['hash'], expected)
