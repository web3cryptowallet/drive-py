"""Unchanged scanner discoveries must not rewrite persisted records."""
# IMPORT TEST SCANNER WRITES DEPENDENCIES [
from pathlib import Path
from queue import Queue
from threading import Event
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from vfs import VirtualFS
from vfs.scanner import DriveScanner, ScanStore
# IMPORT TEST SCANNER WRITES DEPENDENCIES ]
# MANAGE FAKE REDIS [
class FakeRedis:
    # INITIALIZE FAKE REDIS [
    def __init__(self):
        self.values = {}
        self.writes = 0
    # INITIALIZE FAKE REDIS ]
    # READ A FAKE REDIS HASH VALUE [
    def hget(self, name, key):
        value = self.values.get((name, key))
        return value.encode() if value is not None else None
    # READ A FAKE REDIS HASH VALUE ]
    # WRITE A FAKE REDIS HASH VALUE [
    def hset(self, name, key, value):
        self.values[name, key] = value
        self.writes += 1
    # WRITE A FAKE REDIS HASH VALUE ]
# MANAGE FAKE REDIS ]
# VERIFY SCANNER WRITE BEHAVIOR [
class ScannerWriteTests(unittest.TestCase):
    def test_lite_batches_commits_and_flushes_on_stop(self):
        for cancel in (False, True):
            with self.subTest(cancel=cancel), tempfile.TemporaryDirectory() as directory:
                disk = Path(directory) / 'disk'
                disk.mkdir()
                for index in range(130):
                    (disk / str(index)).write_text('abc')
                fs = VirtualFS(None, 'sqlite', db_path=str(Path(directory) / 'cache.sqlite'))
                try:
                    scanner = DriveScanner(fs.db, str(disk), Queue(), Event())
                    statements = []
                    fs.db.conn.set_trace_callback(statements.append)
                    publish = scanner.publish

                    def publish_and_stop(*args, **kwargs):
                        publish(*args, **kwargs)
                        if cancel and scanner.paths == 5:
                            scanner.stop.set()

                    scanner.publish = publish_and_stop
                    with patch('vfs.scanner.time.monotonic', return_value=100.):
                        scanner.scan_once(fs.db)
                    commits = sum(sql == 'COMMIT' for sql in statements)
                    self.assertLessEqual(commits, 5, statements)
                    self.assertEqual(scanner.paths, 5 if cancel else 131)
                    self.assertFalse(scanner.pending_discoveries)
                    self.assertEqual(fs.db.conn.execute('SELECT COUNT(*) FROM scan_paths').fetchone()[0], scanner.paths)
                    self.assertEqual(fs.db.conn.execute("SELECT COUNT(*) FROM scan_state WHERE kind='entry'").fetchone()[0], scanner.paths)
                    self.assertFalse(fs.db.conn.in_transaction)
                finally:
                    fs.db.conn.close()

    def test_lite_reuses_directory_catalog_and_batches_record_lookups(self):
        with tempfile.TemporaryDirectory() as directory:
            disk = Path(directory) / 'disk'
            disk.mkdir()
            for index in range(512):
                (disk / str(index)).write_text('abc')
            fs = VirtualFS(None, 'sqlite', db_path=str(Path(directory) / 'cache.sqlite'))
            try:
                statements = []
                fs.db.conn.set_trace_callback(statements.append)
                scanner = DriveScanner(fs.db, str(disk), Queue(), Event())
                with patch.object(fs.db, 'get_root', wraps=fs.db.get_root) as root_lookup:
                    scanner.scan_once(fs.db)
                # Missing catalog parents are resolved once, not for each file.
                self.assertEqual(root_lookup.call_count, 1)
                self.assertEqual(scanner.paths, 513)
                selects = [sql for sql in statements if sql.startswith('SELECT')]
                self.assertLess(len(selects), 550)
                # A second pass must still compare/reuse saved states without
                # rewriting unchanged entries or path mappings.
                statements.clear()
                scanner.scan_once(fs.db)
                self.assertFalse(any(sql.startswith('INSERT') and
                    ('scan_paths' in sql or "'entry'" in sql) for sql in statements))
            finally:
                fs.db.conn.close()

    # VERIFY SQLITE STORE SKIPS EQUAL AND LEGACY JSON AFTER REOPEN [
    def test_sqlite_store_skips_equal_and_legacy_json_after_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'cache.sqlite')
            fs = VirtualFS(None, 'sqlite', db_path=path)
            store = ScanStore(fs.db)
            value = {'size': 3, 'state': 'unknown'}
            self.assertTrue(store.put('entry', '/file', value))
            before = fs.db.conn.total_changes
            self.assertFalse(store.put('entry', '/file', dict(reversed(list(value.items())))))
            self.assertEqual(fs.db.conn.total_changes, before)
            with fs.db.conn:
                fs.db.conn.execute("UPDATE scan_state SET value=?", ('{ "state": "unknown", "size": 3 }',))
            fs.db.conn.close()
            fs = VirtualFS(None, 'sqlite', db_path=path)
            try:
                store = ScanStore(fs.db)
                self.assertFalse(store.put('entry', '/file', value))
                self.assertEqual(fs.db.conn.total_changes, 0)
                self.assertTrue(store.put('entry', '/file', {**value, 'size': 4}))
                self.assertEqual(fs.db.conn.total_changes, 1)
                self.assertEqual(store.get('entry', '/file')['size'], 4)
            finally:
                fs.db.conn.close()
    # VERIFY SQLITE STORE SKIPS EQUAL AND LEGACY JSON AFTER REOPEN ]
    # VERIFY LITE REOPEN SKIPS EXISTING PATHS AND ENTRIES BUT EMITS EVENTS [
    def test_lite_reopen_skips_existing_paths_and_entries_but_emits_events(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            disk = root / 'disk'
            disk.mkdir()
            file = disk / 'file'
            file.write_text('abc')
            database = str(root / 'cache.sqlite')
            fs = VirtualFS(None, 'sqlite', db_path=database)
            scanner = DriveScanner(fs.db, str(disk), Queue(), Event())
            scanner.scan_once(fs.db)
            fs.db.conn.close()
            fs = VirtualFS(None, 'sqlite', db_path=database)
            try:
                statements = []
                fs.db.conn.set_trace_callback(statements.append)
                events = Queue()
                scanner = DriveScanner(fs.db, str(disk), events, Event())
                scanner.scan_once(fs.db)
                writes = [sql for sql in statements if sql.lstrip().upper().startswith(('INSERT', 'UPDATE', 'REPLACE', 'DELETE'))]
                self.assertFalse(any('scan_paths' in sql for sql in writes), writes)
                self.assertFalse(any("'entry'" in sql for sql in writes), writes)
                self.assertEqual(scanner.paths, 2)
                self.assertEqual(sum(kind == 'entry' for kind, _ in events.queue), 2)
                statements.clear()
                file.write_text('abcd')
                scanner.scan_once(fs.db)
                entry_writes = [sql for sql in statements if sql.startswith('INSERT') and "'entry'" in sql]
                self.assertEqual(len(entry_writes), 1, entry_writes)
                self.assertEqual(ScanStore(fs.db).get('entry', str(file))['size'], 4)
            finally:
                fs.db.conn.close()
    # VERIFY LITE REOPEN SKIPS EXISTING PATHS AND ENTRIES BUT EMITS EVENTS ]
    # VERIFY MEMORY AND REDIS SKIP EQUAL NORMALIZED VALUES [
    def test_memory_and_redis_skip_equal_normalized_values(self):
        memory = VirtualFS({'files': {}}).db
        redis = SimpleNamespace(client=FakeRedis())
        for db in (memory, redis):
            with self.subTest(backend=type(db).__name__):
                store = ScanStore(db)
                self.assertTrue(store.put('map', '/', {'modes': (True, False, False)}))
                self.assertFalse(store.put('map', '/', {'modes': [True, False, False]}))
                self.assertTrue(store.put('map', '/', {'modes': [False, False, True]}))
                self.assertEqual(store.get('map', '/')['modes'], [False, False, True])
        self.assertEqual(redis.client.writes, 2)
    # VERIFY MEMORY AND REDIS SKIP EQUAL NORMALIZED VALUES ]
# VERIFY SCANNER WRITE BEHAVIOR ]
