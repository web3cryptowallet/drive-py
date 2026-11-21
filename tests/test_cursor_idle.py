"""Cursor redraws stay immediate; expensive work waits for one quiet second."""
import asyncio
import importlib.util
from pathlib import Path
from queue import Queue
from threading import Event, Thread
from types import SimpleNamespace as NS
import time
import unittest
from unittest.mock import Mock
from vfs import VirtualFS
from vfs.scanner import DriveScanner, ScanControls

spec = importlib.util.spec_from_file_location('idle_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class CursorIdleTests(unittest.IsolatedAsyncioTestCase):
    async def test_repeated_moves_defer_and_coalesce_work_for_latest_row(self):
        browser = object.__new__(tui.DriveBrowser)
        controls = NS(interaction_until=0.)
        browser.scanners = [NS(controls=controls)]
        browser.rows = [dict(name='one'), dict(name='two'), dict(name='three')]
        browser.selected = 0
        browser.graphics_mode = False
        browser.video_player = None
        browser.auto_quick_view = True
        browser.screen_stack = []
        browser.app = NS(create_background_task=asyncio.create_task, invalidate=Mock())
        browser.sync_scan_symbols = Mock()
        seen = []
        browser.show_info = lambda **kwargs: seen.append(browser.current_name())
        browser.select(1)
        task = browser.cursor_idle_task
        self.assertEqual(browser.selected, 1)
        browser.sync_scan_symbols.assert_not_called()
        self.assertTrue(browser.cursor_busy())
        await asyncio.sleep(.25)
        browser.select(2)
        self.assertIs(browser.cursor_idle_task, task)
        self.assertEqual(controls.interaction_until, browser.cursor_idle_until)
        await asyncio.sleep(.8)
        browser.sync_scan_symbols.assert_not_called()
        self.assertEqual(seen, [])
        await asyncio.wait_for(task, .6)
        browser.sync_scan_symbols.assert_called_once()
        self.assertEqual(seen, ['three'])
        self.assertFalse(browser.cursor_busy())
        self.assertIsNone(browser.cursor_idle_task)

    async def test_worker_yields_and_stop_interrupts_idle_wait(self):
        controls = ScanControls(startup=True)
        scanner = DriveScanner(VirtualFS({'files': {}}).db, '/', Queue(), Event(), controls=controls)
        scanner.current_mode = 1
        scanner.active_epoch = controls.epochs[0]
        controls.interaction_until = time.monotonic() + 1.
        result = []
        thread = Thread(target=lambda: result.append(scanner.enabled(1)))
        thread.start()
        try:
            await asyncio.sleep(.05)
            self.assertTrue(thread.is_alive())
            self.assertEqual(controls.modes, (True, False, False))
            scanner.stop.set()
            thread.join(.5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(result, [False])
        finally:
            scanner.stop.set()
            thread.join(.5)

    async def test_scanner_file_page_changes_immediately_while_cursor_busy(self):
        from vfs.scanner import ScanEntry, FileMap, Pagination
        scanner = object.__new__(tui.ScannerView)
        scanner.browser = NS(cursor_busy=lambda: True, note_cursor_motion=Mock())
        scanner.model = FileMap()
        scanner.model.fixed = False
        scanner.model.limit = 100
        scanner.selected = 0
        scanner.follow_end = False
        scanner.filter = None
        scanner.pagination = Pagination()
        scanner.page_size = 3
        scanner.detail_signature = None
        scanner.details = NS(index=0)
        scanner.invalidate = Mock()
        for index in range(7):
            path = f'/scan/file{index}'
            scanner.model.update(ScanEntry(path, path, False))
        scanner.model.rebuild()
        scanner.update_details(immediate=True)
        all_ids = list(scanner.model.entries)
        self.assertEqual(scanner.detail_ids, all_ids[:3])
        scanner.details.index = 2
        scanner.move_details(1)
        self.assertEqual(scanner.pagination.page, 2)
        self.assertEqual(scanner.detail_ids, all_ids[3:6])
        self.assertEqual(scanner.details.index, 0)
        scanner.move_details(-1)
        self.assertEqual(scanner.pagination.page, 1)
        self.assertEqual(scanner.detail_ids, all_ids[:3])
        self.assertEqual(scanner.details.index, 2)
        scanner.set_page(3)
        self.assertEqual(scanner.detail_ids, all_ids[6:])
        self.assertEqual(scanner.details.index, 0)


class DeferredScannerRenderTests(unittest.TestCase):
    def test_saved_bucket_renders_before_first_details_refresh(self):
        import tempfile
        from dataclasses import asdict
        from prompt_toolkit.input import DummyInput
        from prompt_toolkit.output import DummyOutput
        from prompt_toolkit.layout.controls import FormattedTextControl
        from vfs.scanner import ScanEntry, ScanStore
        with tempfile.TemporaryDirectory() as directory:
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=DummyInput(), output=DummyOutput())
            entry = ScanEntry(directory + '/file', directory + '/file', False, 100)
            ScanStore(browser.vfs.db).put('map', browser.vfs.pwd(),
                                         {'entries': [asdict(entry)]})
            browser.cursor_busy = Mock(return_value=True)
            scanner = tui.ScannerView(browser, startup=False)
            self.assertTrue(scanner.model.buckets)
            self.assertEqual(scanner.filtered_count, 0)
            summary = FormattedTextControl(lambda: scanner.path_fragments(scanner.bucket_summary()))
            self.assertIsNotNone(summary.preferred_width(80))
            self.assertIn('shown 0/1', scanner.bucket_summary())
            browser.cursor_busy.return_value = False
            scanner.update_details()
            self.assertEqual(scanner.filtered_count, 1)
            self.assertIn('shown 1/1', scanner.bucket_summary())
