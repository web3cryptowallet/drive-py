"""SQLite log loading without accumulating parsed logs."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('drive_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class LoadLiteTests(unittest.TestCase):
    def test_stream_merge_and_rebuild(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            logs = [root / 'first.sh', root / 'second.sh']
            logs[0].write_text('# files [\nMD5 old disk/a 3\nMD5 keep disk/keep 2\n# files ]\n')
            logs[1].write_text('# files [\nMD5 new disk/a 7\nMD5 other disk/deep/b 5\n# files ]\n')
            db_path = str(root / 'cache.db')
            original = tui.load_log
            calls = []
            def check_load(context, file):
                self.assertTrue(all(not value for value in context.values()))
                if calls:
                    # Previous log was committed before parsing this one.
                    import sqlite3
                    with sqlite3.connect(db_path) as conn:
                        self.assertEqual(conn.execute("SELECT size FROM nodes WHERE id='/disk/a'").fetchone()[0], 3)
                calls.append(file)
                original(context, file)
            with patch.object(tui, 'load_log', side_effect=check_load):
                fs = tui.load_lite(iter(logs), rebuild_db=True, db_path=db_path)
            try:
                self.assertEqual(fs.get_cwd().size, 14)
                self.assertEqual(fs.get_from_path('/disk/a').size, 7)
                self.assertEqual(fs.get_hash_dups('MD5:old:3'), set())
                self.assertEqual(fs.get_from_path('/disk/deep/b').size, 5)
                fs.enter('disk')
                fs.update({'files': {'disk/a': {'MD5:small:1'}}})
                self.assertEqual(fs.pwd(), '/disk')
                self.assertEqual(fs.get_cwd().size, 8)
            finally:
                fs.db.conn.close()
            fs = tui.load_lite([logs[1]], db_path=db_path)
            try:
                self.assertIsNotNone(fs.get_from_path('/disk/keep'))
            finally:
                fs.db.conn.close()
            fs = tui.load_lite([logs[1]], rebuild_db=True, db_path=db_path)
            try:
                self.assertIsNone(fs.get_from_path('/disk/keep'))
                self.assertEqual(fs.get_cwd().size, 12)
            finally:
                fs.db.conn.close()
