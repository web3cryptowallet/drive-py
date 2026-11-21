"""Default startup restores per-database navigation while explicit paths win."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS
from vfs.scanner import ScanStore

spec = importlib.util.spec_from_file_location('startup_restore_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class StartupRestoreTests(unittest.TestCase):
    def test_first_launch_restore_navigation_override_empty_and_missing(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(tui, 'HISTORY_PATH', Path(directory) / 'history.llog'):
            root = Path(directory)
            one, two = root / 'one', root / 'two'
            one.mkdir()
            two.mkdir()
            database = str(root / 'catalog.sqlite')
            cwd = os.getcwd()
            def launch(path=None):
                fs = VirtualFS(None, 'sqlite', db_path=database)
                browser = tui.DriveBrowser(fs, path=path, input=DummyInput(), output=DummyOutput())
                return fs, browser
            fs, browser = launch()
            self.assertEqual(browser.original_path(fs.pwd()), os.path.realpath(cwd))
            self.assertTrue(browser.go_path(str(one)))
            fs.db.conn.close()
            fs, browser = launch('')
            self.assertEqual(browser.original_path(fs.pwd()), str(one))
            self.assertEqual(browser.startup_path, cwd)
            fs.db.conn.close()
            fs, browser = launch(str(two))
            self.assertEqual(browser.original_path(fs.pwd()), str(two))
            fs.db.conn.close()
            two.rmdir()
            fs, browser = launch()
            self.assertEqual(browser.original_path(fs.pwd()), os.path.realpath(cwd))
            ScanStore(fs.db).put('ui', 'last_directory', 'invalid')
            fs.db.conn.close()
            fs, browser = launch('  ')
            self.assertEqual(browser.original_path(fs.pwd()), os.path.realpath(cwd))
            self.assertEqual(os.getcwd(), cwd)
            with fs.db.conn:
                fs.db.conn.execute("UPDATE scan_state SET value='invalid-json' WHERE kind='ui' AND key='last_directory'")
            fs.db.conn.close()
            fs, browser = launch()
            self.assertEqual(browser.original_path(fs.pwd()), os.path.realpath(cwd))
            self.assertTrue(browser.go_path('/'))
            fs.db.conn.close()
            fs, browser = launch()
            self.assertEqual(fs.pwd(), '/')
            fs.db.conn.close()

    def test_cli_accepts_empty_startup_argument(self):
        with patch('sys.argv', ['drive-tui.py', '']), patch.object(tui, 'load_config', return_value={}), \
                patch.object(tui, 'load_vfs') as load, patch.object(tui, 'DriveBrowser') as browser:
            tui.main()
            browser.assert_called_once_with(load.return_value, path='')
            browser.return_value.run.assert_called_once()
