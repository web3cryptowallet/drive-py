"""Explicit disk prefixes, relative roots and followed symbolic links."""
# VERIFY LOCAL PATH RESOLUTION AND SYMLINK RENDERING [
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS, aliases, get_real_path, get_stat_info

spec = importlib.util.spec_from_file_location('local_paths_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class LocalPathTests(unittest.TestCase):
    def test_relative_absolute_and_explicit_disk_prefixes(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(aliases, {'disk': folder, 'relative': 'test0'}, clear=True):
            target = Path(folder) / 'a.txt'
            target.write_text('hello')
            self.assertEqual(get_real_path('test0/'), os.path.join(os.getcwd(), 'test0'))
            self.assertEqual(get_real_path('/home/example'), '/home/example')
            self.assertEqual(get_real_path('relative:/file'), os.path.join(os.getcwd(), 'test0/file'))
            for path in (str(target), ':' + str(target), '/:' + str(target), 'disk:/a.txt', '/disk:/a.txt', '/disk/a.txt'):
                self.assertEqual(get_real_path(path), str(target))
                self.assertEqual(get_stat_info(path)['size'], 5)
            fs = VirtualFS({'files': {':' + str(target): {'hash:5'}}})
            node = fs.get_from_path(':' + str(target))
            self.assertEqual(fs.get_full_info(node)['size'], 5)
            self.assertTrue(fs.get_full_info(node)['exists'])
            with patch.dict(aliases, {'home': '/wrong'}):
                self.assertEqual(get_real_path(':/home/example'), '/home/example')

    def test_follow_links_and_render_marker_without_mutating_identity(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(aliases, {'disk': folder}, clear=True):
            root = Path(folder)
            (root / 'target').mkdir()
            (root / 'target/a.txt').write_text('hello')
            (root / 'linked').symlink_to('target', target_is_directory=True)
            (root / 'file-link').symlink_to('target/a.txt')
            (root / 'broken').symlink_to('missing')
            (root / 'target/back').symlink_to('..', target_is_directory=True)
            fs = VirtualFS({'files': {}})
            with patch.object(tui, 'HISTORY_PATH', root / 'history.llog'):
                browser = tui.DriveBrowser(fs, path=folder, output=DummyOutput())
            self.assertFalse(browser.show_path_prefixes)
            browser.refresh('file-link')
            row = browser.rows[browser.selected]
            identity = row['node'].id
            self.assertEqual(row['indicator'], 'green')
            self.assertEqual(browser.file_list_path(row), 'file-link ↗')
            self.assertEqual(row['node'].name, 'file-link')
            self.assertEqual(row['node'].size, 5)
            content = browser.control.create_content(22, 20)
            self.assertIn('↗', ''.join(text for _, text in content.get_line(browser.selected)))
            self.assertEqual(row['node'].id, identity)
            browser.refresh('broken')
            self.assertEqual(browser.rows[browser.selected]['indicator'], 'red')
            self.assertTrue(get_stat_info('/disk/broken')['is_symlink'])
            browser.refresh('linked')
            browser.open()
            self.assertIn('a.txt', [r['name'] for r in browser.rows])
            browser.parent()
            browser.refresh('linked')
            browser.expand_all_levels = True
            browser.expand_subdirs()
            self.assertLess(len(browser.expanded_dirs), 10)
# VERIFY LOCAL PATH RESOLUTION AND SYMLINK RENDERING ]
