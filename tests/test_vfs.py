"""Regression coverage for the public VFS package and its storage adapters."""

import tempfile
import unittest
from pathlib import Path

import vfs
from vfs import paths


class VirtualFSTests(unittest.TestCase):
    def setUp(self):
        self.data = {
            'files': {
                'disk/z.txt': {'same:3'},
                'disk/folder/a.txt': {'same:3'},
                'disk/empty.txt': {'empty:0'},
            },
            'hashes': {
                'same:3': {'disk/z.txt', 'disk/folder/a.txt'},
                'empty:0': {'disk/empty.txt'},
            },
        }

    def check_navigation(self, fs):
        self.assertEqual(fs.pwd(), '/')
        self.assertEqual(fs.listdir(), [('disk', True)])
        fs.enter('disk')
        self.assertEqual(fs.pwd(), '/disk')
        self.assertEqual(fs.get_cwd().size, 6)
        self.assertEqual(fs.listdir(), [
            ('..', True), ('folder', True), ('empty.txt', False), ('z.txt', False),
        ])
        fs.enter('z.txt')
        self.assertEqual(fs.pwd(), '/disk')
        fs.enter('missing')
        self.assertEqual(fs.pwd(), '/disk')
        node = fs.get_from_path('/disk/folder/a.txt')
        self.assertEqual(node.size, 3)
        self.assertEqual(node.info['hashinfo'], 'same:3')
        self.assertEqual(set(fs.get_hash_dups('same:3')), self.data['hashes']['same:3'])
        self.assertIsNone(fs.get_from_path('/disk/missing'))
        fs.enter('folder')
        self.assertEqual(fs.get('..').id, '/disk')
        fs.enter('..')
        fs.enter('..')
        fs.enter('..')
        self.assertEqual(fs.pwd(), '/')

    def test_memory_navigation(self):
        self.check_navigation(vfs.VirtualFS(self.data))

    def test_sqlite_navigation_and_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = str(Path(directory) / 'vfs.db')
            fs = vfs.VirtualFS(self.data, db_type='sqlite', rebuild_db=True, db_path=db_path)
            try:
                self.check_navigation(fs)
            finally:
                fs.db.conn.close()
            fs = vfs.VirtualFS({}, db_type='sqlite', db_path=db_path)
            try:
                self.check_navigation(fs)
            finally:
                fs.db.conn.close()

    def test_shared_drive_mappings_and_local_metadata(self):
        self.assertIs(vfs.aliases, paths.aliases)
        self.assertIs(vfs.prefixes, paths.prefixes)
        self.assertIs(vfs.disabled_prefixes, paths.disabled_prefixes)
        old_aliases, old_prefixes = dict(vfs.aliases), dict(vfs.prefixes)
        try:
            with tempfile.TemporaryDirectory() as directory:
                Path(directory, 'item').write_bytes(b'abc')
                vfs.aliases['mapped'] = directory
                vfs.prefixes['original'] = {'local': directory, 'alias': 'mapped'}
                self.assertEqual(vfs.path_update_prefix('original/item'), 'mapped/item')
                self.assertEqual(vfs.get_real_path('/mapped/item'), directory + '/item')
                self.assertEqual(vfs.get_stat_info('/mapped/item')['size'], 3)
                self.assertEqual(vfs.get_stat_info('/mapped/missing'), {'exists': False})
                fs = vfs.VirtualFS({'files': {'original/item': {'hash:3'}}, 'hashes': {}})
                self.assertEqual(fs.listdir(), [('mapped', True)])
                self.assertEqual(fs.get_full_info(fs.get_from_path('/mapped/item'), True)['size'], 3)
        finally:
            vfs.aliases.clear()
            vfs.aliases.update(old_aliases)
            vfs.prefixes.clear()
            vfs.prefixes.update(old_prefixes)

    def test_public_exports(self):
        for name in vfs.__all__:
            self.assertIsNotNone(getattr(vfs, name))
        with self.assertRaisesRegex(ValueError, 'Unknown db_type'):
            vfs.VirtualFS(self.data, db_type='unsupported')


if __name__ == '__main__':
    unittest.main()
