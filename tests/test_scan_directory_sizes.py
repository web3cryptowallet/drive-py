"""Live directory sizes use bounded cached scan-event accounting."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock
from vfs.scanner import ScanEntry

spec = importlib.util.spec_from_file_location('size_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


def scanner():
    view = object.__new__(tui.ScannerView)
    view.directory_sizes = {}
    view.directory_counts = {}
    view.directory_size_files = {}
    view.directory_size_dirty = set()
    return view


class DirectorySizeTests(unittest.TestCase):
    def test_deltas_deduplicate_repeated_entries_and_remove_sizes(self):
        view = scanner()
        entry = ScanEntry('/a/sub/file', '/a/sub/file', False, 100)
        view.account_directory_size(entry)
        view.account_directory_size(entry)
        self.assertEqual(view.directory_sizes, {'/a/sub': 100, '/a': 100, '': 100})
        view.account_directory_size(ScanEntry(entry.id, entry.path, False, 250))
        self.assertEqual(view.directory_sizes['/a'], 250)
        self.assertEqual(view.directory_counts['/a'], 1)
        view.account_directory_size(ScanEntry('/a/empty', '/a/empty', True, state='empty'))
        self.assertEqual(view.directory_sizes['/a'], 250)
        self.assertEqual(view.directory_counts['/a'], 1)
        view.account_directory_size(removed=entry.id)
        self.assertEqual(view.directory_sizes['/a'], 0)
        self.assertEqual(view.directory_counts['/a'], 0)
        view.account_directory_size(ScanEntry(entry.id, entry.path, False, 100, blacklisted=True))
        self.assertEqual(view.directory_sizes['/a'], 0)
        self.assertEqual(view.directory_counts['/a'], 0)

    def test_cached_sizes_yield_during_motion_and_preserve_catalog_floor(self):
        view = scanner()
        view.account_directory_size(ScanEntry('/a/file', '/a/file', False, 5000))
        row = dict(node=NS(size=100), size='old')
        browser = object.__new__(tui.DriveBrowser)
        browser.scanners = [view]
        browser.directory_size_rows = {'/a': row}
        browser.metadata_widths = (2, 7)
        browser.cursor_busy = Mock(return_value=True)
        browser.update_scan_directory_sizes(view)
        self.assertEqual(row['size'], 'old')
        self.assertTrue(view.directory_size_dirty)
        browser.cursor_busy.return_value = False
        browser.update_scan_directory_sizes(view)
        self.assertEqual(row['size'], tui.format_size(5000, 0).strip())
        self.assertGreaterEqual(browser.metadata_widths[0], len(row['size']) + 1)
        view.account_directory_size(removed='/a/file')
        browser.update_scan_directory_sizes(view)
        self.assertEqual(row['size'], tui.format_size(100, 0).strip())
        self.assertEqual(row['node'].size, 100)

    def test_each_tick_updates_at_most_128_dirty_directories(self):
        view = scanner()
        view.directory_size_dirty = {f'/dir{i}' for i in range(300)}
        browser = object.__new__(tui.DriveBrowser)
        browser.cursor_busy = lambda: False
        browser.directory_size_rows = {}
        browser.update_scan_directory_sizes(view)
        self.assertGreaterEqual(len(view.directory_size_dirty), 172)
