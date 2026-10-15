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
from vfs.scanner import DriveScanner, FileMap, ScanEntry, Pagination, ScanStats, ScanControls, ScanStore
from views.ScannerScreen import ScannerScreen, BucketMap, PageButtons, PageSlider


def checksum(data):
    return 'MD5:' + hashlib.md5(data).hexdigest() + ':' + str(len(data))


class ScannerTests(unittest.TestCase):
    def test_lite_root_includes_disk_only_roots_and_all_nested_folders(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / 'local' / 'new' / 'deep'
            nested.mkdir(parents=True)
            (nested / 'file').write_bytes(b'abc')
            fs = VirtualFS({'files': {'/archived/old/file': {checksum(b'abc')}}})
            resolve = lambda path: str(root / path.lstrip('/'))
            with patch('vfs.filesystem.get_real_path', side_effect=resolve), patch(
                    'vfs.scanner.get_real_path', side_effect=resolve):
                self.assertIsNotNone(fs.get_from_path('/local'))
                roots = tuple(node.name for node in fs.list_nodes(fs.db.get_root()))
                self.assertIn('local', roots)
                for read_known in (False, True):
                    with self.subTest(read_known=read_known):
                        scanner = DriveScanner(fs.db, '/', Queue(), Event(),
                                               controls=ScanControls(read_known=read_known),
                                               root_names=roots)
                        scanner.scan_once(fs.db)
                        self.assertEqual(set(scanner.entries), {
                            '/archived', '/archived/old', '/archived/old/file',
                            '/local', '/local/new', '/local/new/deep', '/local/new/deep/file'})
                        self.assertEqual(scanner.entries['/local/new/deep/file'].state, 'unknown')
                        self.assertEqual(scanner.bytes_read, 0)
                        self.assertTrue(scanner.entries['/local/new/deep'].is_dir)

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
            scanner = DriveScanner(fs.db, directory, queue, Event(),
                                   controls=ScanControls((True, False, True)))
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
            self.assertEqual(stats[-1].bytes_read, 9)  # two baseline files plus the new file
            self.assertFalse(stats[-1].active)
            self.assertGreater(stats[-1].mb_per_second, 0)  # Recent work survives cycle-end idle.
            with patch('vfs.scanner.time.monotonic',
                       return_value=stats[-1].rate_samples[-1][0] + 5):
                self.assertEqual(stats[-1].mb_per_second, 0)
                self.assertEqual(stats[-1].paths_per_second, 0)
            self.assertTrue(any(event.active and event.mb_per_second > 0 for event in stats))
            self.assertIn(str(root / 'ok'), [event.path for event in stats])
            self.assertEqual(ScanStats('/file', 2_000_000, .5, True).mb_per_second, 4)
            self.assertEqual(ScanStats('/file', 2_000_000, 0, True).mb_per_second, 0)
            self.assertEqual(entries[str(root / 'ok')].state, 'verified')
            self.assertEqual(entries[str(root / 'changed')].state, 'modified')
            self.assertEqual(entries[str(root / 'gone')].state, 'missing')
            self.assertEqual(entries[str(root / 'new')].state, 'verified')
            self.assertIsNotNone(ScanStore(fs.db).get('checksum', str(root / 'new')))
            self.assertIn(str(root / 'new'), fs.db.scan_paths)
            self.assertEqual(len(entries), 6)  # root + 5 paths, no symlink recursion
            self.assertEqual(fs.db.get_child(fs.get_from_path(directory), 'new').info['hash'],
                             'md5:' + hashlib.md5(b'new').hexdigest())
            (root / 'new').unlink()
            scanner.scan_once(fs.db)
            removed = set()
            final = {}
            while not queue.empty():
                kind, value = queue.get()
                if kind == 'removed':
                    removed.update(value)
                elif kind == 'entry':
                    final[value.path] = value
            self.assertNotIn(str(root / 'new'), removed)
            self.assertEqual(final[str(root / 'new')].state, 'missing')

    def test_sqlite_worker_promotes_new_file_and_preserves_its_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'disk'
            root.mkdir()
            (root / 'new').write_bytes(b'hello')
            fs = VirtualFS(None, 'sqlite', db_path=str(Path(directory) / 'index.db'))
            queue, stop = Queue(), Event()
            scanner = DriveScanner(fs.db, str(root), queue, stop,
                                   controls=ScanControls((True, False, True)))
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
            self.assertGreater(fs.db.conn.execute('SELECT count(*) FROM nodes').fetchone()[0], 0)
            node = fs.get_from_path(str(root / 'new'))
            self.assertEqual(node.info['hash'], 'md5:' + hashlib.md5(b'hello').hexdigest())
            saved = ScanStore(fs.db).get('checksum', str(root / 'new'))
            self.assertEqual(saved, {'size': 5, 'hash': 'md5:' + hashlib.md5(b'hello').hexdigest()})
            (root / 'new').write_bytes(b'world')
            # A second scanner compares the persisted hash rather than replacing it.
            resumed = DriveScanner(fs.db, str(root), Queue(), Event(),
                                   controls=ScanControls((False, False, True)),
                                   entries=scanner.entries.values())
            resumed.scan_once(fs.db)
            self.assertEqual(resumed.entries[str(root / 'new')].state, 'modified')
            self.assertEqual(fs.get_from_path(str(root / 'new')).info['hash'], node.info['hash'])
            fs.db.conn.close()

    def test_lite_medium_and_combined_totals(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            known, fresh, gone = (str(root / name) for name in ('known', 'fresh', 'gone'))
            Path(known).write_bytes(b'abc')
            Path(fresh).write_bytes(b'12345')
            fs = VirtualFS({'files': {known: {checksum(b'abc')}, gone: {checksum(b'abc')}}})
            fs.db.get_child(fs.get_from_path(directory), 'known').info['state'] = 'modified'
            controls = ScanControls()
            scanner = DriveScanner(fs.db, directory, Queue(), Event(), controls=controls)
            original = scanner.disk_info
            with patch.object(scanner, 'disk_info', wraps=original) as disk, patch('vfs.scanner.os.open', side_effect=AssertionError('lite must not hash')):
                scanner.scan_once(fs.db)
                touched = [call.args[0] for call in disk.call_args_list]
                self.assertNotIn(known, touched)
                self.assertNotIn(gone, touched)
            self.assertEqual(scanner.entries[known].state, 'modified')
            self.assertEqual(scanner.entries[fresh].state, 'unknown')
            self.assertEqual(scanner.entries[fresh].size, 5)
            self.assertEqual((scanner.paths, scanner.size_scanned), (4, 11))
            controls.read_known = True
            scanner.scan_once(fs.db)
            self.assertEqual(scanner.entries[known].state, 'verified')
            self.assertEqual(scanner.entries[gone].state, 'missing')
            controls.modes = (False, True, False)
            Path(known).write_bytes(b'different')
            with patch('vfs.scanner.os.open', side_effect=AssertionError('medium must not hash')):
                scanner.scan_once(fs.db)
            self.assertEqual(scanner.entries[known].state, 'modified')
            self.assertEqual(scanner.entries[fresh].state, 'unknown')
            before_paths, before_size = scanner.paths, scanner.size_scanned
            controls.modes = (False, False, False)
            scanner.scan_once(fs.db)
            self.assertEqual((scanner.paths, scanner.size_scanned), (before_paths, before_size))
            controls.modes = (True, True, True)
            scanner.scan_once(fs.db)
            self.assertEqual(scanner.paths - before_paths, 10)  # lite includes root; verification skips it
            self.assertEqual(scanner.size_scanned - before_size, 3 * (9 + 5 + 3))
            self.assertEqual(scanner.entries[fresh].state, 'verified')
            self.assertEqual(scanner.entries[known].state, 'modified')
            events = list(scanner.events.queue)
            last_stats = [payload for kind, payload in events if kind == 'stats'][-1]
            self.assertEqual(last_stats.paths, scanner.paths)
            self.assertEqual(last_stats.size_scanned, scanner.size_scanned)
            self.assertEqual(ScanStats(elapsed=2, active=True, paths=10, size_scanned=4_000_000).paths_per_second, 5)
            self.assertEqual(ScanStats(elapsed=2, active=True, size_scanned=4_000_000).mb_per_second, 2)

    def test_heavy_priority_checksum_persistence_and_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            known, fresh = str(root / 'a-known'), str(root / 'z-new')
            Path(known).write_bytes(b'abc')
            Path(fresh).write_bytes(b'123')
            fs = VirtualFS({'files': {known: {checksum(b'abc')}}})
            entries = [ScanEntry(known, known, False, 3), ScanEntry(fresh, fresh, False, 3)]
            for new_first in (False, True):
                fs = VirtualFS({'files': {known: {checksum(b'abc')}}})
                controls = ScanControls((False, False, True), new_first=new_first)
                scanner = DriveScanner(fs.db, directory, Queue(), Event(), controls=controls, entries=entries)
                order = []
                original = scanner.verify
                def verify(entry, *args):
                    order.append(entry.path)
                    return original(entry, *args)
                with patch.object(scanner, 'verify', side_effect=verify):
                    scanner.scan_once(fs.db)
                self.assertEqual(order, [fresh, known] if new_first else [known, fresh])
                self.assertEqual(scanner.entries[fresh].state, 'verified')
            scanner.scan_once(fs.db)
            Path(fresh).write_bytes(b'456')
            resumed = DriveScanner(fs.db, directory, Queue(), Event(),
                                   controls=ScanControls((False, False, True)), entries=entries)
            resumed.scan_once(fs.db)
            self.assertEqual(resumed.entries[fresh].state, 'modified')
            controls = ScanControls((False, False, True))
            stopped = DriveScanner(fs.db, directory, Queue(), Event(), controls=controls, entries=entries)
            def stop_hash(**kwargs):
                if kwargs.get('read'):
                    controls.toggle(3)
            with patch.object(stopped, 'report_stats', side_effect=stop_hash):
                stopped.scan_once(fs.db)
            self.assertEqual(stopped.paths, 0)
            self.assertTrue(all(entry.progress is None for entry in stopped.entries.values()))

    def test_modes_resume_saved_position_after_stop_and_sqlite_reopen(self):
        for mode in (1, 2, 3):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / 'disk'
                root.mkdir()
                paths = [str(root / name) for name in ('a', 'b', 'c')]
                for path in paths:
                    Path(path).write_bytes(b'abc')
                database = str(Path(directory) / 'index.db')
                fs = VirtualFS({'files': {path: {checksum(b'abc')} for path in paths}},
                               'sqlite', db_path=database)
                modes = tuple(index == mode - 1 for index in range(3))
                controls = ScanControls(modes)
                entries = [ScanEntry(path, path, False, 3) for path in paths]
                scanner = DriveScanner(fs.db, str(root), Queue(), Event(),
                                       controls=controls, entries=entries)
                original = scanner.publish
                def publish(db, entry):
                    original(db, entry)
                    if entry.path == paths[0]:
                        controls.toggle(mode)
                with patch.object(scanner, 'publish', side_effect=publish):
                    scanner.scan_once(fs.db)
                saved = ScanStore(fs.db).get('position', str(root))
                pending = saved[str(mode)]['stack' if mode == 1 else 'remaining']
                self.assertIn(paths[1], pending)
                self.assertNotIn(paths[0], pending)
                entries = list(scanner.entries.values())
                fs.db.conn.close()
                fs = VirtualFS(None, 'sqlite', db_path=database)
                resumed = DriveScanner(fs.db, str(root), Queue(), Event(),
                                       controls=ScanControls(modes), entries=entries)
                with patch.object(resumed, 'publish', wraps=resumed.publish) as completed:
                    resumed.scan_once(fs.db)
                visited = [call.args[1].path for call in completed.call_args_list]
                self.assertEqual(visited, paths[1:])
                self.assertIsNone(ScanStore(fs.db).get('position', str(root))[str(mode)])
                fs.db.conn.close()

    def test_cursor_restart_modes_and_heavy_interrupt(self):
        for mode in (1, 2, 3):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                paths = [str(root / name) for name in ('a', 'b', 'c')]
                for path in paths:
                    Path(path).write_bytes(b'abc')
                fs = VirtualFS({'files': {path: {checksum(b'abc')} for path in paths[:2]}})
                controls = ScanControls((False, False, False))
                controls.start_from(mode, paths[1])
                entries = [ScanEntry(path, path, False, 3) for path in paths]
                scanner = DriveScanner(fs.db, directory, Queue(), Event(),
                                       controls=controls, entries=entries)
                with patch.object(scanner, 'publish', wraps=scanner.publish) as completed:
                    scanner.scan_once(fs.db)
                self.assertEqual([call.args[1].path for call in completed.call_args_list], paths[1:])
                self.assertEqual(controls.modes, tuple(index == mode - 1 for index in range(3)))
                self.assertIn(paths[0], scanner.entries)  # partial lite does not delete earlier buckets
                if mode == 3:
                    controls.start_from(3, paths[0])
                    interrupted = False
                    def seek_during_hash(**kwargs):
                        nonlocal interrupted
                        if kwargs.get('read') and not interrupted:
                            interrupted = True
                            controls.start_from(3, paths[1])
                    with patch.object(scanner, 'report_stats', side_effect=seek_during_hash):
                        before = scanner.paths
                        scanner.scan_once(fs.db)
                    self.assertEqual(scanner.paths, before)
                    with patch.object(scanner, 'publish', wraps=scanner.publish) as completed:
                        scanner.scan_once(fs.db)
                    self.assertEqual([call.args[1].path for call in completed.call_args_list], paths[1:])

    def test_lite_cursor_directory_discovers_children_and_keeps_prior_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / 'b-dir'
            folder.mkdir()
            (folder / 'new-child').write_bytes(b'abc')
            before, after = str(root / 'a'), str(root / 'c')
            Path(before).write_bytes(b'a')
            Path(after).write_bytes(b'c')
            fs = VirtualFS({'files': {}})
            entries = [ScanEntry(before, before, False, 1),
                       ScanEntry(str(folder), str(folder), True),
                       ScanEntry(after, after, False, 1)]
            controls = ScanControls((False, False, False))
            controls.start_from(1, str(folder))
            scanner = DriveScanner(fs.db, directory, Queue(), Event(),
                                   controls=controls, entries=entries)
            with patch.object(scanner, 'publish', wraps=scanner.publish) as completed:
                scanner.scan_once(fs.db)
            self.assertEqual([call.args[1].path for call in completed.call_args_list],
                             [str(folder), str(folder / 'new-child'), after])
            self.assertIn(before, scanner.entries)

    def test_directory_state_migration_and_verification_skips_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / 'folder'
            folder.mkdir()
            file = folder / 'file'
            file.write_bytes(b'abc')
            fs = VirtualFS({'files': {str(file): {checksum(b'abc')}}})
            for old_state in ('unknown', 'verified', 'missing', 'modified'):
                migrated = ScanEntry(str(root), str(root), True, 123, old_state, progress=50)
                self.assertEqual((migrated.state, migrated.size, migrated.progress),
                                 ('directory', 0, None))
            entries = [ScanEntry(str(root), str(root), True),
                       ScanEntry(str(folder), str(folder), True),
                       ScanEntry(str(file), str(file), False, 3)]
            scanner = DriveScanner(fs.db, directory, Queue(), Event(),
                                   controls=ScanControls((False, True, True)), entries=entries)
            with patch.object(scanner, 'verify', wraps=scanner.verify) as verify:
                scanner.scan_once(fs.db)
            self.assertEqual([call.args[0].path for call in verify.call_args_list],
                             [str(file), str(file)])
            self.assertEqual(scanner.paths, 2)
            self.assertEqual(scanner.entries[str(root)].state, 'directory')
            self.assertEqual(scanner.entries[str(folder)].state, 'directory')
            self.assertEqual(scanner.entries[str(file)].state, 'verified')
            model = FileMap()
            model.entries = scanner.entries
            model.rebuild()
            self.assertEqual(sum(bucket.counts['directory'] for bucket in model.buckets), 2)
            self.assertEqual(sum(bucket.counts['unknown'] for bucket in model.buckets), 0)

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
                grid = screen.query_one(BucketMap)
                self.assertEqual(grid.selected, 1)
                if grid.follow_end:
                    await pilot.press('left')
                    self.assertFalse(grid.follow_end)
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
                self.assertEqual(table.get_row_at(0)[0].plain, f'? /file[{screen.page_size}]')
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

    async def test_independent_controls_and_saved_maps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'disk'
            root.mkdir()
            (root / 'new').write_bytes(b'hello')
            database = str(Path(directory) / 'index.db')
            fs = VirtualFS(None, 'sqlite', db_path=database)
            app = App()
            async with app.run_test(size=(80, 24)) as pilot:
                screen = ScannerScreen(fs, str(root), startup=False)
                app.push_screen(screen)
                await pilot.pause(.4)
                await pilot.press('1', '2', '3', 'r', 't')
                self.assertEqual(screen.controls.modes, (False, True, True))
                self.assertTrue(screen.controls.read_known)
                self.assertFalse(screen.controls.new_first)
                await pilot.press('2', '3')
                self.assertEqual(screen.controls.modes, (False, False, False))
                screen.model.limit = 1
                screen.model.rebuild()
                screen.redraw()
                screen.query_one(BucketMap).selected = 1
                self.assertLessEqual(screen.query_one('#scan-nav').region.bottom, 24)
                await pilot.press('escape')
                await pilot.pause()
                screen.worker_thread.join(2)
                # Reopen the actual SQLite connection to prove persistence.
                fs.db.conn.close()
                fs = VirtualFS(None, 'sqlite', db_path=database)
                restored = ScannerScreen(fs, str(root) + '/', startup=False)
                app.push_screen(restored)
                await pilot.pause(.2)
                self.assertEqual(restored.controls.modes, (False, False, False))
                self.assertTrue(restored.controls.read_known)
                self.assertFalse(restored.controls.new_first)
                self.assertEqual(restored.model.limit, 1)
                self.assertEqual(len(restored.model.entries), 2)
                self.assertEqual(restored.query_one(BucketMap).selected, 1)
                self.assertTrue(all(entry.progress is None for entry in restored.model.entries.values()))
                other = ScannerScreen(fs, str(root / 'other'), startup=False)
                self.assertEqual(other.model.entries, {})
                self.assertEqual(other.controls.modes, (True, False, False))
                await pilot.press('escape')
                await pilot.pause()
                restored.worker_thread.join(2)
            fs.db.conn.close()

    async def test_shift_mode_bindings_use_selected_bucket_first_file(self):
        with tempfile.TemporaryDirectory() as directory:
            fs = VirtualFS({'files': {}})
            app = App()
            async with app.run_test(size=(80, 24)) as pilot:
                screen = ScannerScreen(fs, directory)
                app.push_screen(screen)
                await pilot.pause(.2)
                screen.stop.set()
                screen.worker_thread.join(2)
                screen.model.entries = {str(i): ScanEntry(str(i), f'/file-{i}', False)
                                        for i in range(6)}
                screen.model.limit = 2
                screen.model.rebuild()
                screen.redraw()
                grid = screen.query_one(BucketMap)
                grid.selected = 1
                grid.focus()
                for mode, alias in ((1, 'exclamation_mark'), (2, 'at'), (3, 'number_sign')):
                    with patch.object(screen.controls, 'start_from',
                                      wraps=screen.controls.start_from) as start:
                        await pilot.press(f'shift+{mode}', alias)
                    self.assertEqual(start.call_count, 2)
                    start.assert_called_with(mode, '2')
                    self.assertTrue(screen.controls.modes[mode - 1])
                    self.assertEqual(grid.selected, 1)
                saved = ScanStore(fs.db).get('map', directory)
                self.assertEqual(saved['selected'], 1)
                screen.model.entries.clear()
                screen.model.rebuild()
                screen.redraw()
                with patch.object(screen.controls, 'start_from') as start:
                    await pilot.press('shift+1')
                start.assert_not_called()
                await pilot.press('escape')
                await pilot.pause()

    async def test_end_cursor_follows_growth_wraps_and_exits_on_navigation(self):
        with tempfile.TemporaryDirectory() as directory:
            fs = VirtualFS({'files': {}})
            app = App()
            async with app.run_test(size=(80, 24)) as pilot:
                screen = ScannerScreen(fs, directory)
                app.push_screen(screen)
                await pilot.pause(.2)
                screen.stop.set()
                screen.worker_thread.join(2)
                while not screen.events.empty():
                    screen.events.get_nowait()
                screen.controls.modes = (False, False, False)
                grid = screen.query_one(BucketMap)
                count = grid.columns * (grid.scrollable_content_region.height + 1)
                screen.model.limit = 1
                screen.model.entries = {
                    str(i): ScanEntry(str(i), f'/file-{i}', False) for i in range(count)}
                screen.model.rebuild()
                screen.redraw()
                grid.selected = count - 1
                grid.reveal_selection()
                grid.focus()
                await pilot.press('right')
                self.assertTrue(grid.follow_end)
                self.assertEqual(grid.selected, count)
                self.assertEqual(grid.rows, count // grid.columns + 1)
                self.assertGreater(grid.scroll_y, 0)
                def assert_marker():
                    row = grid.selected // grid.columns - int(grid.scroll_y)
                    self.assertGreaterEqual(row, 0)
                    self.assertLess(row, grid.scrollable_content_region.height)
                    segment = list(grid.render_line(row))[grid.selected % grid.columns]
                    self.assertEqual(segment.text, '>')
                    self.assertTrue(segment.style.underline)
                assert_marker()
                await pilot.press('right', 'right')
                self.assertTrue(grid.follow_end)
                self.assertEqual(grid.selected, count)
                assert_marker()
                self.assertEqual(screen.query_one('#scan-details', DataTable).row_count, 0)
                self.assertIn('following', str(screen.query_one('#bucket-summary', Static).render()))
                with patch.object(screen.controls, 'start_from') as start:
                    await pilot.press('shift+3')
                start.assert_not_called()
                screen.events.put(('entry', ScanEntry(str(count), '/new', False)))
                await pilot.pause(.2)
                self.assertEqual(grid.selected, count + 1)
                assert_marker()
                # Updating an existing bucket does not advance the empty-cell cursor.
                screen.events.put(('entry', ScanEntry(str(count), '/new', False, state='verified')))
                await pilot.pause(.2)
                self.assertEqual(grid.selected, count + 1)
                # Removal/regrouping keeps the marker at the new end.
                screen.events.put(('removed', {str(count)}))
                await pilot.pause(.3)
                self.assertEqual(grid.selected, count)
                assert_marker()
                await pilot.resize_terminal(100, 32)
                await pilot.pause(.3)
                self.assertEqual(grid.selected, count)
                assert_marker()
                for key in ('left', 'up', 'down', 'pageup', 'pagedown'):
                    if not grid.follow_end:
                        grid.selected = len(screen.model.buckets) - 1
                        await pilot.press('right')
                    await pilot.press(key)
                    self.assertFalse(grid.follow_end, key)
                    self.assertLess(grid.selected, len(screen.model.buckets))
                grid.selected = len(screen.model.buckets) - 1
                await pilot.press('right')
                await pilot.press('escape')
                await pilot.pause()
                saved = ScanStore(fs.db).get('map', directory)
                self.assertTrue(saved['follow_end'])
                restored = ScannerScreen(fs, directory, startup=False)
                app.push_screen(restored)
                await pilot.pause(.2)
                grid = restored.query_one(BucketMap)
                self.assertTrue(grid.follow_end)
                self.assertEqual(grid.selected, len(restored.model.buckets))
                last = len(restored.model.buckets) - 1
                await pilot.click('#bucket-map', offset=(
                    last % grid.columns, last // grid.columns - int(grid.scroll_y)))
                self.assertFalse(grid.follow_end)
                self.assertEqual(grid.selected, last)
                # An empty map can wait at > and follow its first bucket.
                restored.model.entries.clear()
                restored.model.rebuild()
                restored.redraw()
                grid.focus()
                await pilot.press('right')
                self.assertTrue(grid.follow_end)
                self.assertEqual(grid.selected, 0)
                await pilot.press('right')
                self.assertTrue(grid.follow_end)
                self.assertEqual(grid.selected, 0)
                restored.events.put(('entry', ScanEntry('/first', '/first', False)))
                await pilot.pause(.2)
                self.assertEqual(grid.selected, 1)
                await pilot.press('left')
                self.assertFalse(grid.follow_end)
                self.assertEqual(grid.selected, 0)
                await pilot.press('escape')
                await pilot.pause()
                restored.worker_thread.join(2)

    async def test_bucket_status_filters_pagination_updates_and_all(self):
        with tempfile.TemporaryDirectory() as directory:
            fs = VirtualFS({'files': {}})
            app = App()
            async with app.run_test(size=(120, 42)) as pilot:
                screen = ScannerScreen(fs, directory)
                app.push_screen(screen)
                await pilot.pause(.2)
                screen.stop.set()
                screen.worker_thread.join(2)
                while not screen.events.empty():
                    screen.events.get_nowait()
                screen.controls.modes = (False, False, False)
                screen.model.limit = 1000
                screen.model.entries = {
                    str(i): ScanEntry(str(i), f'/file-{i}', False,
                                      state='unknown' if i < 80 else 'verified')
                    for i in range(160)}
                screen.model.entries['error'] = ScanEntry(
                    'error', '/bad', False, state='modified', error='Only modified error')
                screen.model.rebuild()
                screen.redraw()
                await pilot.pause()
                table = screen.query_one('#scan-details', DataTable)
                unknown = screen.query_one('#scan-filter-unknown', Button)
                verified = screen.query_one('#scan-filter-verified', Button)
                all_button = screen.query_one('#scan-filter-all', Button)
                self.assertIn('unverified: 80', str(unknown.label))
                self.assertTrue(all_button.has_class('filter-selected'))
                await pilot.click('#scan-filter-unknown')
                self.assertEqual(screen.file_filter, 'unknown')
                self.assertEqual(screen.pagination.page, 1)
                self.assertTrue(unknown.has_class('filter-selected'))
                self.assertFalse(all_button.has_class('filter-selected'))
                self.assertTrue(all(row[0].plain.startswith('? ') for row in
                                    (table.get_row_at(i) for i in range(table.row_count))))
                expected_pages = max(1, (80 + screen.page_size - 1) // screen.page_size)
                self.assertEqual(screen.pages, expected_pages)
                self.assertNotIn('Only modified error', str(screen.query_one('#bucket-summary', Static).render()))
                screen.set_page(screen.pages)
                self.assertIn('/file-', table.get_row_at(0)[0].plain)
                await pilot.click('#scan-filter-verified')
                self.assertEqual(screen.file_filter, 'verified')
                self.assertEqual(screen.pagination.page, 1)
                self.assertTrue(table.get_row_at(0)[0].plain.startswith('● /file-80'))
                # Clicking an active state filter toggles it off.
                await pilot.click('#scan-filter-verified')
                self.assertIsNone(screen.file_filter)
                self.assertTrue(all_button.has_class('filter-selected'))
                await pilot.click('#scan-filter-unknown')
                screen.set_page(screen.pages)
                for i in range(80):
                    screen.model.update(ScanEntry(str(i), f'/file-{i}', False, state='verified'))
                screen.redraw()
                await pilot.pause()
                self.assertEqual(table.row_count, 0)
                self.assertEqual((screen.pagination.page, screen.pages), (1, 1))
                self.assertTrue(unknown.display)
                self.assertIn('unverified: 0', str(unknown.label))
                self.assertIn('verified: 160', str(verified.label))
                self.assertTrue(screen.query_one('#scan-next', Button).disabled)
                await pilot.click('#scan-filter-all')
                self.assertIsNone(screen.file_filter)
                self.assertGreater(table.row_count, 0)
                self.assertFalse(unknown.display)
                await pilot.resize_terminal(80, 24)
                await pilot.pause()
                self.assertLessEqual(screen.query_one('#scan-nav').region.bottom, 24)
                self.assertEqual(table.max_scroll_y, 0)
                await pilot.click('#scan-filter-modified')
                self.assertEqual(table.row_count, 1)
                self.assertEqual(table.get_row_at(0)[0].plain, 'M /bad')
                self.assertIn('Only modified error', str(screen.query_one('#bucket-summary', Static).render()))
                await pilot.press('escape')
                await pilot.pause()
                self.assertEqual(ScanStore(fs.db).get('map', directory)['file_filter'], 'modified')
                restored = ScannerScreen(fs, directory, startup=False)
                app.push_screen(restored)
                await pilot.pause(.2)
                self.assertEqual(restored.file_filter, 'modified')
                self.assertEqual(restored.query_one('#scan-details', DataTable).row_count, 1)
                await pilot.press('escape')
                await pilot.pause()
                restored.worker_thread.join(2)

    async def test_file_details_horizontal_scroll_preserved_during_updates(self):
        with tempfile.TemporaryDirectory() as directory:
            fs = VirtualFS({'files': {}})
            app = App()
            async with app.run_test(size=(80, 24)) as pilot:
                screen = ScannerScreen(fs, directory)
                app.push_screen(screen)
                await pilot.pause(.2)
                screen.stop.set()
                screen.worker_thread.join(2)
                while not screen.events.empty():
                    screen.events.get_nowait()
                screen.model.limit = 1000
                screen.model.entries = {
                    str(i): ScanEntry(str(i), '/' + 'long-name-' * 30 + str(i), False)
                    for i in range(30)}
                screen.model.rebuild()
                screen.redraw()
                await pilot.pause(.3)
                table = screen.query_one('#scan-details', DataTable)
                self.assertTrue(table.show_horizontal_scrollbar)
                self.assertGreater(table.max_scroll_x, 0)
                self.assertEqual(table.max_scroll_y, 0)
                self.assertLessEqual(table.row_count,
                                     table.scrollable_content_region.height - int(table.show_header))
                self.assertLessEqual(screen.query_one('#scan-nav').region.bottom, 24)
                table.focus()
                await pilot.press('right')
                await pilot.pause(.3)
                self.assertGreater(table.scroll_x, 0)
                table.scroll_to(x=100, animate=False)
                await pilot.pause()
                # No transient reset or stale after-refresh restoration during live updates.
                with patch.object(table, 'clear', wraps=table.clear) as clear:
                    screen.events.put(('stats', ScanStats('/live', active=True)))
                    await pilot.pause(.3)
                    self.assertEqual(table.scroll_x, 100)
                    clear.assert_not_called()
                    entry = screen.model.entries['0']
                    screen.events.put(('entry', ScanEntry(
                        entry.id, entry.path, False, state='verified', progress=25)))
                    await pilot.pause(.3)
                    self.assertEqual(table.scroll_x, 100)
                    clear.assert_not_called()
                    self.assertIn('S 25% ●', table.get_row_at(0)[0].plain)
                table.scroll_to(x=140, animate=False)
                screen.redraw()
                self.assertEqual(table.scroll_x, 140)
                await pilot.pause()
                self.assertEqual(table.scroll_x, 140)
                table.scroll_to(x=100, animate=False)
                screen.model.entries.pop('0')
                screen.model.rebuild()
                screen.redraw()
                self.assertEqual(table.scroll_x, 100)
                await pilot.pause()
                self.assertEqual(table.scroll_x, 100)
                self.assertEqual(table.max_scroll_y, 0)
                await pilot.press('left')
                await pilot.pause(.3)
                self.assertLess(table.scroll_x, 100)
                horizontal_offset = table.scroll_x
                screen.set_page(2)
                self.assertEqual(table.scroll_x, horizontal_offset)
                await pilot.pause()
                self.assertEqual(table.scroll_x, horizontal_offset)
                await pilot.press('up')
                self.assertEqual(screen.pagination.page, 1)
                self.assertEqual(table.cursor_row, table.row_count - 1)
                self.assertEqual(table.scroll_x, horizontal_offset)
                await pilot.press('down')
                self.assertEqual(screen.pagination.page, 2)
                self.assertEqual(table.cursor_row, 0)
                self.assertEqual(table.scroll_x, horizontal_offset)
                await pilot.resize_terminal(120, 42)
                await pilot.pause(.3)
                self.assertGreater(table.max_scroll_x, 0)
                self.assertEqual(table.max_scroll_y, 0)
                self.assertLessEqual(table.row_count,
                                     table.scrollable_content_region.height - int(table.show_header))
                await pilot.press('escape')
                await pilot.pause()

    async def test_file_cursor_crosses_page_edges_and_clamps_at_list_edges(self):
        with tempfile.TemporaryDirectory() as directory:
            fs = VirtualFS({'files': {}})
            app = App()
            async with app.run_test(size=(120, 42)) as pilot:
                screen = ScannerScreen(fs, directory)
                app.push_screen(screen)
                await pilot.pause(.2)
                screen.stop.set()
                screen.worker_thread.join(2)
                while not screen.events.empty():
                    screen.events.get_nowait()
                screen.model.limit = 1000
                screen.model.entries = {
                    str(i): ScanEntry(str(i), f'/file-{i}', False,
                                      state='verified' if i % 2 else 'unknown')
                    for i in range(31)}
                screen.model.rebuild()
                screen.redraw()
                await pilot.pause()
                table = screen.query_one('#scan-details', DataTable)
                table.focus()
                await pilot.press('up')
                self.assertEqual((screen.pagination.page, table.cursor_row), (1, 0))
                if table.row_count > 1:
                    await pilot.press('down')
                    self.assertEqual((screen.pagination.page, table.cursor_row), (1, 1))
                table.move_cursor(row=table.row_count - 1, animate=False)
                await pilot.press('down')
                self.assertEqual((screen.pagination.page, table.cursor_row), (2, 0))
                self.assertIn(f'/file-{screen.page_size}', table.get_row_at(0)[0].plain)
                await pilot.press('up')
                self.assertEqual((screen.pagination.page, table.cursor_row), (1, table.row_count - 1))
                # Reach the final page from the preceding page, including a partial page.
                screen.set_page(screen.pages - 1)
                table.move_cursor(row=table.row_count - 1, animate=False)
                await pilot.press('down')
                self.assertEqual((screen.pagination.page, table.cursor_row), (screen.pages, 0))
                table.move_cursor(row=table.row_count - 1, animate=False)
                await pilot.press('down')
                self.assertEqual(screen.pagination.page, screen.pages)
                self.assertEqual(table.cursor_row, table.row_count - 1)
                # Filtered pages use the matching paths rather than the original bucket offsets.
                screen.file_filter = 'verified'
                screen.set_page(1)
                await pilot.pause()
                table.move_cursor(row=table.row_count - 1, animate=False)
                await pilot.press('down')
                self.assertEqual((screen.pagination.page, table.cursor_row), (2, 0))
                self.assertEqual(table.get_row_at(0)[0].plain,
                                 f'● /file-{2 * screen.page_size + 1}')
                await pilot.press('up')
                self.assertEqual((screen.pagination.page, table.cursor_row), (1, table.row_count - 1))
                screen.file_filter = 'modified'
                screen.show_details()
                await pilot.pause()
                self.assertEqual(table.row_count, 0)
                await pilot.press('up', 'down')
                self.assertEqual((screen.pagination.page, screen.pages), (1, 1))
                self.assertEqual(table.max_scroll_y, 0)
                await pilot.press('escape')
                await pilot.pause()

    async def test_mixed_path_color_and_filter_count_width_growth(self):
        from rich.color import Color
        with tempfile.TemporaryDirectory() as directory:
            fs = VirtualFS({'files': {}})
            app = App()
            async with app.run_test(size=(80, 24)) as pilot:
                screen = ScannerScreen(fs, directory)
                app.push_screen(screen)
                await pilot.pause(.2)
                screen.stop.set()
                screen.worker_thread.join(2)
                while not screen.events.empty():
                    screen.events.get_nowait()
                screen.model.limit = 1000
                screen.model.entries = {
                    'dir': ScanEntry('dir', '/dir', True),
                    'ok': ScanEntry('ok', '/ok', False, state='verified')}
                screen.model.rebuild()
                screen.redraw()
                await pilot.pause()
                grid = screen.query_one(BucketMap)
                button = screen.query_one('#scan-filter-unknown', Button)
                with patch('views.ScannerScreen.time.monotonic', return_value=10):
                    segment = list(grid.render_line(0))[0]
                self.assertEqual(segment.text, '●')
                self.assertEqual(segment.style.color, Color.parse('green'))
                self.assertFalse(button.display)
                directory_button = screen.query_one('#scan-filter-directory', Button)
                self.assertEqual(directory_button.label.plain, 'D directories: 1')
                screen.model.update(ScanEntry('0', '/0', False))
                screen.model.rebuild()
                screen.redraw()
                await pilot.pause()
                with patch('views.ScannerScreen.time.monotonic', return_value=10):
                    self.assertEqual(list(grid.render_line(0))[0].text, '?')
                    self.assertEqual(list(grid.render_line(0))[0].style.color, Color.parse('green'))
                self.assertEqual(button.label.plain, '? unverified: 1')
                original_width = button.size.width
                for count in (10, 100):
                    for i in range(count):
                        screen.model.update(ScanEntry(str(i), '/' + str(i), False))
                    screen.redraw()
                    await pilot.pause()
                    self.assertEqual(button.label.plain, f'? unverified: {count}')
                    self.assertEqual(button.size.width, len(button.label.plain) + 2)
                    self.assertGreater(button.size.width, original_width)
                # Removing the verified entry makes the unknown-only bucket white.
                screen.model.entries.pop('ok')
                screen.model.rebuild()
                screen.redraw()
                await pilot.pause()
                with patch('views.ScannerScreen.time.monotonic', return_value=10):
                    segment = list(grid.render_line(0))[0]
                self.assertEqual(segment.text, '?')
                self.assertEqual(segment.style.color, Color.parse('#ffffff'))
                await pilot.press('escape')
                await pilot.pause()

    async def test_scanner_shortcut_uses_current_directory_despite_selected_child(self):
        spec = importlib.util.spec_from_file_location(
            'drive_tui_scanner_scope', Path(__file__).resolve().parents[1] / 'drive-tui.py')
        tui = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tui)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = ['/a/file', '/b/file', str(root / 'a' / 'file'),
                     str(root / 'b' / 'file'), str(root / 'known')]
            fs = VirtualFS({'files': {path: {checksum(b'abc')} for path in paths}})
            with patch.object(tui, 'VFS', fs), patch(
                    'vfs.filesystem.os.getcwd', return_value=directory), patch(
                    'vfs.scanner.DriveScanner.run'):
                app = tui.DemoApp()
                async with app.run_test(size=(80, 24)) as pilot:
                    for current, selected in (('/', 'a'), ('/', 'b'),
                                              (directory, 'a'), (directory, 'b'),
                                              (directory, 'known'), (directory, '..')):
                        fs.cwd = fs.get_from_path(current)
                        app.refresh_list(target_name=selected)
                        files = app.query_one('#files', DataTable)
                        files.focus()
                        await pilot.pause()
                        self.assertEqual(files.ordered_rows[files.cursor_row].key.value, selected)
                        await pilot.press('s')
                        await pilot.pause()
                        self.assertIsInstance(app.screen, ScannerScreen)
                        screen = app.screen
                        self.assertEqual(screen.path, current)
                        await pilot.press('escape')
                        await pilot.pause()
                        screen.worker_thread.join(2)
                        self.assertEqual(fs.pwd(), current)

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
                summary = str(screen.query_one('#scan-stats', Static).render())
                self.assertFalse(screen.query('#map-start'))
                self.assertIn(f'bucket {start + 1}/{len(screen.model.buckets)}', summary)
                selected = grid.selected
                grid.scroll_to(y=0, animate=False)
                await pilot.pause()
                self.assertEqual(grid.selected, selected)
                self.assertIn(f'bucket 1/{len(screen.model.buckets)}',
                              str(screen.query_one('#scan-stats', Static).render()))
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
