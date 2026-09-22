"""Incremental SQLite updates against existing and empty databases."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vfs import SQLiteDBAdapter


class SQLiteUpdateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = str(Path(self.directory.name) / 'cache.db')
        self.db = SQLiteDBAdapter(self.path)
        self.addCleanup(lambda: self.db.conn.close())

    def node(self, path):
        return self.db.conn.execute('SELECT * FROM nodes WHERE id = ?', (path,)).fetchone()

    def test_merge_repeat_and_reopen(self):
        self.db.build({'disk/a': {'old:3'}, 'disk/keep': {'old:3'}},
                      {'old:3': {'disk/a', 'disk/keep'}})
        self.db.conn.execute('CREATE TABLE sentinel (value TEXT)')
        connection = self.db.conn
        with patch.object(self.db, 'rebuild_db', side_effect=AssertionError('must not rebuild')):
            updates = {'disk/a': {'new:8'}, 'disk/new/deep/b': {'new:8'}}
            self.db.update(updates, {'new:8': set(updates)})
            self.db.update(updates)
        self.assertIs(self.db.conn, connection)
        self.assertEqual(self.node('')['size'], 19)
        self.assertEqual(self.node('/disk')['size'], 19)
        self.assertEqual(self.node('/disk/new')['size'], 8)
        self.assertEqual(self.node('/disk/new/deep')['size'], 8)
        self.assertEqual(self.node('/disk/keep')['size'], 3)
        self.assertEqual(self.db.get_hash_dups('old:3'), {'disk/keep'})
        self.assertEqual(self.db.get_hash_dups('new:8'), set(updates))
        self.assertEqual(self.db.conn.execute('SELECT COUNT(*) FROM hashes').fetchone()[0], 3)
        self.db.update({'disk/a': {'small:1'}})
        self.assertEqual(self.node('')['size'], 12)
        self.db.conn.close()
        self.db = SQLiteDBAdapter(self.path)
        self.assertEqual(self.node('')['size'], 12)
        self.assertEqual(self.node('/disk/a')['size'], 1)
        self.assertEqual(self.db.get_hash_dups('new:8'), {'disk/new/deep/b'})
        self.db.conn.execute('SELECT * FROM sentinel')

    def test_empty_database_and_zero_size(self):
        self.db.update({'a/b/c': {'empty:0'}, 'top': {'top:4'}})
        self.assertEqual(self.node('')['size'], 4)
        self.assertEqual(self.node('/a/b')['parent_id'], '/a')
        self.assertEqual(self.node('/a/b/c')['size'], 0)
        self.assertEqual(self.db.get_hash_dups('empty:0'), {'a/b/c'})
        self.db.update({})
        self.assertEqual(self.node('')['size'], 4)

    def test_directory_replaced_with_file(self):
        self.db.update({'disk/dir/deep/a': {'same:3'}, 'disk/keep': {'same:3'}})
        self.db.update({'disk/dir/new': {'new:5'}, 'disk/dir': {'file:2'}})
        self.assertFalse(self.node('/disk/dir')['is_dir'])
        self.assertEqual(self.node('/disk/dir')['size'], 2)
        for path in ('/disk/dir/deep', '/disk/dir/deep/a', '/disk/dir/new'):
            self.assertIsNone(self.node(path))
        self.assertEqual(self.node('')['size'], 5)
        self.assertEqual(self.node('/disk')['size'], 5)
        self.assertEqual(self.db.get_hash_dups('same:3'), {'disk/keep'})
        self.assertEqual(self.db.get_hash_dups('new:5'), set())
        self.assertEqual(self.db.get_hash_dups('file:2'), {'disk/dir'})
        self.db.update({'disk/dir': {'file:2'}})
        self.assertEqual(self.node('')['size'], 5)

    def test_parent_file_replaced_with_directory(self):
        self.db.update({'disk/a': {'old:3'}, 'disk/keep': {'old:3'}})
        self.db.update({'disk/a/deep/b': {'new:7'}})
        self.assertTrue(self.node('/disk/a')['is_dir'])
        self.assertEqual(self.node('/disk/a')['size'], 7)
        self.assertEqual(self.node('/disk/a')['info'], '{}')
        self.assertEqual(self.node('/disk/a/deep/b')['size'], 7)
        self.assertEqual(self.node('')['size'], 10)
        self.assertEqual(self.db.get_hash_dups('old:3'), {'disk/keep'})
        self.db.update({'disk/a': {'file:2'}, 'disk/a/child': {'child:5'}})
        self.assertTrue(self.node('/disk/a')['is_dir'])
        self.assertEqual(self.node('/disk/a')['size'], 5)
        self.assertEqual(self.node('/disk')['size'], 8)
        self.assertEqual(self.node('')['size'], 8)
        self.assertEqual(self.db.get_hash_dups('file:2'), set())
        self.assertEqual(self.db.get_hash_dups('new:7'), set())
        self.db.update({'disk/a/child': {'child:5'}})
        self.assertEqual(self.node('')['size'], 8)

    def test_invalid_input_rolls_back_replacement(self):
        self.db.update({'a/b': {'old:3'}})
        before = list(self.db.conn.execute('SELECT * FROM nodes ORDER BY id'))
        for invalid in ({'bad': {'broken'}}, {'': {'empty:0'}}):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    self.db.update({'a/b/c': {'new:7'}, **invalid})
                self.assertEqual(list(self.db.conn.execute('SELECT * FROM nodes ORDER BY id')), before)
                self.assertEqual(self.db.get_hash_dups('new:7'), set())
                self.assertEqual(self.db.get_hash_dups('old:3'), {'a/b'})


if __name__ == '__main__':
    unittest.main()
