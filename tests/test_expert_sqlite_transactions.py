"""Expert scanning groups metadata commits without holding write locks during I/O."""
from pathlib import Path
from queue import Queue
from threading import Event
import tempfile
import unittest
from unittest.mock import patch

from vfs import VirtualFS
from vfs.scanner import DriveScanner, ScanControls, ScanEntry, ScanStore


class ExpertSQLiteTransactionTests(unittest.TestCase):
    def scanner(self, fs, directory, files, buckets=None):
        controls = ScanControls((False, False, True), heavy_order='expert')
        controls.buckets = buckets or tuple((str(file),) for file in files)
        controls.entry_priorities = dict.fromkeys((str(file) for file in files), 0)
        scanner = DriveScanner(fs.db, directory, Queue(), Event(), controls=controls,
            entries=[ScanEntry(str(file), str(file), False, file.stat().st_size) for file in files])
        return scanner, controls

    def test_new_files_use_two_commits_and_events_run_without_write_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = [root / str(index) for index in range(4)]
            for file in files:
                file.write_bytes(b'abc')
            db_path = str(root / 'cache.sqlite')
            fs = VirtualFS(None, 'sqlite', db_path=db_path)
            try:
                scanner, controls = self.scanner(fs, directory, files)
                statements = []
                fs.db.conn.set_trace_callback(statements.append)
                original_emit = scanner.emit

                def emit(event):
                    self.assertFalse(fs.db.conn.in_transaction, event[0])
                    original_emit(event)

                with patch.object(scanner, 'emit', side_effect=emit), patch(
                        'vfs.scanner.random.randint', return_value=20):
                    for _ in files:
                        scanner.scan_once(fs.db)
                commits = sum(sql == 'COMMIT' for sql in statements)
                self.assertEqual(commits, 2 * len(files) + 1)  # One final checkpoint.
                self.assertEqual(scanner.paths, len(files))
                self.assertTrue(all(entry.state == 'verified' for entry in scanner.entries.values()))
                self.assertEqual(controls.selected_buckets, ())
            finally:
                fs.db.conn.close()
            reopened = VirtualFS(None, 'sqlite', db_path=db_path)
            try:
                store = ScanStore(reopened.db)
                self.assertIsNone(store.get('position', directory)['3'])
                for file in files:
                    self.assertEqual(store.get('entry', str(file))['state'], 'verified')
                    self.assertEqual(store.get('checksum', str(file))['size'], 3)
                    self.assertEqual(reopened.get_from_path(str(file)).size, 3)
            finally:
                reopened.db.conn.close()

    def test_nested_metadata_writes_rollback_together(self):
        with tempfile.TemporaryDirectory() as directory:
            fs = VirtualFS(None, 'sqlite', db_path=str(Path(directory) / 'cache.sqlite'))
            try:
                store = ScanStore(fs.db)
                with self.assertRaisesRegex(RuntimeError, 'abort'):
                    with fs.db.write_transaction():
                        store.put('checksum', '/disk/file', {'size': 3, 'hash': 'md5:abc'})
                        fs.db.add_scanned_file('/disk/file', 'md5:abc', 3)
                        raise RuntimeError('abort')
                self.assertIsNone(store.get('checksum', '/disk/file'))
                self.assertIsNone(fs.db.conn.execute(
                    'SELECT 1 FROM nodes WHERE id=?', ('/disk/file',)).fetchone())
                self.assertFalse(fs.db.conn.in_transaction)
            finally:
                fs.db.conn.close()

    def test_interrupted_bucket_keeps_real_remaining_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = [root / str(index) for index in range(3)]
            for file in files:
                file.write_bytes(b'abc')
            db_path = str(root / 'cache.sqlite')
            fs = VirtualFS(None, 'sqlite', db_path=db_path)
            try:
                scanner, controls = self.scanner(fs, directory, files,
                    buckets=(tuple(str(file) for file in files),))
                original_publish = scanner.publish

                def pause(db, entry):
                    original_publish(db, entry)
                    scanner.stop.set()

                with patch.object(scanner, 'publish', side_effect=pause):
                    scanner.scan_once(fs.db)
                checkpoint = ScanStore(fs.db).get('position', directory)['3']
                self.assertEqual(set(checkpoint['remaining']), {str(file) for file in files[1:]})
            finally:
                fs.db.conn.close()
            reopened = VirtualFS(None, 'sqlite', db_path=db_path)
            try:
                scanner, _ = self.scanner(reopened, directory, files,
                    buckets=(tuple(str(file) for file in files),))
                scanner.scan_once(reopened.db)
                self.assertEqual(scanner.paths, 2)
                self.assertIsNone(ScanStore(reopened.db).get('position', directory)['3'])
            finally:
                reopened.db.conn.close()
