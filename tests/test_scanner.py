"""Disk/database union, checksums, persistent IDs and headless popup behavior."""
import hashlib
import importlib.util
from unittest.mock import patch
from pathlib import Path
from queue import Queue
from threading import Event, Thread
import tempfile
import unittest

from textual.app import App
from textual.widgets import Button, DataTable, Input, Static
from vfs import VirtualFS
from vfs.scanner import DriveScanner, FileMap, ScanEntry, Pagination, ScanStats
from views.ScannerScreen import ScannerScreen, BucketMap, PageButtons, PageSlider


def checksum(data):
    return 'MD5:' + hashlib.md5(data).hexdigest() + ':' + str(len(data))


class ScannerTests(unittest.TestCase):
    def test_union_checksums_errors_and_new_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'ok').write_bytes(b'abc')
            (root / 'changed').write_bytes(b'xyz')
            (root / 'new').write_bytes(b'new')
            (root / 'link').symlink_to(root, target_is_directory=True)
            fs = VirtualFS({'files': {str(root / name): {checksum(b'abc')}
                                      for name in ('ok', 'changed', 'gone')}})
            queue = Queue()
            scanner = DriveScanner(fs.db, directory, queue, Event())
            fs.db.scan_paths = {}
            scanner.scan_once(fs.db)
            entries = {}
            stats = []
            while not queue.empty():
                kind, entry = queue.get()
                if kind == 'entry':
                    entries[entry.path] = entry
                elif kind == 'stats':
                    stats.append(entry)
            self.assertEqual(stats[-1].bytes_read, 6)  # only the two hashed files
            self.assertFalse(stats[-1].active)
            self.assertEqual(stats[-1].mb_per_second, 0)
            self.assertTrue(any(event.active and event.mb_per_second > 0 for event in stats))
            self.assertIn(str(root / 'ok'), [event.path for event in stats])
            self.assertEqual(ScanStats('/file', 2_000_000, .5, True).mb_per_second, 4)
            self.assertEqual(ScanStats('/file', 2_000_000, 0, True).mb_per_second, 0)
            self.assertEqual(entries[str(root / 'ok')].state, 'verified')
            self.assertEqual(entries[str(root / 'changed')].state, 'modified')
            self.assertEqual(entries[str(root / 'gone')].state, 'missing')
            self.assertEqual(entries[str(root / 'new')].state, 'new')
            self.assertIn(str(root / 'new'), fs.db.scan_paths)
            self.assertEqual(len(entries), 6)  # root + 5 paths, no symlink recursion
            self.assertIsNone(fs.db.get_child(fs.get_from_path(directory), 'new'))
            (root / 'new').unlink()
            scanner.scan_once(fs.db)
            removed = set()
            while not queue.empty():
                kind, value = queue.get()
                if kind == 'removed':
                    removed.update(value)
            self.assertIn(str(root / 'new'), removed)

    def test_sqlite_worker_persists_without_changing_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'disk'
            root.mkdir()
            (root / 'new').write_bytes(b'hello')
            fs = VirtualFS(None, 'sqlite', db_path=str(Path(directory) / 'index.db'))
            queue, stop = Queue(), Event()
            scanner = DriveScanner(fs.db, str(root), queue, stop)
            worker = Thread(target=scanner.run)
            worker.start()
            try:
                while True:
                    kind, value = queue.get(timeout=5)
                    if kind == 'phase' and value.startswith('Watching'):
                        break
                    self.assertFalse(kind == 'phase' and value.startswith('Scan stopped'), value)
            finally:
                stop.set()
                worker.join(5)
            self.assertFalse(worker.is_alive())
            self.assertEqual(fs.db.conn.execute('SELECT path FROM scan_paths WHERE id = ?',
                                               (str(root / 'new'),)).fetchone()[0], str(root / 'new'))
            self.assertEqual(fs.db.conn.execute('SELECT count(*) FROM nodes').fetchone()[0], 0)
            fs.db.conn.close()

    def test_buckets_and_pagination(self):
        model = FileMap()
        model.cells = 8
        for i in range(1000):
            model.update(ScanEntry(str(i), str(i), False, size=i, state='verified'))
        self.assertLessEqual(len(model.buckets), 8)
        self.assertEqual(sum(b.files for b in model.buckets), 1000)
        model.fixed, model.limit, model.mode, model.byte_limit = False, 7, 'size', 2000
        model.rebuild()
        self.assertTrue(all(len(b.ids) <= 7 for b in model.buckets))
        model.update(ScanEntry('0', '0', False, state='missing'))
        self.assertEqual(sum(b.counts['missing'] for b in model.buckets), 1)
        pager = Pagination()
        for width in (12, 40, 80, 120):
            for page in (1, 50, 101):
                pager.select(page, 101)
                choices = pager.choices(101, width)
                self.assertIn(page, choices)
                self.assertLessEqual(len(choices) * 5, width)
        pager.select(500, 101)
        self.assertEqual(pager.page, 101)
        pager.select(-100, 101)
        self.assertEqual(pager.page, 1)
        self.assertEqual(pager.choices(3, 80), [1, 2, 3])
        self.assertEqual(pager.choices(0, 80), [1])



class PopupTests(unittest.IsolatedAsyncioTestCase):
    async def test_popup_modes_inputs_navigation_and_close(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for i in range(12):
                (root / str(i)).write_text('abc')
            fs = VirtualFS({'files': {str(root / '0'): {checksum(b'abc')}}})
            app = App()
            async with app.run_test(size=(120, 42)) as pilot:
                screen = ScannerScreen(fs, directory)
                app.push_screen(screen)
                await pilot.pause(.5)
                self.assertEqual(len(screen.model.entries), 13)
                await pilot.press('right')
                self.assertEqual(screen.query_one(BucketMap).selected, min(1, len(screen.model.buckets) - 1))
                await pilot.press('m', 'v', 'v')
                self.assertEqual(screen.model.mode, 'size')
                self.assertFalse(screen.model.fixed)
                field = screen.query_one('#scan-limit', Input)
                field.value = '2'
                field.focus()
                await pilot.press('enter')
                self.assertTrue(all(len(b.ids) <= 2 for b in screen.model.buckets))
                # Large bucket pagination updates the actual table and navigation controls.
                screen.stop.set()
                screen.worker_thread.join(1)
                screen.events.put(('stats', ScanStats('/disk/[live]', 2_000_000, .5, True)))
                await pilot.pause(.2)
                stats_view = screen.query_one('#scan-stats', Static)
                self.assertIn('4.00 MB/s', str(stats_view.render()))
                self.assertIn('/disk/[live]', str(stats_view.render()))
                screen.events.put(('stats', ScanStats('/disk/[live]', 2_000_000, .5, False)))
                await pilot.pause(.2)
                self.assertIn('0.00 MB/s', str(stats_view.render()))
                self.assertIn('Last path:', str(stats_view.render()))
                screen.model = FileMap()
                grid = screen.query_one(BucketMap)
                grid.model = screen.model
                screen.model.cells = 1
                for i in range(1200):
                    screen.model.update(ScanEntry(str(i), f'/file[{i}]', False, size=i))
                screen.redraw()
                await pilot.pause()
                total_pages = screen.pages
                table = screen.query_one('#scan-details', DataTable)
                self.assertGreater(total_pages, 12)
                self.assertLessEqual(table.row_count, table.content_size.height - int(table.show_header))
                self.assertEqual(table.max_scroll_y, 0)
                screen.query_one('#scan-next', Button).press()
                await pilot.pause()
                self.assertEqual(screen.pagination.page, 2)
                self.assertEqual(table.get_row_at(0)[0].plain, f'/file[{screen.page_size}]')
                screen.query_one('#scan-last', Button).press()
                await pilot.pause()
                self.assertEqual(screen.pagination.page, total_pages)
                self.assertTrue(screen.query_one('#scan-next', Button).disabled)
                self.assertLessEqual(table.row_count, screen.page_size)
                screen.set_page(1)
                await pilot.pause()
                bar = screen.query_one(PageButtons)
                target = next(start for start, end, page in bar.targets if page == 3)
                await pilot.click('#scan-pages', offset=(target, 0))
                self.assertEqual(screen.pagination.page, 3)
                await pilot.click('#scan-pages', offset=(target, 0))
                self.assertEqual(screen.pagination.page, 3)
                for jump in (10, 100, 1000):
                    screen.set_page(1)
                    screen.query_one(f'#scan-ahead{jump}', Button).press()
                    await pilot.pause()
                    self.assertEqual(screen.pagination.page, min(1 + jump, total_pages))
                    screen.query_one(f'#scan-back{jump}', Button).press()
                    await pilot.pause()
                    self.assertEqual(screen.pagination.page, 1)
                slider = screen.query_one(PageSlider)
                await pilot.click('#scan-slider', offset=(slider.size.width - 1, 0))
                self.assertEqual(screen.pagination.page, total_pages)
                await pilot.press('left')
                self.assertEqual(screen.pagination.page, total_pages - 1)
                await pilot.press('home')
                self.assertEqual(screen.pagination.page, 1)
                await pilot.mouse_down('#scan-slider', offset=(0, 0))
                await pilot.hover('#scan-slider', offset=(slider.size.width - 1, 0))
                await pilot.mouse_up('#scan-slider', offset=(slider.size.width - 1, 0))
                self.assertEqual(screen.pagination.page, total_pages)
                self.assertFalse(slider.dragging)
                await pilot.resize_terminal(80, 24)
                await pilot.pause()
                self.assertEqual(table.max_scroll_y, 0)
                self.assertLessEqual(table.row_count, table.content_size.height - int(table.show_header))
                self.assertLessEqual(screen.pagination.page, screen.pages)
                self.assertLessEqual(bar.render().cell_len, bar.size.width)
                grid.focus()
                await pilot.press('s')
                await pilot.pause()
                self.assertTrue(screen.stop.is_set())
                screen.worker_thread.join(1)
                self.assertFalse(screen.worker_thread.is_alive())

    async def test_main_app_shortcut_at_standard_terminal_size(self):
        spec = importlib.util.spec_from_file_location('drive_tui_scanner', Path(__file__).resolve().parents[1] / 'drive-tui.py')
        tui = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tui)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'known'
            path.write_bytes(b'abc')
            fs = VirtualFS({'files': {str(path): {checksum(b'abc')}}})
            with patch.object(tui, 'VFS', fs), patch('vfs.filesystem.os.getcwd', return_value=directory):
                app = tui.DemoApp()
                async with app.run_test(size=(80, 24)) as pilot:
                    await pilot.press('s')
                    await pilot.pause(.3)
                    self.assertIsInstance(app.screen, ScannerScreen)
                    screen = app.screen
                    self.assertEqual(len(screen.model.entries), 2)
                    self.assertLessEqual(screen.query_one('#scan-nav').region.bottom, 24)
                    await pilot.press('escape')
                    self.assertNotIsInstance(app.screen, ScannerScreen)
                    self.assertEqual(fs.pwd(), directory)

    async def test_dense_map_colors_activity_and_viewport_fit(self):
        from rich.color import Color
        with tempfile.TemporaryDirectory() as directory:
            fs = VirtualFS({'files': {}})
            app = App()
            async with app.run_test(size=(120, 42)) as pilot:
                screen = ScannerScreen(fs, directory)
                app.push_screen(screen)
                await pilot.pause(.3)
                screen.stop.set()
                screen.worker_thread.join(1)
                grid = screen.query_one(BucketMap)
                model = FileMap()
                model.fixed, model.limit = False, 1
                states = ['new', 'missing', 'modified', 'verified', 'unknown']
                model.entries = {str(i): ScanEntry(str(i), str(i), False, state=states[i % 5])
                                 for i in range(2000)}
                model.rebuild()
                screen.model = grid.model = model
                screen.redraw()
                await pilot.pause()
                self.assertEqual(grid.columns, grid.scrollable_content_region.width)
                self.assertGreater(grid.rows, grid.content_size.height)
                self.assertGreater(grid.max_scroll_y, 0)
                self.assertEqual(grid.max_scroll_x, 0)
                details = screen.query_one('#scan-details', DataTable)
                self.assertGreaterEqual(grid.size.height, 2 * details.size.height - 2)
                with patch('views.ScannerScreen.time.monotonic', return_value=10):
                    strip = grid.render_line(0)
                self.assertEqual(strip.cell_length, grid.scrollable_content_region.width)
                self.assertEqual(strip.text[:5], 'UUM●?')
                self.assertNotIn(' ', strip.text)
                for segment, color in zip(strip, ['#ffffff', '#ff0000', '#ff8800', 'green', '#ffffff']):
                    self.assertEqual(segment.style.color, Color.parse(color))
                    self.assertEqual(segment.style.bgcolor, Color.parse('#000000'))
                for selected in (0, 1, 3):
                    grid.selected = selected
                    with patch('views.ScannerScreen.time.monotonic', return_value=10):
                        segment = list(grid.render_line(0))[selected]
                    self.assertEqual(segment.style.bgcolor, Color.parse('#000000'))
                    self.assertTrue(segment.style.underline)
                grid.selected = 0
                # Activity must stay white on red even on the selected cell.
                model.buckets[0].updated = 10
                with patch('views.ScannerScreen.time.monotonic', return_value=10.1):
                    segment = next(iter(grid.render_line(0)))
                self.assertIn(segment.text, ('\\', '|', '/', '-'))
                self.assertEqual(segment.style.color, Color.parse('#ffffff'))
                self.assertEqual(segment.style.bgcolor, Color.parse('#ff0000'))
                # One character is also one mouse hit target.
                await pilot.click('#bucket-map', offset=(1, 0))
                self.assertEqual(grid.selected, 1)
                await pilot.press('pagedown')
                self.assertGreaterEqual(grid.selected, grid.columns * grid.scrollable_content_region.height)
                self.assertGreater(grid.scroll_y, 0)
                self.assertFalse(screen.query('#scan-rows'))
                start = int(grid.scroll_y) * grid.columns
                summary = str(screen.query_one('#map-start', Static).render())
                self.assertIn(f'View start: bucket {start + 1}/', summary)
                selected = grid.selected
                grid.scroll_to(y=0, animate=False)
                await pilot.pause()
                self.assertEqual(grid.selected, selected)
                self.assertIn('View start: bucket 1/', str(screen.query_one('#map-start', Static).render()))
                await pilot.resize_terminal(80, 24)
                await pilot.pause(.3)
                self.assertEqual(grid.columns, grid.scrollable_content_region.width)
                self.assertGreater(grid.rows, grid.content_size.height)
                self.assertGreater(grid.max_scroll_y, 0)
                # Optional fixed packing derives its target from the viewport.
                await pilot.press('v')
                await pilot.pause(.3)
                self.assertTrue(screen.model.fixed)
                self.assertLessEqual(len(screen.model.buckets), grid.cells)
                await pilot.press('escape')
