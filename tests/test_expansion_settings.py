"""The o expansion preference persists per catalog without saving open folders."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS
from vfs.scanner import ScanStore

spec = importlib.util.spec_from_file_location('expansion_settings_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class ExpansionSettingsTests(unittest.TestCase):
    def test_o_preference_survives_database_reopen_both_values(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(tui, 'HISTORY_PATH', Path(directory) / 'history.llog'):
            database = str(Path(directory) / 'catalog.sqlite')
            def browser(fs):
                return tui.DriveBrowser(fs, path=directory, input=DummyInput(), output=DummyOutput())
            for expected in (False, True, False):
                fs = VirtualFS(None, 'sqlite', db_path=database)
                try:
                    app = browser(fs)
                    self.assertIs(app.expand_all_levels, expected)
                    self.assertFalse(app.expanded_dirs)
                    app.toggle_expansion_depth()
                    self.assertIs(ScanStore(fs.db).get('ui', 'expand_all_levels'), not expected)
                finally:
                    fs.db.conn.close()
            other = VirtualFS({'files': {}})
            self.assertFalse(browser(other).expand_all_levels)
            ScanStore(other.db).put('ui', 'expand_all_levels', 'false')
            self.assertFalse(browser(other).expand_all_levels)
