"""Finite automatic expert scanning and persistent per-path scan accounting."""
import asyncio
import importlib.util
from pathlib import Path
from queue import Queue
from threading import Event
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from prompt_toolkit.input import DummyInput, create_pipe_input
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS
from vfs.scan_statistics import ScanStatistics
from vfs.scanner import DriveScanner, ScanControls, ScanEntry, ScanStore

spec = importlib.util.spec_from_file_location('statistics_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class AutomaticExpertTests(unittest.TestCase):
    def test_default_stops_skips_old_and_manual_expert_rescans(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'old'
            path.write_bytes(b'old data')
            fs = VirtualFS({'files': {}})
            controls = ScanControls(startup=True)
            self.assertEqual(controls.heavy_order, 'expert')
            first = DriveScanner(fs.db, directory, Queue(), Event(), controls=controls)
            first.scan_once(fs.db)
            self.assertEqual(controls.modes, (False, False, False))
            self.assertEqual(first.mode_counts[2], [1, 8])
            fresh = Path(directory) / 'new'
            fresh.write_bytes(b'new')
            second_controls = ScanControls(startup=True)
            second = DriveScanner(fs.db, directory, Queue(), Event(), controls=second_controls,
                                  entries=first.entries.values())
            second.scan_once(fs.db)
            self.assertEqual(second.mode_counts[1], [1, 3])
            self.assertEqual(second.mode_counts[2], [1, 3])
            self.assertEqual(second_controls.modes, (False, False, False))
            # Explicitly start expert; previously verified files become eligible.
            second_controls.buckets = tuple((entry.id,) for entry in second.entries.values() if not entry.is_dir)
            second_controls.toggle(3)
            for _ in range(10):
                second.scan_once(fs.db)
                if second.mode_counts[2][0] > 1:
                    break
            self.assertGreater(second.mode_counts[2][0], 1)

    def test_manual_lite_advances_and_loop_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'file').write_bytes(b'data')
            fs = VirtualFS({'files': {}})
            controls = ScanControls(modes=(False, False, False), heavy_order='expert')
            controls.toggle(1)
            scanner = DriveScanner(fs.db, directory, Queue(), Event(), controls=controls)
            scanner.scan_once(fs.db)
            self.assertFalse(any(controls.modes))
            self.assertEqual([counts[0] for counts in scanner.mode_counts], [1, 1, 1])
            controls.toggle_loop()
            self.assertTrue(controls.loop)
            self.assertEqual(controls.modes, (True, False, False))
            scanner.scan_once(fs.db)
            self.assertEqual(controls.startup_mode, 1)
            self.assertEqual(controls.modes, (True, False, False))
            controls.toggle_loop()
            scanner.scan_once(fs.db)
            self.assertFalse(any(controls.modes))
            self.assertIsNone(controls.startup_mode)

    def test_manual_medium_advances_heavy_and_order_preserves_sequence(self):
        controls = ScanControls(modes=(False, False, False))
        controls.toggle(2)
        controls.toggle_order()
        self.assertEqual(controls.startup_mode, 2)
        controls.advance_startup(2)
        self.assertEqual(controls.modes, (False, False, True))
        controls.advance_startup(3)
        self.assertFalse(any(controls.modes))
        controls.start_from(1, '/file')
        self.assertEqual(controls.startup_mode, 1)
        self.assertEqual(controls.modes, (True, False, False))
        controls.toggle(1)
        self.assertFalse(any(controls.modes))

    def test_new_precedes_unknown_and_errors_do_not_loop(self):
        with tempfile.TemporaryDirectory() as directory:
            fs = VirtualFS({'files': {}})
            known = str(Path(directory) / 'a-unknown')
            fresh = str(Path(directory) / 'z-new')
            Path(known).write_bytes(b'known')
            Path(fresh).write_bytes(b'new')
            fs.db.add_scanned_file(known, 'md5:00000000000000000000000000000000', 5)
            ScanStore(fs.db).put('entry', known, vars(ScanEntry(known, known, False, 5, 'unknown')))
            scanner = DriveScanner(fs.db, directory, Queue(), Event(), controls=ScanControls(startup=True))
            order = []
            verify = scanner.verify
            def record(entry, *args):
                if scanner.current_mode == 3:
                    order.append(entry.id)
                return verify(entry, *args)
            with patch.object(scanner, 'verify', side_effect=record):
                scanner.scan_once(fs.db)
            self.assertEqual(order, [fresh, known])
            self.assertEqual(scanner.controls.modes, (False, False, False))


class StatisticsStorageTests(unittest.TestCase):
    def test_interactive_map_saves_defer_counts_until_browser_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / 'stats.sqlite')
            fs = VirtualFS(None, 'sqlite', db_path=database)
            try:
                browser = tui.DriveBrowser(fs, path=directory,
                                           input=DummyInput(),
                                           output=DummyOutput())
                scanner = tui.ScannerView(browser, startup=False)
                ledger = browser.scan_statistics
                token = object()
                ledger.begin(scanner.storage_path, token, [0, 0, 0])
                ledger.update(scanner.storage_path, token, [(2, 123), (0, 0), (0, 0)],
                              [(2, 123), (0, 0), (0, 0)], [1, 0, 0], [1, 0, 0])
                with patch.object(ledger, 'save', side_effect=AssertionError('UI count write')):
                    scanner.save()
                    scanner.save()
                self.assertEqual(fs.db.conn.execute('SELECT COUNT(*) FROM scan_statistics').fetchone()[0], 0)
                self.assertIn(scanner.storage_path, ledger.dirty)
                with patch.object(browser.app, 'run'), patch.object(tui.sys, 'stderr'), \
                        patch.object(browser, 'stop_video'), patch.object(browser, 'clear_native_preview'), \
                        patch.object(browser, 'clear_grid_native'):
                    browser.run()
                self.assertFalse(ledger.dirty)
                reopened = sqlite3.connect(database)
                try:
                    self.assertEqual(reopened.execute(
                        "SELECT files,bytes,seconds FROM scan_statistics WHERE path=? AND scope='total' AND mode=1",
                        (scanner.storage_path,)).fetchone(), (2, 123, 1.))
                finally:
                    reopened.close()
            finally:
                fs.db.conn.close()

    def test_periodic_save_retries_busy_database_without_losing_dirty_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / 'stats.sqlite')
            fs = VirtualFS(None, 'sqlite', db_path=database)
            blocker = sqlite3.connect(database)
            try:
                ledger = ScanStatistics(fs.db)
                token = object()
                ledger.begin('/busy', token, [0, 0, 0])
                ledger.update('/busy', token, [(2, 123), (0, 0), (0, 0)],
                              [(2, 123), (0, 0), (0, 0)], [1, 0, 0], [1, 0, 0])
                fs.db.conn.execute('PRAGMA busy_timeout=1234')
                blocker.execute('BEGIN IMMEDIATE')
                self.assertFalse(ledger.save(nonblocking=True))
                self.assertEqual(ledger.dirty, {'/busy'})
                self.assertEqual(fs.db.conn.execute('PRAGMA busy_timeout').fetchone()[0], 1234)
                self.assertFalse(fs.db.conn.in_transaction)
                blocker.rollback()
                self.assertTrue(ledger.save(nonblocking=True))
                self.assertFalse(ledger.dirty)
                self.assertEqual(fs.db.conn.execute(
                    "SELECT files,bytes,seconds FROM scan_statistics WHERE path='/busy' AND scope='total' AND mode=1"
                ).fetchone()[:], (2, 123, 1.))
            finally:
                blocker.close()
                fs.db.conn.close()

    def test_sessions_current_reset_totals_and_path_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            fs = VirtualFS(None, 'sqlite', db_path=str(Path(directory) / 'stats.sqlite'))
            try:
                ledger = ScanStatistics(fs.db)
                token = object()
                ledger.begin('/a', token, [10, 20, 30])
                ledger.update('/a', token, [(2, 2000000), (1, 100), (0, 0)],
                              [(2, 2000000), (1, 100), (0, 0)], [12, 23, 30], [2, 3, 0])
                ledger.update('/a', token, [(2, 2000000), (1, 100), (0, 0)],
                              [(2, 2000000), (1, 100), (0, 0)], [12, 23, 30], [2, 3, 0])
                self.assertEqual(ledger.record('/a')['total'][0], [2, 2000000, 2])
                self.assertEqual(ledger.record('/b')['total'][0], [0, 0, 0])
                token2 = object()
                ledger.begin('/a', token2, [0, 0, 0])
                self.assertEqual(ledger.record('/a')['current'][0], [0, 0, 0])
                self.assertEqual(ledger.record('/a')['session'][0][0], 2)
                ledger.save()
                self.assertIsNotNone(fs.db.conn.execute('SELECT files FROM scan_statistics WHERE path=?', ('/a',)).fetchone())
                fs.db.conn.close()
                fs = VirtualFS(None, 'sqlite', db_path=str(Path(directory) / 'stats.sqlite'))
                relaunched = ScanStatistics(fs.db)
                self.assertEqual(relaunched.record('/a')['last'][0], [2, 2000000, 2])
                self.assertEqual(relaunched.record('/a')['session'][0], [0, 0, 0])
                self.assertEqual(relaunched.record('/a')['total'][0], [2, 2000000, 2])
                # Empty launches do not overwrite the last non-empty session.
                again = ScanStatistics(fs.db)
                self.assertEqual(again.record('/a')['last'][0], [2, 2000000, 2])
            finally:
                fs.db.conn.close()


class StatisticsViewTests(unittest.IsolatedAsyncioTestCase):
    async def test_keyboard_table_in_files_and_scan_switch_and_live_counts(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
            (Path(directory) / 'file').write_bytes(b'content')
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=pipe, output=DummyOutput())
            task = asyncio.create_task(browser.app.run_async(set_exception_handler=False))
            try:
                await asyncio.sleep(.05)
                pipe.send_text('\x13')
                await asyncio.sleep(.05)
                view = browser.screen_stack[-1][0]
                self.assertIsInstance(view, tui.ScanStatisticsView)
                self.assertIn('Current session', view.table.text)
                pipe.send_text('v')
                await asyncio.sleep(.05)
                self.assertEqual(browser.scan_statistics_scope, 'total')
                view.close()
                browser.toggle_scanner()
                scanner = browser.scanners[0]
                for _ in range(100):
                    if not any(scanner.controls.modes):
                        break
                    await asyncio.sleep(.02)
                await asyncio.sleep(.15)
                pipe.send_text('\x13')
                await asyncio.sleep(.05)
                self.assertIsInstance(browser.screen_stack[-1][0], tui.ScanStatisticsView)
                rows = browser.scan_statistics.record(scanner.storage_path)['current']
                self.assertEqual([row[0] for row in rows], [1, 1, 1])
                self.assertEqual([row[1] for row in rows], [7, 7, 7])
                browser.screen_stack[-1][0].close()
                browser.app.layout.focus(scanner.grid)
                pipe.send_text('L')
                await asyncio.sleep(.04)
                self.assertTrue(scanner.controls.loop)
                self.assertIn('L Loop ON', ''.join(text for _, text in scanner.controls_text()))
                pipe.send_text('L')
                await asyncio.sleep(.04)
                self.assertFalse(scanner.controls.loop)
            finally:
                browser.stop_scanner()
                for _ in range(100):
                    if not browser.scanners:
                        break
                    await asyncio.sleep(.02)
                browser.app.exit()
                await task
