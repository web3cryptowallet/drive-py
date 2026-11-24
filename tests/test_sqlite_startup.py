"""A fresh SQLite catalog supports navigation before any log import."""
import tempfile
import sqlite3
import unittest
from pathlib import Path

from vfs import VirtualFS


class SQLiteStartupTests(unittest.TestCase):
    def test_navigation_commit_with_active_scanner_reader(self):
        from vfs.scanner import ScanStore

        with tempfile.TemporaryDirectory() as directory:
            filename = str(Path(directory) / 'drivevfs')
            fs = VirtualFS(None, 'sqlite', db_path=filename)
            reader = sqlite3.connect(filename)
            try:
                store = ScanStore(fs.db)
                store.put('entry', '/one', {'size': 1})
                store.put('entry', '/two', {'size': 2})
                # Keep a partially consumed scanner query alive through commit.
                cursor = reader.execute('SELECT * FROM scan_state')
                self.assertIsNotNone(cursor.fetchone())
                fs.db.conn.execute('PRAGMA busy_timeout=0')
                location = {'directory': directory, 'catalog_root': False}
                store.put('ui', 'last_directory', location)
                self.assertFalse(fs.db.conn.in_transaction)
                self.assertIsNotNone(cursor.fetchone())
                cursor.close()
            finally:
                reader.close()
                fs.db.conn.close()
            reopened = VirtualFS(None, 'sqlite', db_path=filename)
            try:
                self.assertEqual(ScanStore(reopened.db).get('ui', 'last_directory'), location)
            finally:
                reopened.db.conn.close()

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
