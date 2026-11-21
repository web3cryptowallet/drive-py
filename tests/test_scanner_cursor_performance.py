"""Scanner cursor redraw reuses page formatting and width calculations."""
from dataclasses import replace
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS
from vfs.scanner import ScanEntry

spec = importlib.util.spec_from_file_location('fast_scanner_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class ScannerCursorTests(unittest.TestCase):
    def test_page_cache_clipped_rows_and_refresh_contracts(self):
        with tempfile.TemporaryDirectory() as directory:
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=DummyInput(), output=DummyOutput())
            scanner = tui.ScannerView(browser, startup=False)
            scanner.model.fixed = False
            scanner.model.limit = 100
            for index in range(6):
                path = '/scan/' + 'long/' * 80 + str(index)
                scanner.model.update(ScanEntry(path, path, False, 10))
            scanner.model.rebuild()
            scanner.page_size = 3
            scanner.update_details(immediate=True)
            rows = scanner.detail_rows()
            scanner.details.create_content(40, 3)
            scanner.details.maximum_pan()
            with patch.object(browser, 'display_path', side_effect=AssertionError('reformatting page')):
                scanner.details.move(1)
                self.assertIs(scanner.detail_rows(), rows)
                content = scanner.details.create_content(40, 3)
                self.assertLessEqual(sum(tui.get_cwidth(text) for _, text in content.get_line(0)), 40)
                with patch.object(tui, 'get_cwidth', side_effect=AssertionError('recounting width')):
                    scanner.details.maximum_pan()
                    scanner.horizontal.create_content(40, 1)
            key = scanner.detail_ids[0]
            scanner.model.update(replace(scanner.model.entries[key], state='modified'))
            updated = scanner.detail_rows()
            self.assertIsNot(updated, rows)
            self.assertTrue(any(text == 'M' for _, text in updated[0]))
            scanner.set_page(2)
            self.assertIsNot(scanner.detail_rows(), updated)
            scanner.filter = 'unknown'
            scanner.detail_signature = None
            scanner.update_details(immediate=True)
            filtered = scanner._filtered_ids_value
            scanner.set_page(1)
            self.assertIs(scanner._filtered_ids_value, filtered)
            scanner.set_page(2)
            self.assertIs(scanner._filtered_ids_value, filtered)
            scanner.scope_path = '/scan'
            self.assertTrue(any(style == 'fg:#ffd700' and text for style, text in scanner.detail_rows()[0]))

    def test_bucket_selection_and_filters_are_synchronous_during_motion(self):
        with tempfile.TemporaryDirectory() as directory:
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=DummyInput(), output=DummyOutput())
            scanner = tui.ScannerView(browser, startup=False)
            scanner.model.fixed = False
            scanner.model.limit = 1
            for index in range(2):
                path = f'/scan/{index}'
                scanner.model.update(ScanEntry(path, path, False))
            scanner.model.rebuild()
            scanner.move_map(1)
            self.assertTrue(browser.cursor_busy())
            self.assertEqual(scanner.detail_ids, ['/scan/1'])
            scanner.filter = 'unknown'
            scanner.move_map(-1)
            self.assertEqual(scanner.detail_ids, ['/scan/0'])
            self.assertEqual(scanner.pagination.page, 1)
            self.assertEqual(scanner.details.index, 0)
            scanner.move_map(1)
            self.assertEqual(scanner.detail_ids, ['/scan/1'])
            scanner.filter = 'verified'
            scanner.move_map(-1)
            self.assertEqual(scanner.detail_ids, [])
            self.assertEqual(scanner.filtered_count, 0)
            scanner.filter = None
            scanner.selection_changed()
            self.assertEqual(scanner.detail_ids, ['/scan/0'])
            scanner.end()
            self.assertEqual(scanner.detail_ids, [])
            self.assertEqual(scanner.filtered_count, 0)
