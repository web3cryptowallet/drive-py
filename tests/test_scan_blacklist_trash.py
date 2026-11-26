"""Blacklist pruning/markers and recoverable catalog-only removal."""
import asyncio
import importlib.util
from pathlib import Path
from queue import Queue
from threading import Event
import tempfile
import unittest
from unittest.mock import patch
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS
from vfs.scanner import DriveScanner, ScanControls, FileMap, ScanEntry
from vfs.db_trash import DBTrash

spec = importlib.util.spec_from_file_location('exclusion_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class ScanExclusionTests(unittest.TestCase):
    def test_prunes_before_disk_reads_and_marks_bucket_red(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'skip').mkdir()
            (root / 'skip' / 'hidden').write_bytes(b'never read')
            (root / 'skip2').mkdir()
            (root / 'skip2' / 'file').write_bytes(b'ok')
            fs = VirtualFS({'files': {}})
            controls = ScanControls(startup=True)
            excluded = str(root / 'skip')
            controls.excluded_paths = (excluded,)
            scanner = DriveScanner(fs.db, directory, Queue(), Event(), controls=controls)
            original = scanner.disk_info
            reads = []
            def disk(path):
                reads.append(path)
                return original(path)
            with patch.object(scanner, 'disk_info', side_effect=disk):
                scanner.scan_once(fs.db)
            self.assertFalse(any(path == excluded or path.startswith(excluded + '/') for path in reads))
            self.assertTrue(scanner.entries[excluded].blacklisted)
            self.assertNotIn(excluded + '/hidden', scanner.entries)
            self.assertEqual(scanner.mode_counts[2][0], 1)
            model = FileMap()
            model.update(scanner.entries[excluded])
            from types import SimpleNamespace
            screen = SimpleNamespace(model=model, backgrounds={}, expert_blue=set(), selected=0, follow_end=False)
            control = tui.MapControl(screen)
            (style, symbol), _ = control.render_cell(0, 0, False)
            self.assertEqual(symbol, '!')
            self.assertIn('fg:#ff5555', style)
            screen.selected = 1
            (style, symbol), _ = control.render_cell(0, 0, False)
            self.assertIn('bg:#000000', style)
            self.assertEqual(symbol, '!')

    def test_present_archived_paths_can_be_rescanned(self):
        for backend in ('memory', 'sqlite'):
            with self.subTest(backend=backend), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                folder = root / 'folder'
                folder.mkdir()
                path = folder / 'file'
                path.write_bytes(b'keep')
                fs = VirtualFS({'files': {}}) if backend == 'memory' else VirtualFS(None, 'sqlite', db_path=str(root / 'db.sqlite'))
                try:
                    fs.db.add_scanned_file(str(path), 'md5:01234567890123456789012345678901', 4)
                    trash = DBTrash(fs.db)
                    self.assertEqual(trash.move(str(folder)), 2)
                    self.assertEqual(path.read_bytes(), b'keep')
                    self.assertEqual(set(trash.records()), {str(folder), str(path)})
                    if backend == 'sqlite':
                        self.assertEqual(fs.db.conn.execute('SELECT count(*) FROM nodes WHERE id=?', (str(path),)).fetchone()[0], 0)
                        self.assertEqual(fs.db.conn.execute('SELECT count(*) FROM D').fetchone()[0], 2)
                    from vfs.scanner import ScanStore
                    legacy = ScanStore(fs.db)
                    legacy.put('entry', str(path), {'state': 'verified', 'size': 4})
                    legacy.put('checksum', str(path), {'size': 4, 'hash': 'md5:' + '0' * 32})
                    controls = ScanControls(startup=True)
                    scanner = DriveScanner(fs.db, str(folder), Queue(), Event(), controls=controls)
                    scanner.scan_once(fs.db)
                    self.assertIn(str(path), scanner.entries)
                    self.assertEqual(scanner.entries[str(path)].state, 'verified')
                    self.assertEqual(scanner.mode_counts[2][0], 1)
                finally:
                    if backend == 'sqlite':
                        fs.db.conn.close()

    def test_fragmented_trash_is_persistent_and_updates_totals(self):
        from vfs.adapter.sqlite import SQLiteDBAdapter
        from vfs.adapter.fragmented import FragmentedSQLiteDBAdapter
        with tempfile.TemporaryDirectory() as directory:
            filename = str(Path(directory) / 'catalog.sqlite')
            base = SQLiteDBAdapter(filename)
            base.update({'/disk/a': {'MD5:same:4'}, '/disk/sub/b': {'MD5:same:6'},
                         '/other/c': {'MD5:other:2'}})
            base.conn.close()
            db = FragmentedSQLiteDBAdapter(filename, {'/disk': str(Path(directory) / 'disk.sqlite')}, refragment=True)
            try:
                trash = DBTrash(db)
                self.assertEqual(trash.move('/disk'), 4)
                self.assertIsNone(db.get_child(db.get_root(), 'disk'))
                self.assertEqual(db.get_root().size, 2)
                self.assertFalse(db.get_hash_dups('MD5:same:4'))
                self.assertFalse(db.get_hash_dups('MD5:same:6'))
                self.assertEqual(set(trash.records()), {'/disk', '/disk/a', '/disk/sub', '/disk/sub/b'})
            finally:
                db.conn.close()
            reopened = FragmentedSQLiteDBAdapter(filename)
            try:
                self.assertEqual(DBTrash(reopened).roots(), ('/disk',))
                self.assertIsNone(reopened.get_child(reopened.get_root(), 'disk'))
            finally:
                reopened.conn.close()


class ExclusionInputTests(unittest.IsolatedAsyncioTestCase):
    async def test_d_selection_delete_keys(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
            root = Path(directory)
            fs = VirtualFS({'files': {}})
            trash = DBTrash(fs.db)
            for name in ('a', 'b', 'c'):
                fs.db.add_scanned_file(str(root / name), 'md5:' + name, 4)
                trash.move(str(root / name))
            with patch.object(tui, 'HISTORY_PATH', root / 'history.llog'):
                browser = tui.DriveBrowser(fs, path=directory, input=pipe, output=DummyOutput())
            view = tui.DBTrashView(browser)
            browser.push(view)
            task = asyncio.create_task(browser.app.run_async(set_exception_handler=False))
            try:
                await asyncio.sleep(.05)
                pipe.send_text('/a')
                await asyncio.sleep(.04)
                self.assertEqual(len(view.rows()), 1)
                pipe.send_text('\r')
                await asyncio.sleep(.04)
                self.assertTrue(browser.app.layout.has_focus(view.table))
                self.assertEqual(view.search.text, 'a')
                self.assertFalse(view.expanded)
                pipe.send_text('/')
                await asyncio.sleep(.04)
                pipe.send_text('\x1b')
                # Standalone Escape is delayed by the terminal parser.
                await asyncio.sleep(.6)
                self.assertTrue(browser.app.layout.has_focus(view.table))
                self.assertEqual(view.search.text, '')
                self.assertEqual(len(view.rows()), 3)
                for key in ('\x1b[2~', '\x1b[2~'):
                    pipe.send_text(key)
                    await asyncio.sleep(.04)
                self.assertEqual(len(view.marked), 2)
                pipe.send_text('-')
                await asyncio.sleep(.04)
                self.assertFalse(view.marked)
                pipe.send_text('\x1b[H')
                await asyncio.sleep(.04)
                pipe.send_text('\x1b[2~')
                await asyncio.sleep(.04)
                pipe.send_text('\x1b[3~')
                await asyncio.sleep(.04)
                self.assertEqual(len(trash.records()), 2)
                pipe.send_text('\x1b[3;5~')
                await asyncio.sleep(.04)
                self.assertFalse(trash.records())
            finally:
                browser.app.exit()
                await task

    async def test_d_mark_remove_clear_and_reopen(self):
        from prompt_toolkit.input import DummyInput
        for backend in ('memory', 'sqlite'):
            with self.subTest(backend=backend), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                options = {'db_path': str(root / 'catalog.sqlite')} if backend == 'sqlite' else {}
                fs = VirtualFS({'files': {}}, backend, **options)
                try:
                    trash = DBTrash(fs.db)
                    for name in ('a', 'b', 'c'):
                        file = root / name
                        file.write_bytes(b'keep')
                        fs.db.add_scanned_file(str(file), 'md5:' + name, 4)
                        trash.move(str(file))
                    browser = tui.DriveBrowser(fs, path=directory, input=DummyInput(), output=DummyOutput())
                    view = tui.DBTrashView(browser)
                    browser.push(view)
                    view.rows()
                    first, second = view.items[0][1], view.items[1][1]
                    view.toggle_mark()
                    self.assertEqual(view.table.index, 1)
                    self.assertEqual(view.marked, {first})
                    self.assertTrue(any('fg:#ffd700' in style for style, _ in view.rows()[0]))
                    view.toggle_mark()
                    self.assertEqual(view.marked, {first, second})
                    view.clear_marks()
                    self.assertFalse(view.marked)
                    view.table.index = 0
                    view.toggle_mark()
                    view.toggle_mark()
                    view.search.text = 'no-match'
                    view.remove_marked()
                    self.assertEqual(len(trash.records()), 1)
                    self.assertFalse(view.marked)
                    view.search.text = ''
                    view.rows()
                    # Duplicate/message rows must not delete active files or archives.
                    view.items = [('duplicate', str(root / 'a'))]
                    view.rows_key = (view.table.width, view.search.text, view.rows_revision, browser.show_path_prefixes)
                    view.table.index = 0
                    view.remove_marked()
                    self.assertEqual(len(trash.records()), 1)
                    view.rows_revision += 1
                    view.remove_marked()  # Cursor fallback.
                    self.assertFalse(trash.records())
                    for name in ('a', 'b'):
                        fs.db.add_scanned_file(str(root / name), 'md5:' + name, 4)
                        trash.move(str(root / name))
                    view.search.text = 'no-match'
                    view.remove_marked(all_entries=True)
                    self.assertFalse(trash.records())
                    self.assertFalse(view.rows())
                    self.assertEqual(view.table.index, 0)
                    self.assertTrue(all((root / name).read_bytes() == b'keep' for name in ('a', 'b', 'c')))
                finally:
                    if backend == 'sqlite':
                        fs.db.conn.close()
                if backend == 'sqlite':
                    reopened = VirtualFS(None, backend, **options)
                    try:
                        self.assertFalse(DBTrash(reopened.db).records())
                    finally:
                        reopened.db.conn.close()

    def test_reset_vscode_files_and_folder_rescans_from_scratch(self):
        from vfs.scanner import ScanStore
        for backend in ('memory', 'sqlite'):
            for folder_scope in (False, True):
                with self.subTest(backend=backend, folder=folder_scope), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    folder = root / '.vscode'
                    folder.mkdir()
                    files = [folder / 'settings.json', folder / 'tasks.json']
                    options = {'db_path': str(root / 'db.sqlite')} if backend == 'sqlite' else {}
                    fs = VirtualFS({'files': {}}, backend, **options)
                    try:
                        store = ScanStore(fs.db)
                        for file in files:
                            file.write_bytes(b'new contents')
                            fs.db.add_scanned_file(str(file), 'md5:' + '0' * 32, 1)
                            store.put('checksum', str(file), {'size': 1, 'hash': 'md5:' + '0' * 32})
                            store.put('entry', str(file), {'state': 'verified', 'size': 1})
                        store.put('map', str(folder), {'entries': []})
                        store.put('position', str(folder), {'1': {'stack': [], 'seen': []}})
                        trash = DBTrash(fs.db)
                        roots = (str(folder),) if folder_scope else tuple(map(str, files))
                        for path in roots:
                            trash.move(path, archive=False)
                        self.assertFalse(trash.records())
                        self.assertIsNone(store.get('map', str(folder)))
                        self.assertIsNone(store.get('position', str(folder)))
                        for file in files:
                            self.assertIsNone(store.get('checksum', str(file)))
                            self.assertIsNone(store.get('entry', str(file)))
                        scanner = DriveScanner(fs.db, str(folder), Queue(), Event(),
                            controls=ScanControls(startup=True), scan_roots=roots)
                        scanner.scan_once(fs.db)
                        for file in files:
                            self.assertEqual(scanner.entries[str(file)].state, 'verified')
                            self.assertEqual(store.get('checksum', str(file))['size'], len(b'new contents'))
                        self.assertEqual(scanner.mode_counts[2][0], 2)
                    finally:
                        if backend == 'sqlite':
                            fs.db.conn.close()

    def test_sqlite_reset_does_not_load_unrelated_scan_payloads(self):
        from vfs.scanner import ScanStore
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / 'folder'
            folder.mkdir()
            file = folder / 'file'
            file.write_bytes(b'rescan')
            fs = VirtualFS(None, 'sqlite', db_path=str(root / 'catalog.sqlite'))
            try:
                fs.db.add_scanned_file(str(file), 'md5:old', 6)
                trash = DBTrash(fs.db)
                store = ScanStore(fs.db)
                for kind in ('entry', 'checksum'):
                    store.put(kind, str(file), {'state': 'verified'})
                    store.put(kind, str(folder) + '2/file', {'keep': True})
                selection = str(folder) + '::selection:["file"]'
                for kind in ('map', 'position'):
                    store.put(kind, directory, {'old': True})
                    store.put(kind, selection, {'old': True})
                    # Even an unreadable unrelated payload must not affect reset.
                    fs.db.conn.execute('INSERT INTO scan_state VALUES (?,?,?)',
                                       (kind, '/unrelated', 'invalid JSON'))
                fs.db.conn.commit()
                with patch.object(trash.store, 'items', side_effect=AssertionError('global payload load')):
                    self.assertEqual(trash.move(str(folder), archive=False), 2)
                for kind in ('entry', 'checksum'):
                    self.assertIsNone(store.get(kind, str(file)))
                    self.assertEqual(store.get(kind, str(folder) + '2/file'), {'keep': True})
                for kind in ('map', 'position'):
                    self.assertIsNone(store.get(kind, directory))
                    self.assertIsNone(store.get(kind, selection))
                    self.assertEqual(fs.db.conn.execute(
                        'SELECT value FROM scan_state WHERE kind=? AND key=?',
                        (kind, '/unrelated')).fetchone()[0], 'invalid JSON')
                scanner = DriveScanner(fs.db, str(folder), Queue(), Event(),
                                       controls=ScanControls(startup=True))
                scanner.scan_once(fs.db)
                self.assertEqual(scanner.entries[str(file)].state, 'verified')
                self.assertEqual(file.read_bytes(), b'rescan')
                self.assertFalse(trash.records())
            finally:
                fs.db.conn.close()

    async def test_multiple_marked_files_confirmation_cancel_and_remove(self):
        from prompt_toolkit.input import DummyInput
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fs = VirtualFS({'files': {}})
            for name in ('one', 'two', 'keep'):
                (root / name).write_bytes(b'abc')
                fs.db.add_scanned_file(str(root / name), 'md5:' + name, 3)
            with patch.object(tui, 'HISTORY_PATH', root / 'history.llog'):
                browser = tui.DriveBrowser(fs, path=directory, input=DummyInput(), output=DummyOutput())
            for name in ('one', 'two'):
                browser.selected = next(i for i, row in enumerate(browser.rows) if row['name'] == name)
                browser.toggle_scan_selection()
            browser.selected = next(i for i, row in enumerate(browser.rows) if row['name'] == 'keep')
            browser.trash_selected()
            dialog = browser.screen_stack[-1][0]
            self.assertEqual(set(dialog.paths), {str(root / 'one'), str(root / 'two')})
            self.assertEqual(dialog.question, 'Remove 2 items from db?')
            self.assertEqual(tui.RemoveDBConfirmView(browser, (directory,)).question,
                             'Remove 1 items from db?')
            dialog.close()
            self.assertFalse(browser.db_trash.records())
            self.assertEqual(len(browser.scan_selection), 2)
            browser.trash_selected()
            browser.screen_stack[-1][0].confirm()
            await asyncio.sleep(.05)
            self.assertFalse(browser.db_trash.records())
            self.assertIn('keep', [row['name'] for row in browser.rows])
            self.assertFalse(browser.scan_selection)
            for name in ('one', 'two'):
                row = next(row for row in browser.rows if row['name'] == name)
                self.assertEqual(row['indicator'], 'orange')
            # Timestamp order must take precedence over path order.
            records = {str(root / name): dict(node={'size': 3, 'info': {}}, trashed_at='') for name in ('one', 'two')}
            records[str(root / 'one')]['trashed_at'] = '2026-11-24T12:00:00+00:00'
            records[str(root / 'two')]['trashed_at'] = '2026-11-23T12:00:00+00:00'
            with patch.object(browser.db_trash, 'records', return_value=records):
                view = tui.DBTrashView(browser)
            view.rows()
            self.assertEqual(view.items[:2], [('trash', str(root / 'one')), ('trash', str(root / 'two'))])
            self.assertTrue(all((root / name).is_file() for name in ('one', 'two', 'keep')))

    async def test_trash_hash_expansion_timestamp_and_duplicate_jump(self):
        from prompt_toolkit.input import DummyInput
        for backend in ('memory', 'sqlite'):
            with self.subTest(backend=backend), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                removed, duplicate = root / 'removed', root / 'copy'
                removed.write_bytes(b'same')
                duplicate.write_bytes(b'same')
                options = {'db_path': str(root / 'catalog.sqlite')} if backend == 'sqlite' else {}
                fs = VirtualFS({'files': {}}, backend, **options)
                digest = 'md5:01234567890123456789012345678901'
                fs.db.add_scanned_file(str(removed), digest, 4)
                fs.db.add_scanned_file(str(duplicate), digest, 4)
                digest = fs.get_from_path(str(removed)).info['hashinfo']
                trash = DBTrash(fs.db)
                trash.move(str(removed))
                if backend == 'sqlite':
                    fs.db.conn.close()
                    fs = VirtualFS(None, backend, **options)
                    trash = DBTrash(fs.db)
                self.assertEqual(trash.records()[str(removed)]['node']['info']['hashinfo'], digest)
                browser = tui.DriveBrowser(fs, path=directory, input=DummyInput(), output=DummyOutput())
                view = tui.DBTrashView(browser)
                browser.push(view)
                view.table.width = 150
                rows = view.rows()
                text = ''.join(part for _, part in rows[0])
                self.assertRegex(text, r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}  ')
                self.assertTrue(text.endswith('4 bytes ' + digest.split(':')[-2][-6:]))
                self.assertEqual(tui.get_cwidth(text), 150)
                view.choose()
                self.assertEqual(view.items, [('trash', str(removed))])
                rows = view.rows()
                self.assertEqual(view.items[1], ('duplicate', str(duplicate)))
                self.assertIn(('class:green', '● '), rows[1])
                with patch.object(tui, 'get_stat_info', side_effect=AssertionError('stat during redraw')):
                    view.rows()
                    view.table.move(1)
                    view.table.create_content(150, 10).get_line(1)
                view.table.index = 0
                view.search_focus()
                self.assertTrue(browser.app.layout.has_focus(view.search))
                view.search.text = 'REMOVED'
                rows = view.rows()
                self.assertEqual(len(rows), 2)
                self.assertEqual([text for style, text in rows[0] if 'bg:#ffff00' in style], ['removed'])
                self.assertEqual(tui.get_cwidth(''.join(text for _, text in rows[0])), 150)
                view.search.text = 'COPY'
                self.assertEqual(view.items[0][0], 'trash')
                self.assertEqual(len(view.rows()), 2)
                self.assertEqual([text for style, text in view.rows()[1] if 'bg:#ffff00' in style], ['copy'])
                # Selected rendering retains the Help highlight colors.
                view.table.index = 1
                rendered = view.table.create_content(150, 10).get_line(1)
                self.assertTrue(any('class:selected' in style and 'bg:#ffff00' in style for style, _ in rendered))
                view.search.text = 'no-such-file'
                self.assertEqual(view.rows(), [])
                view.search.text = ''
                self.assertFalse(any('bg:#ffff00' in style for row in view.rows() for style, _ in row))
                view.escape()
                self.assertTrue(browser.app.layout.has_focus(view.table))
                self.assertEqual(view.search.text, '')
                self.assertEqual(tui.DBTrashView.summary({'size': 0}), '0 bytes')
                view.choose()  # collapse
                self.assertEqual(len(view.rows()), 1)
                duplicate.unlink()
                view.choose()  # expand again; refresh disk status
                self.assertIn(('class:red', '● '), view.rows()[1])
                duplicate.write_bytes(b'same')
                view.choose()  # collapse
                view.choose()  # expand again; present -> green
                self.assertIn(('class:green', '● '), view.rows()[1])
                view.table.index = 1
                view.choose()
                self.assertFalse(browser.screen_stack)
                self.assertEqual(browser.current_name(), 'copy')
                self.assertTrue(removed.exists())
                if backend == 'sqlite':
                    fs.db.conn.close()

    async def test_trash_cursor_redraw_reuses_formatted_rows(self):
        from prompt_toolkit.input import DummyInput
        with tempfile.TemporaryDirectory() as directory:
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=DummyInput(), output=DummyOutput())
            view = tui.DBTrashView(browser)
            view.records = {f'/folder/file{i}': {
                'trashed_at': '2026-11-22T12:00:00+00:00',
                'node': {'size': i, 'info': {'hashinfo': 'md5:abcdef123456:4'}}}
                for i in range(5000)}
            view.table.width, view.table.height = 100, 20
            initial = view.rows()
            with patch.object(view, 'summary', side_effect=AssertionError('reformatted on movement')), \
                    patch.object(view, 'timestamp', side_effect=AssertionError('parsed date on movement')), \
                    patch.object(browser, 'display_path', side_effect=AssertionError('converted path on movement')):
                for _ in range(20):
                    view.table.move(1)
                    view.header()
                    view.table.create_content(100, 20).get_line(view.table.index)
                    view.table.maximum_pan()
                    self.assertIs(view.rows(), initial)
            view.search.text = 'file42'
            filtered = view.rows()
            self.assertIsNot(filtered, initial)
            self.assertLess(len(filtered), len(initial))
            view.table.width = 120
            resized = view.rows()
            self.assertIsNot(resized, filtered)
            browser.show_path_prefixes = not browser.show_path_prefixes
            self.assertIsNot(view.rows(), resized)

    async def test_visibility_and_database_trash_keys(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
            root = Path(directory)
            (root / 'skip').mkdir()
            (root / 'skip2').mkdir()
            path = root / 'file'
            path.write_bytes(b'keep')
            fs = VirtualFS({'files': {}})
            fs.db.add_scanned_file(str(path), 'md5:01234567890123456789012345678901', 4)
            with patch.object(tui, 'HISTORY_PATH', root / 'history.llog'):
                browser = tui.DriveBrowser(fs, path=directory, input=pipe, output=DummyOutput())
            browser.blacklist = {str(root / 'skip')}
            task = asyncio.create_task(browser.app.run_async(set_exception_handler=False))
            try:
                await asyncio.sleep(.05)
                pipe.send_text('\x02')
                await asyncio.sleep(.05)
                self.assertNotIn('skip', [row['name'] for row in browser.rows])
                self.assertIn('skip2', [row['name'] for row in browser.rows])
                pipe.send_text('\x02')
                await asyncio.sleep(.05)
                self.assertIn('skip', [row['name'] for row in browser.rows])
                browser.selected = next(i for i, row in enumerate(browser.rows) if row['name'] == 'file')
                pipe.send_text('\x04')
                await asyncio.sleep(.05)
                self.assertIsInstance(browser.screen_stack[-1][0], tui.RemoveDBConfirmView)
                dialog = browser.screen_stack[-1][0]
                screen = browser.app.renderer.last_rendered_screen
                lines = [''.join(screen.data_buffer[y][x].char for x in range(80)) for y in range(40)]
                self.assertEqual(dialog.question, 'Remove 1 items from db?')
                question_y = next(y for y, line in enumerate(lines) if dialog.question in line)
                question_line = lines[question_y]
                question_start = question_line.index(dialog.question)
                left = question_line.rindex('│', 0, question_start)
                right = question_line.index('│', question_start)
                self.assertEqual(right - left + 1, 34)
                question_x = question_line.index(dialog.question)
                self.assertLessEqual(abs((question_x - left) - (right - question_x - len(dialog.question) + 1)), 1)
                self.assertEqual(lines[question_y - 2][left], '┌')
                self.assertEqual(lines[question_y - 2][right], '┐')
                self.assertEqual(lines[question_y + 4][left], '└')
                self.assertEqual(lines[question_y + 4][right], '┘')
                self.assertIn('Remove', lines[question_y + 2])
                self.assertIn('Cancel', lines[question_y + 2])
                self.assertTrue(browser.app.layout.has_focus(dialog.focus))
                for key in ('\x1b[C', '\x1b[D', '\t', '\t'):
                    previous = browser.app.layout.current_control
                    pipe.send_text(key)
                    await asyncio.sleep(.03)
                    self.assertIsNot(browser.app.layout.current_control, previous)
                self.assertTrue(browser.app.layout.has_focus(dialog.focus))
                self.assertIn('file', [row['name'] for row in browser.rows])
                pipe.send_text('y')
                await asyncio.sleep(.1)
                row = next(row for row in browser.rows if row['name'] == 'file')
                self.assertEqual(row['indicator'], 'orange')
                self.assertEqual(row['node'].info['status'], 'new')
                self.assertEqual(browser.scan_row_marker(row), '●')
                self.assertTrue(path.is_file())
                self.assertTrue(any(entry['action'] == 'reset scan info' and entry['path'] == str(path)
                                    for entry in browser.action_history.entries))
                pipe.send_text('d')
                await asyncio.sleep(.05)
                self.assertIsInstance(browser.screen_stack[-1][0], tui.DBTrashView)
                trash_view = browser.screen_stack[-1][0]
                pipe.send_text('h')
                await asyncio.sleep(.05)
                help_view = browser.screen_stack[-1][0]
                self.assertIsInstance(help_view, tui.TrashHelpView)
                self.assertIn('Ctrl+Delete: clear ALL', help_view.text)
                self.assertTrue(any(style == '#ff8800' and 'Insert' in text for style, text in help_view.focus.text))
                pipe.send_text('\r')
                await asyncio.sleep(.05)
                self.assertIs(browser.screen_stack[-1][0], trash_view)
                pipe.send_text('/h')
                await asyncio.sleep(.05)
                self.assertEqual(trash_view.search.text, 'h')
                self.assertIs(browser.screen_stack[-1][0], trash_view)
            finally:
                browser.app.exit()
                await task
