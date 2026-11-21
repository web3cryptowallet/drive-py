"""Directory-local checksum loading preserves missing paths and bounds decoding."""
import json
from pathlib import Path
from queue import Queue
from threading import Event
import tempfile
import unittest
from unittest.mock import patch

from vfs import VirtualFS
from vfs.scanner import DriveScanner, ScanStore


class ChecksumDirectoryTests(unittest.TestCase):
    def test_directory_scope_and_literal_names(self):
        for backend in ('memory', 'sqlite'):
            with self.subTest(backend=backend), tempfile.TemporaryDirectory() as directory:
                fs = VirtualFS({'files': {}}, backend, **(
                    {'db_path': str(Path(directory) / 'cache')} if backend == 'sqlite' else {}))
                try:
                    store = ScanStore(fs.db)
                    value = {'size': 3, 'hash': 'md5:abc'}
                    for path in ('/a_%/file', '/a_%/child/missing', '/a_%/child/deep/file',
                                 '/a_OTHER/file', '/a_%other/file'):
                        store.put('checksum', path, value)
                    with patch('vfs.scanner.json.loads', wraps=json.loads) as decode:
                        files, dirs = store.checksum_directory('/a_%')
                    self.assertEqual(files, {'/a_%/file': value})
                    self.assertEqual(dirs, {'child'})
                    self.assertEqual(decode.call_count, 1)
                    files, dirs = store.checksum_directory('/')
                    self.assertFalse(files)
                    self.assertEqual(dirs, {'a_%', 'a_OTHER', 'a_%other'})
                finally:
                    if backend == 'sqlite':
                        fs.db.conn.close()

    def test_discovery_preserves_checksum_only_missing_descendants(self):
        with tempfile.TemporaryDirectory() as directory:
            fs = VirtualFS({'files': {}})
            store = ScanStore(fs.db)
            path = directory + '/absent/nested/file'
            store.put('checksum', path, {'size': 3, 'hash': 'md5:abc'})
            # An unrelated corrupt payload must never be decoded by this scope.
            fs.db.scan_state['checksum', '/unrelated/file'] = 'invalid json'
            scanner = DriveScanner(fs.db, directory, Queue(), Event())
            original_items = ScanStore.items

            def scoped_items(instance, kind):
                self.assertNotEqual(kind, 'checksum', 'global checksum read')
                return original_items(instance, kind)

            with patch.object(ScanStore, 'items', scoped_items):
                scanner.scan_once(fs.db)
            self.assertIn(path, scanner.entries)
            self.assertFalse(scanner.entries[path].is_dir)
            self.assertEqual(scanner.entries[path].size, 3)

    def test_cache_reuses_directory_and_evicts_old_scopes(self):
        scanner = DriveScanner(None, '/', Queue(), Event())
        from unittest.mock import Mock
        scanner.store = Mock()
        scanner.store.checksum_directory.side_effect = lambda directory: ({}, set())
        scanner.directory_checksums('/one')
        scanner.directory_checksums('/one')
        self.assertEqual(scanner.store.checksum_directory.call_count, 1)
        for index in range(40):
            scanner.directory_checksums('/' + str(index))
        self.assertEqual(len(scanner.checksum_cache), 32)
        self.assertNotIn('/one', scanner.checksum_cache)
