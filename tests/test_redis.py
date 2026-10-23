"""Run the SQLite navigation contract against an isolated real Redis server.

Requires the redis Python package and redis-server on PATH (or REDIS_SERVER).
The server uses a temporary Unix socket, disables persistence, and never connects
to an existing Redis database.
"""

# IMPORT TEST REDIS DEPENDENCIES [
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import vfs
from vfs.adapter.redis import redis
import test_vfs
# IMPORT TEST REDIS DEPENDENCIES ]
# VERIFY REDIS BEHAVIOR [
class RedisTests(unittest.TestCase):
    # UPDATE UP CLASS [
    @classmethod
    def setUpClass(cls):
        executable = os.environ.get('REDIS_SERVER') or shutil.which('redis-server')
        if redis is None or not executable:
            raise unittest.SkipTest('Requires redis Python package and redis-server (or REDIS_SERVER)')
        directory = tempfile.TemporaryDirectory(prefix='vfs-redis-')
        cls.addClassCleanup(directory.cleanup)
        socket = str(Path(directory.name) / 'redis.sock')
        log = open(Path(directory.name) / 'redis.log', 'w+')
        cls.addClassCleanup(log.close)
        server = subprocess.Popen(
            [executable, '--port', '0', '--unixsocket', socket,
             '--unixsocketperm', '700', '--save', '', '--appendonly', 'no'],
            stdout=log, stderr=subprocess.STDOUT,
        )

        # STOP REDIS TESTS [
        def stop():
            if server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()
        # STOP REDIS TESTS ]
        cls.addClassCleanup(stop)
        cls.client = redis.Redis(unix_socket_path=socket, decode_responses=True)
        cls.addClassCleanup(cls.client.close)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                if cls.client.ping():
                    break
            except redis.ConnectionError:
                pass
            if server.poll() is not None:
                break
            time.sleep(0.02)
        else:
            raise RuntimeError('Test Redis did not become ready within five seconds')
        if server.poll() is not None:
            log.seek(0)
            raise RuntimeError(f'Test Redis exited: {log.read()}')
    # UPDATE UP CLASS ]
    # PREPARE TEST FIXTURES FOR REDIS TESTS [
    def setUp(self):
        # Only the private server started above is ever cleared.
        self.client.flushdb()
        self.addCleanup(self.client.flushdb)
        self.factory = patch('vfs.adapter.redis.redis.Redis', return_value=self.client)
        self.factory.start()
        self.addCleanup(self.factory.stop)
        test_vfs.VirtualFSTests.setUp(self)
    # PREPARE TEST FIXTURES FOR REDIS TESTS ]
    # VERIFY NAVIGATION AND REOPEN [
    def test_navigation_and_reopen(self):
        fs = vfs.VirtualFS(self.data, db_type='redis', rebuild_db=True)
        test_vfs.VirtualFSTests.check_navigation(self, fs)
        reopened = vfs.VirtualFS({}, db_type='redis')
        self.assertIsNot(reopened.db, fs.db)
        test_vfs.VirtualFSTests.check_navigation(self, reopened)
    # VERIFY NAVIGATION AND REOPEN ]
    # VERIFY TREE MATCHES SQLITE [
    def test_tree_matches_sqlite(self):
        with tempfile.TemporaryDirectory() as directory:
            sql = vfs.VirtualFS(self.data, db_type='sqlite', rebuild_db=True,
                                db_path=str(Path(directory) / 'cache.db'))
            self.addCleanup(sql.db.conn.close)
            actual = vfs.VirtualFS(self.data, db_type='redis', rebuild_db=True)

            # SNAPSHOT FOR TEST TREE MATCHES SQLITE [
            def snapshot(db, node):
                return (vars(node), [snapshot(db, child) for child in
                        sorted(db.get_children(node), key=lambda child: child.id)])
            # SNAPSHOT FOR TEST TREE MATCHES SQLITE ]

            self.assertEqual(snapshot(actual.db, actual.db.get_root()),
                             snapshot(sql.db, sql.db.get_root()))
            for hash_id in (*self.data['hashes'], 'missing:1'):
                self.assertEqual(actual.get_hash_dups(hash_id), sql.get_hash_dups(hash_id))
    # VERIFY TREE MATCHES SQLITE ]
    # VERIFY SCANNED FILE INSERT IS INDEXED AND IDEMPOTENT [
    def test_scanned_file_insert_is_indexed_and_idempotent(self):
        fs = vfs.VirtualFS({'files': {}, 'hashes': {}}, db_type='redis', rebuild_db=True)
        self.assertTrue(fs.db.add_scanned_file('/new/dir/file', 'md5:abc', 3))
        node = fs.get_from_path('/new/dir/file')
        self.assertEqual(node.info['hashinfo'], 'md5:abc:3')
        self.assertEqual(fs.db.get_root().size, 3)
        self.assertEqual(fs.get_hash_dups('md5:abc:3'), {'/new/dir/file'})
        self.assertFalse(fs.db.add_scanned_file('/new/dir/file', 'md5:changed', 5))
        self.assertEqual(fs.db.get_root().size, 3)
        self.assertEqual(fs.get_from_path('/new/dir/file').info['hash'], 'md5:abc')
    # VERIFY SCANNED FILE INSERT IS INDEXED AND IDEMPOTENT ]
    # VERIFY EMPTY TREE [
    def test_empty_tree(self):
        fs = vfs.VirtualFS({'files': {}, 'hashes': {}}, db_type='redis', rebuild_db=True)
        self.assertEqual(fs.pwd(), '/')
        self.assertEqual(fs.get_cwd().size, 0)
        self.assertEqual(fs.listdir(), [])
        self.assertIsNone(fs.db.get_parent(fs.get_cwd()))
        self.assertIsNone(fs.get_from_path('/missing'))
        self.assertEqual(fs.get_hash_dups('missing:0'), set())
    # VERIFY EMPTY TREE ]
# VERIFY REDIS BEHAVIOR ]
# RUN TEST REDIS ENTRY POINT [
if __name__ == '__main__':
    unittest.main()
# RUN TEST REDIS ENTRY POINT ]
