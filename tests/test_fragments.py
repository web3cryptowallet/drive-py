# IMPORT TEST FRAGMENTS DEPENDENCIES [
import json
from pathlib import Path
import tempfile
import unittest

from drive import load_log
from vfs.adapter.sqlite import SQLiteDBAdapter
from vfs.adapter.fragmented import FragmentedSQLiteDBAdapter
from vfs.export import export_livelog
from vfs import VirtualFS
# IMPORT TEST FRAGMENTS DEPENDENCIES ]
# VERIFY FRAGMENT BEHAVIOR [
class FragmentTests(unittest.TestCase):
    # VERIFY LAZY NESTED MIGRATION REOPEN UPDATE EXPORT [
    def test_lazy_nested_migration_reopen_update_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            filename = str(root / 'catalog')
            db = SQLiteDBAdapter(filename)
            db.update({'/disk/a': {'MD5:same:4'}, '/disk/sub/b': {'MD5:same:4'},
                       '/other/c': {'MD5:other:2'}, '/diskish/d': {'MD5:other:2'}})
            db.conn.execute("UPDATE nodes SET info=json_set(info, '$.custom', 42) WHERE id='/disk/a'")
            db.conn.commit()
            db.conn.close()
            routes = {'/disk': str(root / 'disk.db')}
            db = FragmentedSQLiteDBAdapter(filename, routes)
            self.assertEqual(db.routes, {})
            db.conn.close()
            db = FragmentedSQLiteDBAdapter(filename, routes, refragment=True)
            self.assertEqual(db.stores[''].conn.execute('SELECT count(*) FROM nodes WHERE is_dir=0').fetchone()[0], 4)
            disk = db.get_child(db.get_root(), 'disk')
            self.assertEqual({n.name for n in db.get_children(disk)}, {'a', 'sub'})
            self.assertIsNone(db.stores[''].conn.execute("SELECT * FROM nodes WHERE id='/disk/a'").fetchone())
            self.assertIsNotNone(db.stores[''].conn.execute("SELECT * FROM nodes WHERE id='/disk/sub/b'").fetchone())
            self.assertEqual(db.get_child(disk, 'a').info['custom'], 42)
            self.assertEqual(db.get_root().size, 12)
            db.conn.close()
            routes['/disk/sub'] = str(root / 'sub.db')
            db = FragmentedSQLiteDBAdapter(filename, routes, refragment=True)
            db.refragment(batch_size=1)
            self.assertEqual(db.stores['/disk/sub'].get_hash_dups('MD5:same:4'), {'/disk/sub/b'})
            self.assertEqual(db.get_hash_dups('MD5:same:4'), {'/disk/a', '/disk/sub/b'})
            self.assertEqual(db.get_root().size, 12)
            db.update({'/disk/sub/b': {'MD5:new:9'}})
            self.assertEqual(db.get_root().size, 17)
            self.assertTrue(db.add_scanned_file('/disk/sub/new', 'abcd', 3))
            self.assertFalse(db.add_scanned_file('/disk/sub/new', 'abcd', 3))
            export_livelog(db, root / 'export')
            manifest = json.loads((root / 'export/db-paths.json').read_text())
            self.assertEqual(len(manifest), 3)
            data = {'hashes': {}, 'files': {}}
            for path in (root / 'export').rglob('llog-llogfiles.sh'):
                load_log(data, str(path))
            self.assertEqual(len(data['files']), 5)
            db.conn.close()
            fs = VirtualFS(None, 'sqlite', db_path=filename)
            self.assertEqual(fs.db.get_root().size, 20)
            fs.db.conn.close()
    # VERIFY LAZY NESTED MIGRATION REOPEN UPDATE EXPORT ]
    # VERIFY TRANSACTION ROLLBACK AND BOUNDARY [
    def test_transaction_rollback_and_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = FragmentedSQLiteDBAdapter(str(root / 'main'), {'/disk': str(root / 'disk')}, True)
            db.update({'/disk/a': {'MD5:a:2'}, '/diskish/a': {'MD5:a:2'}})
            with self.assertRaises(ValueError):
                db.update({'/other/a': {'MD5:a:7'}, '/disk/b': {'MD5:b:-1'}})
            self.assertEqual(db.get_root().size, 4)
            self.assertEqual(db.owner('/diskish/a'), '')
            self.assertEqual(db.owner('/disk/a'), '/disk')
            db.conn.close()
    # VERIFY TRANSACTION ROLLBACK AND BOUNDARY ]
    # VERIFY STRUCTURAL REPLACEMENTS CROSS FRAGMENTS AND NESTED ROLLBACK [
    def test_structural_replacements_cross_fragments_and_nested_rollback(self):
        from vfs.scanner import ScanStore
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = FragmentedSQLiteDBAdapter(str(root / 'main'), {'/disk/sub': str(root / 'sub')}, True)
            db.update({'/disk/sub/a': {'MD5:a:5'}, '/disk/b': {'MD5:b:3'}})
            db.update({'/disk': {'MD5:file:2'}})
            self.assertEqual(db.get_root().size, 2)
            self.assertEqual(db.get_hash_dups('MD5:a:5'), set())
            db.update({'/disk/sub/c': {'MD5:c:7'}})
            self.assertEqual(db.get_root().size, 7)
            self.assertEqual(db.get_hash_dups('MD5:file:2'), set())
            scan_store = ScanStore(db)
            with self.assertRaisesRegex(RuntimeError, 'abort'):
                with db.write_transaction():
                    scan_store.put('checksum', '/disk/sub/new', {'size': 3})
                    db.add_scanned_file('/disk/sub/new', 'MD5:new', 3)
                    raise RuntimeError('abort')
            self.assertEqual(db.get_root().size, 7)
            self.assertIsNone(ScanStore(db).get('checksum', '/disk/sub/new'))
            self.assertEqual(db.get_hash_dups('MD5:new:3'), set())
            db.conn.close()
    # VERIFY STRUCTURAL REPLACEMENTS CROSS FRAGMENTS AND NESTED ROLLBACK ]
    # VERIFY FAILED LAZY BATCH ROLLS BACK AND RESUMES [
    def test_failed_lazy_batch_rolls_back_and_resumes(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            filename = str(root / 'main')
            original = SQLiteDBAdapter(filename)
            original.update({'/disk/a': {'MD5:a:5'}, '/disk/b': {'MD5:b:3'}})
            original.conn.close()
            db = FragmentedSQLiteDBAdapter(filename, {'/disk': str(root / 'disk')}, True)
            destination = db.stores['/disk'].conn
            execute = destination.execute

            # FAIL FOR TEST FAILED LAZY BATCH ROLLS BACK AND RESUMES [
            def fail(sql, params=()):
                if sql.startswith('INSERT INTO nodes') and params[0] == '/disk/b':
                    raise RuntimeError('interrupted')
                return execute(sql, params)
            # FAIL FOR TEST FAILED LAZY BATCH ROLLS BACK AND RESUMES ]

            with patch.object(destination, 'execute', side_effect=fail):
                with self.assertRaises(RuntimeError):
                    db.refragment(batch_size=1)
            self.assertEqual(db.get_root().size, 8)
            self.assertEqual(db.stores['/disk'].get_hash_dups('MD5:a:5'), {'/disk/a'})
            self.assertEqual(db.stores[''].get_hash_dups('MD5:b:3'), {'/disk/b'})
            db.conn.close()
            db = FragmentedSQLiteDBAdapter(filename)
            db.refragment(batch_size=1)
            self.assertEqual(db.get_root().size, 8)
            self.assertEqual(db.stores['/disk'].get_hash_dups('MD5:b:3'), {'/disk/b'})
            db.conn.close()
    # VERIFY FAILED LAZY BATCH ROLLS BACK AND RESUMES ]
    # VERIFY MISSING FRAGMENT AND EXPORT ERRORS DO NOT HIDE DATA [
    def test_missing_fragment_and_export_errors_do_not_hide_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            filename = str(root / 'main')
            db = FragmentedSQLiteDBAdapter(filename, {'/disk': str(root / 'disk')}, True)
            db.add_scanned_file('/disk/bad\nname', 'MD5:abc', 3)
            with self.assertRaises(ValueError):
                export_livelog(db, root / 'export')
            self.assertFalse((root / 'export').exists())
            db.conn.close()
            (root / 'disk').unlink()
            with self.assertRaises(FileNotFoundError):
                FragmentedSQLiteDBAdapter(filename)
    # VERIFY MISSING FRAGMENT AND EXPORT ERRORS DO NOT HIDE DATA ]
    # VERIFY CLI CONFIG ACTIVATION AND HEADLESS EXPORT [
    def test_cli_config_activation_and_headless_export(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'config.sh').write_text('# SETTINGS JSON [\n' + json.dumps(
                {'db_fragments': {'/disk': 'fragments/disk.sqlite'}}) + '\n# SETTINGS JSON ]\n')
            command = [sys.executable, str(Path(__file__).resolve().parents[1] / 'drive-tui.py'), '-c', 'sqlite']
            result = subprocess.run(command + ['-refragment', '-export-livelog', 'export'],
                                    cwd=root, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((root / 'fragments/disk.sqlite').is_file())
            self.assertEqual(len(json.loads((root / 'export/db-paths.json').read_text())), 2)
    # VERIFY CLI CONFIG ACTIVATION AND HEADLESS EXPORT ]
    # VERIFY SCANNER WORKER REOPENS ALL FRAGMENTS [
    def test_scanner_worker_reopens_all_fragments(self):
        from queue import Queue
        from threading import Event
        from unittest.mock import patch
        from vfs.scanner import DriveScanner
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = FragmentedSQLiteDBAdapter(str(root / 'main'), {'/disk': str(root / 'disk')}, True)
            stop = Event()
            scanner = DriveScanner(db, '/disk', Queue(), stop)
            checked = []

            # ONCE FOR TEST SCANNER WORKER REOPENS ALL FRAGMENTS [
            def once(worker):
                self.assertIsInstance(worker, FragmentedSQLiteDBAdapter)
                worker.add_scanned_file('/disk/new', 'MD5:abc', 3)
                checked.append(worker.routes)
                stop.set()
            # ONCE FOR TEST SCANNER WORKER REOPENS ALL FRAGMENTS ]

            with patch.object(scanner, 'scan_once', side_effect=once):
                scanner.run()
            self.assertEqual(len(checked), 1)
            self.assertEqual(db.get_root().size, 3)
            self.assertEqual(db.stores['/disk'].get_hash_dups('MD5:abc:3'), {'/disk/new'})
            db.conn.close()
    # VERIFY SCANNER WORKER REOPENS ALL FRAGMENTS ]
# VERIFY FRAGMENT BEHAVIOR ]
