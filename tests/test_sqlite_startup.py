"""A fresh SQLite catalog supports navigation before any log import."""
import tempfile
import unittest
from pathlib import Path

from vfs import VirtualFS


class SQLiteStartupTests(unittest.TestCase):
    def test_empty_catalog_startup_build_and_reopen(self):
        for existing in (False, True):
            for fragmented in (False, True):
                with self.subTest(existing=existing, fragmented=fragmented), tempfile.TemporaryDirectory() as directory:
                    filename = Path(directory) / 'drivevfs'
                    if existing:
                        filename.touch()
                    options = {'fragments': {'/disk': str(Path(directory) / 'disk.sqlite')},
                               'refragment': True} if fragmented else {}
                    fs = VirtualFS(None, 'sqlite', db_path=str(filename), **options)
                    try:
                        self.assertEqual(fs.pwd(), '/')
                        self.assertEqual(fs.list_nodes(), [])
                        fs.start_in_current_directory(directory)
                        self.assertEqual(fs.pwd(), directory)
                        fs.cwd = fs.db.get_root()
                        fs.db.rebuild_db()
                        self.assertIsNotNone(fs.db.get_root())
                        fs.db.build({'disk/file': {'digest:7'}})
                        self.assertEqual(fs.db.get_root().size, 7)
                    finally:
                        fs.db.conn.close()
                    fs = VirtualFS(None, 'sqlite', db_path=str(filename))
                    try:
                        self.assertEqual(fs.db.get_root().size, 7)
                        self.assertIsNotNone(fs.get_from_path('/disk/file'))
                    finally:
                        fs.db.conn.close()

    def test_existing_schema_without_root_is_initialized(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = str(Path(directory) / 'drivevfs')
            fs = VirtualFS(None, 'sqlite', db_path=filename)
            fs.db.conn.execute("DELETE FROM nodes WHERE id = ''")
            fs.db.conn.commit()
            fs.db.conn.close()
            fs = VirtualFS(None, 'sqlite', db_path=filename)
            try:
                self.assertEqual(fs.pwd(), '/')
                self.assertEqual(fs.list_nodes(), [])
            finally:
                fs.db.conn.close()
