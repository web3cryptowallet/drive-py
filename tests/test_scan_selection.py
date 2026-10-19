"""Folder marks and scoped scanner discovery."""
import importlib.util
from pathlib import Path
from queue import Queue
from threading import Event
import tempfile
import unittest
from unittest.mock import Mock
from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS
from vfs.scanner import DriveScanner, ScanControls

spec = importlib.util.spec_from_file_location('selection_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)

class SelectionTests(unittest.TestCase):
    def test_marks_cursor_styles_navigation_and_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('a', 'b'):
                (root / name).mkdir()
                (root / name / 'file').write_text(name)
            (root / 'plain').write_text('file')
            fs = VirtualFS({'files': {}})
            browser = tui.DriveBrowser(fs, path=directory, input=DummyInput(), output=DummyOutput())
            browser.app.invalidate = Mock()
            browser.selected = next(i for i, row in enumerate(browser.rows) if row['name'] == 'a')
            index = browser.selected
            browser.toggle_scan_selection()
            selected = browser.rows[index]['node'].id
            self.assertEqual(browser.selected, index)
            self.assertEqual(browser.scan_selection, {selected})
            self.assertIn('#ffd700', browser.scan_row_style(browser.rows[index]))
            browser.toggle_scan_selection(True)
            self.assertEqual(browser.selected, index + 1)
            self.assertFalse(browser.scan_selection)
            browser.invert_scan_selection()
            self.assertEqual(len(browser.scan_selection), 2)
            browser.invert_scan_selection()
            self.assertFalse(browser.scan_selection)
            browser.selected = index
            browser.toggle_scan_selection()
            view = tui.ScannerView(browser, startup=False)
            self.assertEqual(view.scan_roots, (selected,))
            self.assertNotEqual(view.storage_path, view.path)
            scanner = DriveScanner(fs.db, fs.pwd(), Queue(), Event(),
                controls=ScanControls((True, False, False), startup=False),
                scan_roots=view.scan_roots, storage_path=view.storage_path)
            scanner.scan_once(fs.db)
            self.assertEqual(set(scanner.entries), {selected, selected + '/file'})
            browser.open()
            self.assertFalse(browser.scan_selection)
            browser.parent()
            browser.selected = next(i for i, row in enumerate(browser.rows) if row['name'] == 'plain')
            browser.toggle_scan_selection()
            self.assertFalse(browser.scan_selection)
