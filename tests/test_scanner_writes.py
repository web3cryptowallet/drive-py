"""Unchanged scanner discoveries must not rewrite persisted records."""
# IMPORT TEST SCANNER WRITES DEPENDENCIES [
from pathlib import Path
from queue import Queue
from threading import Event
from types import SimpleNamespace
import tempfile
import unittest

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
