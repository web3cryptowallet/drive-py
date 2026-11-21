"""Expert scanning groups metadata commits without holding write locks during I/O."""
# IMPORT TEST EXPERT SQLITE TRANSACTIONS DEPENDENCIES [
from pathlib import Path
from queue import Queue
from threading import Event
import tempfile
import unittest
from unittest.mock import patch

from vfs import VirtualFS
from vfs.scanner import DriveScanner, ScanControls, ScanEntry, ScanStore
# IMPORT TEST EXPERT SQLITE TRANSACTIONS DEPENDENCIES ]
# VERIFY EXPERT SQLITE TRANSACTION BEHAVIOR [
class ExpertSQLiteTransactionTests(unittest.TestCase):
    # SCANNER FOR EXPERT SQLITE TRANSACTION TESTS [
    def scanner(self, fs, directory, files, buckets=None):
        controls = ScanControls((False, False, True), heavy_order='expert')
        controls.buckets = buckets or tuple((str(file),) for file in files)
        controls.entry_priorities = dict.fromkeys((str(file) for file in files), 0)
        scanner = DriveScanner(fs.db, directory, Queue(), Event(), controls=controls,
            entries=[ScanEntry(str(file), str(file), False, file.stat().st_size) for file in files])
        return scanner, controls
    # SCANNER FOR EXPERT SQLITE TRANSACTION TESTS ]
    # VERIFY NEW FILES USE TWO COMMITS AND EVENTS RUN WITHOUT WRITE LOCK [
    def test_single_file_buckets_combine_result_and_checkpoint_commit(self):
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

                # DELIVER SCANNER EVENTS WITH BACKPRESSURE [
                def emit(event):
                    self.assertFalse(fs.db.conn.in_transaction, event[0])
                    original_emit(event)
                # DELIVER SCANNER EVENTS WITH BACKPRESSURE ]

                with patch.object(scanner, 'emit', side_effect=emit), patch(
                        'vfs.scanner.random.randint', return_value=20):
                    for _ in files:
                        scanner.scan_once(fs.db)
                commits = sum(sql == 'COMMIT' for sql in statements)
                self.assertEqual(commits, len(files))  # Result and resume position share a commit.
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
    # VERIFY NEW FILES USE TWO COMMITS AND EVENTS RUN WITHOUT WRITE LOCK ]
    def test_many_small_files_share_commits_without_io_or_events_under_lock(self):
        import os
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = [root / str(index) for index in range(257)]
            for file in files:
                file.write_bytes(b'small file')
            fs = VirtualFS(None, 'sqlite', db_path=str(root / 'cache.sqlite'))
            try:
                scanner, _ = self.scanner(fs, directory, files,
                    buckets=(tuple(str(file) for file in files),))
                statements = []
                fs.db.conn.set_trace_callback(statements.append)
                original_open = os.open
                original_emit = scanner.emit

                def open_file(*args, **kwargs):
                    self.assertFalse(fs.db.conn.in_transaction)
                    return original_open(*args, **kwargs)

                def emit(event):
                    self.assertFalse(fs.db.conn.in_transaction)
                    if event[0] == 'entry' and event[1].state == 'verified':
                        self.assertIsNotNone(fs.db.conn.execute(
                            'SELECT 1 FROM nodes WHERE id=?', (event[1].path,)).fetchone())
                        self.assertEqual(ScanStore(fs.db).get('entry', event[1].id)['state'], 'verified')
                    original_emit(event)

                with patch('vfs.scanner.os.open', side_effect=open_file), \
                        patch.object(scanner, 'emit', side_effect=emit), \
                        patch('vfs.scanner.time.monotonic', return_value=100.):
                    scanner.scan_once(fs.db)
                self.assertLessEqual(sum(sql == 'COMMIT' for sql in statements), 4)
                self.assertEqual(scanner.paths, len(files))
                self.assertFalse(scanner.pending_heavy)
                self.assertEqual(fs.db.conn.execute(
                    "SELECT COUNT(*) FROM scan_state WHERE kind='checksum'").fetchone()[0], len(files))
                self.assertEqual(fs.db.conn.execute(
                    "SELECT COUNT(*) FROM scan_state WHERE kind='entry'").fetchone()[0], len(files))
            finally:
                fs.db.conn.close()

    def test_failed_batch_rolls_back_catalog_checksums_and_states(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = [root / str(index) for index in range(2)]
            for file in files:
                file.write_bytes(b'abc')
            fs = VirtualFS(None, 'sqlite', db_path=str(root / 'cache.sqlite'))
            try:
                scanner, _ = self.scanner(fs, directory, files,
                    buckets=(tuple(str(file) for file in files),))
                original_add = fs.db.add_scanned_file

                def fail_second(path, *args):
                    if path == str(files[1]):
                        raise ValueError('batch failure')
                    return original_add(path, *args)

                with patch.object(fs.db, 'add_scanned_file', side_effect=fail_second), \
                        patch('vfs.scanner.time.monotonic', return_value=100.):
                    with self.assertRaisesRegex(ValueError, 'batch failure'):
                        scanner.scan_once(fs.db)
                self.assertFalse(fs.db.conn.in_transaction)
                self.assertFalse(scanner.remembered)
                for file in files:
                    self.assertIsNone(ScanStore(fs.db).get('checksum', str(file)))
                    self.assertIsNone(ScanStore(fs.db).get('entry', str(file)))
                    self.assertIsNone(fs.db.conn.execute(
                        'SELECT 1 FROM nodes WHERE id=?', (str(file),)).fetchone())
            finally:
                fs.db.conn.close()

    # VERIFY NESTED METADATA WRITES ROLLBACK TOGETHER [
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
    # VERIFY NESTED METADATA WRITES ROLLBACK TOGETHER ]
    # VERIFY INTERRUPTED BUCKET KEEPS REAL REMAINING CHECKPOINT [
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

                # PAUSE FOR TEST INTERRUPTED BUCKET KEEPS REAL REMAINING CHECKPOINT [
                def pause(db, entry):
                    original_publish(db, entry)
                    scanner.stop.set()
                # PAUSE FOR TEST INTERRUPTED BUCKET KEEPS REAL REMAINING CHECKPOINT ]

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
    # VERIFY INTERRUPTED BUCKET KEEPS REAL REMAINING CHECKPOINT ]
# VERIFY EXPERT SQLITE TRANSACTION BEHAVIOR ]
