"""Positional startup directories preserve the process cwd and storage location."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS, aliases

spec = importlib.util.spec_from_file_location('startup_path', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class StartupPathTests(unittest.TestCase):
    def test_symlink_startup_and_symlink_mount_reuse_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mount = root / 'disk'
            target = mount / 'folder'
            target.mkdir(parents=True)
            link = root / 'shortcut'
            link.symlink_to(target, target_is_directory=True)
            mount_link = root / 'mounted-link'
            mount_link.symlink_to(mount, target_is_directory=True)
            cwd = os.getcwd()
            for configured in [mount, mount_link]:
                with self.subTest(configured=configured), patch.dict(aliases, {'disk': str(configured)}, clear=True):
                    fs = VirtualFS({'files': {'/disk/folder/catalog.txt': {'MD5:abc:4'}}})
                    fs.start_in_current_directory(str(link))
                    self.assertEqual(fs.pwd(), '/disk/folder')
                    self.assertIn('catalog.txt', [node.name for node in fs.list_nodes()])
                    self.assertEqual(os.getcwd(), cwd)

    def test_local_paths_and_aliases_without_chdir(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'my path'
            target.mkdir()
            (target / 'file.txt').write_text('hello')
            with patch.dict(os.environ, {'HOME': directory}), patch.dict(aliases, {}, clear=True):
                for path in ['~/my path', str(target), os.path.relpath(target)]:
                    with self.subTest(path=path), create_pipe_input() as pipe:
                        fs = VirtualFS({'files': {}})
                        browser = tui.DriveBrowser(fs, path=path, input=pipe, output=DummyOutput())
                        self.assertEqual(fs.pwd(), str(target))
                        self.assertIn('file.txt', [row['name'] for row in browser.rows])
                        self.assertEqual(os.getcwd(), cwd)
                with patch.dict(aliases, {'disk': directory}):
                    fs = VirtualFS({'files': {}})
                    fs.start_in_current_directory(str(target))
                    self.assertEqual(fs.pwd(), '/disk/my path')
                    self.assertIn('file.txt', [node.name for node in fs.list_nodes()])
            fs = VirtualFS({'files': {}})
            for invalid in [str(root / 'missing'), str(target / 'file.txt')]:
                with self.assertRaises(ValueError):
                    fs.start_in_current_directory(invalid)

    def test_cli_passes_positional_path_and_rejects_invalid_before_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('sys.argv', ['drive-tui.py', directory]), \
                    patch.object(tui, 'load_config'), patch.object(tui, 'load_vfs') as load, \
                    patch.object(tui, 'DriveBrowser') as browser:
                tui.main()
                browser.assert_called_once_with(load.return_value, path=directory)
                browser.return_value.run.assert_called_once()
            with patch('sys.argv', ['drive-tui.py', directory + '/missing']), \
                    patch.object(tui, 'load_vfs') as load, patch('sys.stderr'):
                with self.assertRaises(SystemExit) as error:
                    tui.main()
                self.assertEqual(error.exception.code, 2)
                load.assert_not_called()
