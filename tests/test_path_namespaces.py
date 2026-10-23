"""Source-relative imports must not collapse into absolute disk paths."""
# VERIFY CATALOG ORIGINS AND LEGACY SOURCE MIGRATION [
import importlib.util
import json
from types import SimpleNamespace
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from vfs import VirtualFS, aliases
from vfs.paths import catalog_source_path, catalog_source_data, get_real_path
from vfs.path_migration import migrate_source_paths


class SourceNamespaceTests(unittest.TestCase):
    def test_startup_leaves_legacy_paths_for_explicit_cli(self):
        project = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location('migration_startup_tui', project / 'drive-tui.py')
        tui = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tui)
        with tempfile.TemporaryDirectory() as folder, patch.dict(aliases, {}, clear=True):
            filename = Path(folder) / 'legacy.db'
            fs = VirtualFS({'files': {'test0/a': {'hash:3'}},
                            'hashes': {'hash:3': {'test0/a'}}},
                           'sqlite', rebuild_db=True, db_path=str(filename))
            fs.db.conn.close()
            def factory(data, backend, **options):
                return VirtualFS(data, backend, db_path=str(filename), **options)
            with patch.object(tui, 'VirtualFS', side_effect=factory), patch(
                    'vfs.path_migration.migrate_source_paths', side_effect=AssertionError('startup migration')):
                fs = tui.load_vfs(SimpleNamespace(cache='sqlite', build=False, update=False, db=None))
                self.assertIsNotNone(fs.db.conn.execute("SELECT 1 FROM nodes WHERE id='/test0/a'").fetchone())
                fs.db.conn.close()
            self.assertFalse(Path(str(filename) + '.source-paths-backup.sqlite').exists())
            command = [sys.executable, str(project / 'migrate-paths.py'), str(filename), '--batch-size', '1']
            result = subprocess.run(command, cwd=folder, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Migrated 1 file records.', result.stdout)
            self.assertTrue(Path(str(filename) + '.source-paths-backup.sqlite').exists())
            result = subprocess.run(command, cwd=folder, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Migrated 0 file records.', result.stdout)
            missing = Path(folder) / 'missing.db'
            result = subprocess.run(command[:2] + [str(missing)], cwd=folder, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(missing.exists())

    def test_batched_migration_preserves_large_catalog_and_rolls_back_failure(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(aliases, {}, clear=True):
            fs = VirtualFS(None, 'sqlite', db_path=str(Path(folder) / 'catalog'))
            try:
                count = 1200
                fs.db.conn.execute("UPDATE nodes SET size=? WHERE id=''", (count,))
                fs.db.conn.execute("INSERT INTO nodes VALUES ('/test0','test0',1,?,'','{}')", (count,))
                fs.db.conn.executemany('INSERT INTO nodes VALUES (?,?,0,1,?,?)',
                    ((f'/test0/{i}', str(i), '/test0', json.dumps({'path': f'test0/{i}'})) for i in range(count)))
                fs.db.conn.executemany('INSERT INTO hashes VALUES (?,?)',
                                      (('same:1', f'test0/{i}') for i in range(count)))
                fs.db.conn.commit()
                original_execute = fs.db.conn
                class FailingConnection:
                    def __getattr__(self, name):
                        return getattr(original_execute, name)
                    def executemany(self, sql, rows):
                        original_execute.executemany(sql, rows)
                        raise OSError('simulated write failure')
                with patch.object(fs.db, 'conn', FailingConnection()):
                    # Supply the real transaction context so a failure in a batch rolls back.
                    with patch.object(fs.db, 'write_transaction', return_value=original_execute):
                        with self.assertRaisesRegex(OSError, 'simulated'):
                            migrate_source_paths(fs.db, batch_size=17)
                self.assertEqual(fs.db.conn.execute('SELECT count(*) FROM nodes WHERE is_dir=0').fetchone()[0], count)
                self.assertIsNotNone(fs.db.conn.execute("SELECT 1 FROM nodes WHERE id='/test0/0'").fetchone())
                Path(str(Path(folder) / 'catalog') + '.source-paths-backup.sqlite').unlink()
                self.assertEqual(migrate_source_paths(fs.db, batch_size=17), count)
                self.assertEqual(fs.db.get_root().size, count)
                self.assertEqual(len(fs.get_hash_dups('same:1')), count)
                self.assertEqual(migrate_source_paths(fs.db, batch_size=17), 0)
            finally:
                fs.db.conn.close()

    def test_origins_survive_both_adapters_and_reopen(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(aliases, {}, clear=True):
            data = catalog_source_data({'files': {'test0/a': {'hash:3'}, '/home/example/a': {'hash:3'}},
                                       'hashes': {'hash:3': {'test0/a', '/home/example/a'}}})
            self.assertEqual(set(data['files']), {'~:test0/a', '/home/example/a'})
            for backend in ('memory', 'sqlite'):
                options = {'db_path': str(Path(folder) / 'db')} if backend == 'sqlite' else {}
                fs = VirtualFS(data, backend, rebuild_db=True, **options)
                try:
                    for path in ('/~:/test0/a', '/home/example/a'):
                        node = fs.get_from_path(path)
                        self.assertIsNotNone(node)
                        self.assertEqual(node.info['path'], path[len('/~:/'):] if path.startswith('/~:') else path)
                    self.assertEqual(fs.get_full_info(fs.get_from_path('/~:/test0/a'))['dups'], ['/home/example/a'])
                    self.assertEqual(get_real_path('/~:/test0/a'), str(Path.cwd() / 'test0/a'))
                    self.assertEqual(get_real_path('/home/example/a'), '/home/example/a')
                finally:
                    if backend == 'sqlite': fs.db.conn.close()
                if backend == 'sqlite':
                    reopened = VirtualFS({}, 'sqlite', **options)
                    self.assertEqual(reopened.get_from_path('/~:/test0/a').info['path'], 'test0/a')
                    reopened.db.conn.close()
            self.assertEqual(catalog_source_path('~:test0/a'), 'test0/a')
            self.assertEqual(catalog_source_path('~:/.hidden/a'), '.hidden/a')

    def test_application_log_import_and_sqlite_update(self):
        spec = importlib.util.spec_from_file_location('namespace_import_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
        tui = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tui)
        with tempfile.TemporaryDirectory() as folder, patch.dict(aliases, {}, clear=True):
            log = Path(folder) / 'llog-llogfiles.sh'
            log.write_text('# files [\nMD5 abc "test0/a" 3\nMD5 abc "/home/example/a" 3\n# files ]\n')
            for backend in ('memory', 'sqlite'):
                filename = str(Path(folder) / 'catalog.sqlite')
                def factory(data, kind, **options):
                    if kind == 'sqlite': options['db_path'] = filename
                    return VirtualFS(data, kind, **options)
                # Memory uses a third positional build flag.
                def factory_compat(data, kind, build=False, **options):
                    options['rebuild_db'] = build
                    return factory(data, kind, **options)
                with patch.object(tui, 'VirtualFS', side_effect=factory_compat):
                    args = SimpleNamespace(cache=backend, build=False, update=backend == 'sqlite', db=[folder])
                    fs = tui.load_vfs(args)
                    try:
                        self.assertIsNotNone(fs.get_from_path('/~:/test0/a'))
                        self.assertEqual(fs.get_from_path('/home/example/a').info['path'], '/home/example/a')
                    finally:
                        if backend == 'sqlite': fs.db.conn.close()

    def test_legacy_migration_backups_counts_metadata_and_idempotence(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(aliases, {}, clear=True):
            filename = Path(folder) / 'legacy.db'
            fs = VirtualFS({'files': {'test0/a': {'hash:3'}, '/home/example/a': {'hash:3'}},
                            'hashes': {'hash:3': {'test0/a', '/home/example/a'}}},
                           'sqlite', rebuild_db=True, db_path=str(filename))
            try:
                fs.db.conn.execute("UPDATE nodes SET info=json_set(info, '$.custom', 42) WHERE id='/test0/a'")
                fs.db.conn.execute("UPDATE nodes SET info=json_set(info, '$.marker', 7) WHERE id='/test0'")
                fs.db.conn.execute("INSERT INTO nodes VALUES ('/test0/empty', 'empty', 1, 0, '/test0', '{}')")
                fs.db.conn.commit()
                self.assertGreater(migrate_source_paths(fs.db, batch_size=1), 0)
                self.assertEqual(migrate_source_paths(fs.db), 0)
                self.assertIsNone(fs.db.conn.execute("SELECT 1 FROM nodes WHERE id='/test0/a'").fetchone())
                self.assertEqual(fs.get_from_path('/~:/test0/a').info['custom'], 42)
                self.assertEqual(fs.get_from_path('/home/example/a').info['path'], '/home/example/a')
                self.assertEqual(fs.db.get_root().size, 6)
                self.assertEqual(fs.get_from_path('/~:').size, 3)
                self.assertEqual(fs.get_from_path('/~:/test0').info['marker'], 7)
                self.assertIsNotNone(fs.get_from_path('/~:/test0/empty'))
                backup = sqlite3.connect(str(filename) + '.source-paths-backup.sqlite')
                try:
                    self.assertIsNotNone(backup.execute("SELECT 1 FROM nodes WHERE id='/test0/a'").fetchone())
                finally: backup.close()
                fs.db.add_scanned_file('/~:/test0/new', 'new', 1)
                self.assertEqual(fs.get_from_path('/~:/test0/new').info['path'], 'test0/new')
                self.assertEqual(migrate_source_paths(fs.db), 0)
            finally: fs.db.conn.close()

    def test_fragment_migration_preserves_combined_root_and_backups(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(aliases, {}, clear=True):
            filename = Path(folder) / 'coordinator'
            fragment = Path(folder) / 'relative.sqlite'
            fs = VirtualFS(None, 'sqlite', db_path=str(filename),
                           fragments={'/test0': str(fragment)}, refragment=True)
            try:
                fs.update({'files': {'test0/a': {'hash:3'}}})
                self.assertGreater(migrate_source_paths(fs.db, batch_size=1), 0)
                self.assertEqual(fs.get_from_path('/~:/test0/a').size, 3)
                self.assertEqual(fs.db.get_root().size, 3)
                self.assertTrue(Path(str(fragment) + '.source-paths-backup.sqlite').is_file())
                self.assertEqual(migrate_source_paths(fs.db), 0)
            finally: fs.db.conn.close()

    def test_raw_relative_paths_resolve_against_each_run_directory(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(aliases, {}, clear=True):
            root = Path(folder)
            first, second = root / 'first', root / 'second'
            for directory, contents in ((first, 'one'), (second, 'second')):
                (directory / 'test0').mkdir(parents=True)
                (directory / 'test0/a').write_text(contents)
            absolute = root / 'absolute'
            absolute.write_text('fixed')
            filename = str(root / 'catalog')
            data = catalog_source_data({'files': {'test0/a': {'relative:3'}, str(absolute): {'global:5'}},
                                       'hashes': {'relative:3': {'test0/a'}, 'global:5': {str(absolute)}}})
            fs = VirtualFS(data, 'sqlite', rebuild_db=True, db_path=filename)
            fs.db.conn.close()
            for directory, size in ((first, 3), (second, 6)):
                with patch('os.getcwd', return_value=str(directory)):
                    uncataloged = VirtualFS({'files': {}})
                    self.assertEqual(uncataloged.get_from_path('test0/a').size, size)
                    fs = VirtualFS({}, 'sqlite', db_path=filename)
                    try:
                        node = fs.get_from_path('test0/a')
                        self.assertEqual(node.info['path'], 'test0/a')
                        self.assertEqual(fs.get_full_info(node)['size'], size)
                        self.assertEqual(fs.get_full_info(fs.get_from_path(str(absolute)))['size'], 5)
                        self.assertEqual(migrate_source_paths(fs.db), 0)
                        stored = {r[0] for r in fs.db.conn.execute('SELECT path FROM hashes')}
                        self.assertEqual(stored, {'test0/a', str(absolute)})
                    finally: fs.db.conn.close()

    def test_relative_absolute_hash_updates_remain_separate(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(aliases, {}, clear=True):
            data = catalog_source_data({'files': {'test0/a': {'same:3'}, '/test0/a': {'same:3'}},
                                       'hashes': {'same:3': {'test0/a', '/test0/a'}}})
            fs = VirtualFS(data, 'sqlite', rebuild_db=True, db_path=str(Path(folder) / 'db'))
            try:
                self.assertEqual(migrate_source_paths(fs.db), 0)
                self.assertEqual(fs.get_full_info(fs.get_from_path('test0/a'))['dups'], ['/test0/a'])
                fs.update(catalog_source_data({'files': {'test0/a': {'new:4'}}}))
                self.assertEqual(fs.get_hash_dups('same:3'), {'/test0/a'})
                self.assertEqual(fs.get_hash_dups('new:4'), {'test0/a'})
                fs.update(catalog_source_data({'files': {'test0': {'replacement:1'}}}))
                self.assertEqual(fs.get_hash_dups('same:3'), {'/test0/a'})
                self.assertEqual(fs.get_hash_dups('new:4'), set())
            finally: fs.db.conn.close()

    def test_raw_hash_paths_survive_lazy_fragment_moves(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(aliases, {}, clear=True):
            filename = str(Path(folder) / 'db')
            fragment = str(Path(folder) / 'relative')
            fs = VirtualFS(None, 'sqlite', db_path=filename)
            fs.update(catalog_source_data({'files': {'test0/a': {'same:3'}, '/test0/a': {'same:3'}}}))
            fs.db.conn.close()
            fs = VirtualFS(None, 'sqlite', db_path=filename,
                           fragments={'/~:/test0': fragment}, refragment=True)
            try:
                self.assertIsNotNone(fs.get_from_path('test0/a'))
                self.assertEqual(fs.get_hash_dups('same:3'), {'test0/a', '/test0/a'})
                relative_store = fs.db.stores['/~:/test0']
                self.assertEqual({row[0] for row in relative_store.conn.execute('SELECT path FROM hashes')}, {'test0/a'})
                fs.update(catalog_source_data({'files': {'test0': {'replacement:1'}}}))
                self.assertEqual(fs.get_hash_dups('same:3'), {'/test0/a'})
            finally: fs.db.conn.close()

    def test_livelog_exports_raw_source_paths_and_reimports(self):
        from vfs.export import export_livelog
        from drive import load_log
        with tempfile.TemporaryDirectory() as folder, patch.dict(aliases, {}, clear=True):
            data = catalog_source_data({'files': {'test0/a': {'MD5:abc:3'}, '/test0/a': {'MD5:abc:3'}},
                                       'hashes': {'MD5:abc:3': {'test0/a', '/test0/a'}}})
            fs = VirtualFS(data, 'sqlite', rebuild_db=True, db_path=str(Path(folder) / 'db'))
            try:
                destination = Path(folder) / 'export'
                export_livelog(fs.db, destination)
                log = destination / '000/llog-llogfiles.sh'
                text = log.read_text()
                self.assertIn('"test0/a"', text)
                self.assertIn('"/test0/a"', text)
                self.assertNotIn('~:', text)
                imported = {'files': {}, 'hashes': {}}
                load_log(imported, log)
                restored = VirtualFS(catalog_source_data(imported))
                self.assertEqual(restored.get_from_path('test0/a').info['path'], 'test0/a')
                self.assertEqual(restored.get_from_path('/test0/a').info['path'], '/test0/a')
            finally: fs.db.conn.close()

    def test_collapsed_legacy_collision_requires_original_logs(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(aliases, {}, clear=True):
            fs = VirtualFS({'files': {'test0/a': {'hash:3'}},
                            'hashes': {'hash:3': {'test0/a', '/test0/a'}}},
                           'sqlite', rebuild_db=True, db_path=str(Path(folder) / 'db'))
            try:
                with self.assertRaisesRegex(ValueError, 'Ambiguous'):
                    migrate_source_paths(fs.db)
                self.assertIsNotNone(fs.get_from_path('/test0/a'))
            finally: fs.db.conn.close()
# VERIFY CATALOG ORIGINS AND LEGACY SOURCE MIGRATION ]
