"""Global disk navigation reuses tracked nodes instead of creating orange copies."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS, aliases, get_real_path

spec = importlib.util.spec_from_file_location('global_identity_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class GlobalPathIdentityTests(unittest.TestCase):
    def test_home_fallback_never_recurses_into_full_path_lookup(self):
        for backend in ('memory', 'sqlite'):
            for alias in (None, 'root', '~0:/'):
                with self.subTest(backend=backend, alias=alias), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    home = root / 'home' / 'lucky'
                    home.mkdir(parents=True)
                    (home / 'src').mkdir()
                    with patch.dict(os.environ, {'HOME': str(home)}), patch.dict(aliases, {} if alias is None else {alias: str(home)}, clear=True):
                        fs = VirtualFS({'files': {}}, backend,
                            **({'db_path': str(root / 'db.sqlite')} if backend == 'sqlite' else {}))
                        try:
                            # Child fallback must never re-enter get_from_path.
                            parent = fs.get_from_path('/:' + str(home.parent))
                            with patch.object(fs, 'get_from_path', side_effect=AssertionError('recursive path lookup')):
                                node = fs._child(parent, 'lucky')
                            self.assertIsNotNone(node)
                            self.assertEqual(get_real_path(node.id), str(home))
                            for path in (str(home), '/:' + str(home), '/~0:'):
                                fs.cwd = fs.get_from_path(path)
                                self.assertIsNotNone(fs.cwd)
                                self.assertEqual(get_real_path(fs.pwd()), str(home))
                                self.assertIn('src', [entry.name for entry in fs.list_nodes()])
                            fs.cwd = fs.get_from_path('/:' + str(home))
                            fs.enter('..')
                            self.assertEqual(get_real_path(fs.pwd()), str(home.parent))
                        finally:
                            if backend == 'sqlite':
                                fs.db.conn.close()

    def test_root_browser_reuses_catalog_metadata_and_green_status(self):
        for backend in ('memory', 'sqlite'):
            for spelling in ('absolute', 'global', 'alias'):
                with self.subTest(backend=backend, spelling=spelling), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    folder = root / 'media' / 'lucky' / '250D'
                    folder.mkdir(parents=True)
                    target = folder / 'tracked.txt'
                    target.write_text('hello')
                    (folder / 'new.txt').write_text('new')
                    catalog_path = (str(target) if spelling == 'absolute' else
                                    '/:' + str(target) if spelling == 'global' else '/media/lucky/250D/tracked.txt')
                    mappings = {'media': str(root / 'media')} if spelling == 'alias' else {}
                    with patch.dict(aliases, mappings, clear=True), patch.object(tui, 'HISTORY_PATH', root / 'history.llog'):
                        fs = VirtualFS({'files': {catalog_path: {'MD5:abc:5'}}},
                                       backend, rebuild_db=True,
                                       **({'db_path': str(root / 'db.sqlite')} if backend == 'sqlite' else {}))
                        try:
                            tracked = fs.get_from_path(catalog_path)
                            fs.cwd = fs.db.get_root()
                            fs.enter('/')
                            for component in folder.parts[1:]:
                                fs.enter(component)
                            self.assertEqual(get_real_path(fs.pwd()), str(folder))
                            entries = {node.name: node for node in fs.list_nodes()}
                            self.assertEqual(entries['tracked.txt'].id, tracked.id)
                            self.assertEqual(entries['tracked.txt'].info['hashinfo'], 'MD5:abc:5')
                            self.assertNotEqual(entries['tracked.txt'].info.get('status'), 'new')
                            with patch.object(fs, 'start_in_current_directory'):
                                browser = tui.DriveBrowser(fs, input=DummyInput(), output=DummyOutput())
                            indicators = {row['name']: row['indicator'] for row in browser.rows}
                            self.assertEqual(indicators['tracked.txt'], 'green')
                            self.assertEqual(indicators['new.txt'], 'orange')
                            self.assertEqual(fs.get_from_path('/:' + str(target)).id, tracked.id)
                            fs.enter('..')
                            self.assertEqual(get_real_path(fs.pwd()), str(folder.parent))
                        finally:
                            if backend == 'sqlite':
                                fs.db.conn.close()
