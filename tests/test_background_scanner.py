"""Scanner view visibility is independent of worker lifetime and navigation."""
import asyncio
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace as NS

from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS

spec = importlib.util.spec_from_file_location('background_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class BackgroundScannerTests(unittest.IsolatedAsyncioTestCase):
    def test_status_line_keeps_stats_with_stage_rotation(self):
        browser = object.__new__(tui.DriveBrowser)
        scanner = NS(closing=False, paused_modes=None,
                     controls=NS(modes=(True, True, True)),
                     engine=NS(current_mode=1), storage_path='/private/scope',
                     stats=NS(active=True, paths_per_second=25., mb_per_second=1.))
        browser.scan_statistics_scope = 'session'
        browser.scan_statistics = NS(record=lambda path: {'session': [[100, 4_000_000, 2.]]})
        browser.scanners = [scanner]
        for mode, frame, color in [(1, '\\', '#ffd700'), (2, '\\', '#af5fff'),
                                   (3, '◐', '#ffd700')]:
            scanner.engine.current_mode = mode
            with patch.object(tui.time, 'monotonic', return_value=0):
                fragments = browser.scan_progress()
                self.assertEqual(fragments[0], ('fg:' + color, frame + ' · '))
                text = ''.join(part for _, part in fragments)
                self.assertIn('100 files / 4.000 MB', text)
                self.assertIn('25 paths/s · 1.0 MB/s', text)
                self.assertNotIn('/private/scope', text)
                self.assertNotIn('Running', text)
                self.assertNotIn('checksums', text)
        scanner.paused_modes = (True, True, True)
        self.assertIn('25 paths/s', str(browser.scan_progress()))
        self.assertEqual(len(browser.scan_progress()), 1)
        scanner.paused_modes = None
        scanner.stats.active = False
        self.assertEqual(len(browser.scan_progress()), 1)
        browser.scanners = []
        self.assertEqual(browser.scan_progress(), '')

    def test_status_path_fits_terminal(self):
        browser = object.__new__(tui.DriveBrowser)
        browser.app = NS(output=NS())
        browser.scan_statistics_scope = 'session'
        browser.scan_statistics = NS(record=lambda path: {'session': []})
        stats = NS(active=False, paths_per_second=0., mb_per_second=0.,
                   path='/start/' + '界' * 100 + '/final.txt')
        browser.scanners = [NS(closing=False, paused_modes=None,
                               controls=NS(modes=(False, False, False)),
                               storage_path='/', stats=stats)]
        for width in (100, 120, 60, 10, 1):
            browser.app.output.get_size = lambda: NS(columns=width)
            text = ''.join(text for _, text in browser.scan_progress())
            self.assertLessEqual(tui.get_cwidth(text), width)
            self.assertNotIn('s:view', text)
            if width >= 100:
                self.assertIn('/start/', text)
                self.assertIn('...', text)
                self.assertTrue(text.endswith('/final.txt'))
        stats.path = '/short'
        browser.app.output.get_size = lambda: NS(columns=120)
        self.assertTrue(''.join(t for _, t in browser.scan_progress()).endswith('/short'))

    async def test_hide_navigate_reopen_pause_and_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'child').mkdir()
            (root / 'child' / 'video.mp4').write_bytes(b'video')
            fs = VirtualFS({'files': {}})
            browser = tui.DriveBrowser(fs, path=directory, input=DummyInput(), output=DummyOutput())
            browser.stop_video = Mock()
            scanner = tui.ScannerView(browser, startup=False)
            browser.push(scanner)
            worker = scanner.worker
            try:
                scanner.close()
                self.assertFalse(browser.screen_stack)
                self.assertFalse(scanner.stop.is_set())
                browser.go_path(str(root / 'child'))
                cwd = fs.pwd()
                for _ in range(100):
                    if scanner.stats.paths:
                        break
                    await asyncio.sleep(.02)
                self.assertGreater(scanner.stats.paths, 0)
                self.assertNotIn('Scan Running', str(browser.scan_progress()))
                browser.toggle_scanner()
                self.assertIs(browser.screen_stack[-1][0], scanner)
                self.assertIs(scanner.worker, worker)
                self.assertEqual(len(browser.scanners), 1)
                self.assertNotEqual(scanner.path, cwd)
                scanner.close()
                scanner.controls.modes = (True, False, False)
                browser.pause_scanner()
                await asyncio.sleep(.05)
                self.assertEqual(scanner.controls.modes, (False, False, False))
                self.assertIn('paths/s', str(browser.scan_progress()))
                browser.toggle_scanner()
                self.assertIs(browser.screen_stack[-1][0], scanner)
                scanner.close()
                browser.pause_scanner()
                await asyncio.sleep(.05)
                self.assertIsNone(scanner.paused_modes)
                # Stopping a hidden scan must preserve the browser directory/media.
                browser.stop_video.reset_mock()
                browser.stop_scanner()
                for _ in range(100):
                    if not browser.scanners:
                        break
                    await asyncio.sleep(.02)
                self.assertFalse(browser.scanners)
                self.assertFalse(worker.is_alive())
                self.assertEqual(fs.pwd(), cwd)
                browser.stop_video.assert_not_called()
            finally:
                if not scanner.closing:
                    scanner.stop_scanning()
                await asyncio.gather(*tuple(browser.app._background_tasks), return_exceptions=True)

    async def test_stop_under_help_returns_to_browser(self):
        with tempfile.TemporaryDirectory() as directory:
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=DummyInput(), output=DummyOutput())
            scanner = tui.ScannerView(browser, startup=False)
            browser.push(scanner)
            help_view = tui.HelpView(browser, 'Scan help', tui.SCANNER_HELP)
            browser.push(help_view)
            try:
                browser.stop_scanner()
                for _ in range(100):
                    if not browser.scanners:
                        break
                    await asyncio.sleep(.02)
                self.assertFalse(browser.scanners)
                self.assertEqual([screen for screen, _ in browser.screen_stack], [help_view])
                help_view.close()
                self.assertIs(browser.app.layout, browser.main_layout)
            finally:
                if not scanner.closing:
                    scanner.stop_scanning()
                await asyncio.gather(*tuple(browser.app._background_tasks), return_exceptions=True)

    async def test_completed_scan_reopens_fresh_in_current_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            child = root / 'child'
            child.mkdir()
            (child / 'file').write_bytes(b'data')
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=DummyInput(), output=DummyOutput())
            browser.toggle_scanner()
            old = browser.scanners[0]
            try:
                for _ in range(100):
                    if not any(old.controls.modes):
                        break
                    await asyncio.sleep(.02)
                self.assertFalse(any(old.controls.modes))
                old.close()
                browser.go_path(str(child))
                browser.toggle_scanner()
                restart = browser.scanner_restart_task
                browser.toggle_scanner()  # repeated s while saving cannot duplicate
                self.assertIs(browser.scanner_restart_task, restart)
                await restart
                fresh = browser.screen_stack[-1][0]
                self.assertIsNot(fresh, old)
                self.assertEqual(fresh.path, str(child))
                self.assertEqual(browser.scanners, [fresh])
                self.assertFalse(old.worker.is_alive())
                self.assertIsNot(fresh.worker, old.worker)
                for _ in range(100):
                    if not any(fresh.controls.modes):
                        break
                    await asyncio.sleep(.02)
                self.assertEqual(fresh.engine.mode_counts[0][0], 1)
                # Reopening the same completed path also creates a fresh session.
                fresh.close()
                browser.toggle_scanner()
                await browser.scanner_restart_task
                self.assertIsNot(browser.scanners[0], fresh)
                self.assertEqual(browser.scanners[0].path, str(child))
            finally:
                for scanner in tuple(browser.scanners):
                    scanner.stop_scanning()
                await asyncio.gather(*tuple(browser.app._background_tasks), return_exceptions=True)

    async def test_hidden_scan_updates_directory_size_without_listing_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            child = Path(directory) / 'child'
            child.mkdir()
            (child / 'file').write_bytes(b'x' * 5000)
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=DummyInput(), output=DummyOutput())
            browser.toggle_scanner()
            view = browser.scanners[0]
            view.close()
            browser.refresh = Mock()
            try:
                row = next(row for row in browser.rows if row['name'] == 'child')
                for _ in range(100):
                    if view.directory_sizes.get(str(child)) == 5000 and not view.directory_size_dirty:
                        break
                    await asyncio.sleep(.02)
                self.assertEqual(view.directory_sizes[str(child)], 5000)
                self.assertEqual(row['size'], tui.format_size(5000, 0).strip())
                browser.refresh.assert_not_called()
            finally:
                await view.stop_scanning()
                await asyncio.gather(*tuple(browser.app._background_tasks), return_exceptions=True)
