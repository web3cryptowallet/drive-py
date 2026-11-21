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

    def test_database_trash_keeps_files_and_blocks_reimport(self):
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
                    controls = ScanControls(startup=True)
                    scanner = DriveScanner(fs.db, str(folder), Queue(), Event(), controls=controls)
                    scanner.scan_once(fs.db)
                    self.assertFalse(scanner.entries)
                    self.assertEqual(scanner.mode_counts[2][0], 0)
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
                await asyncio.sleep(.1)
                self.assertNotIn('file', [row['name'] for row in browser.rows])
                self.assertTrue(path.is_file())
                self.assertTrue(any(entry['action'] == 'database trash' and entry['path'] == str(path)
                                    for entry in browser.action_history.entries))
                pipe.send_text('D')
                await asyncio.sleep(.05)
                self.assertIsInstance(browser.screen_stack[-1][0], tui.DBTrashView)
            finally:
                browser.app.exit()
                await task
