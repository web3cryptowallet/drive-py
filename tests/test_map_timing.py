"""Per-map processing timers, duration labels and expert selection counts."""
import importlib.util
from pathlib import Path
from queue import Queue
from threading import Event
import tempfile
import unittest
from unittest.mock import patch

from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS
from vfs.scanner import DriveScanner, ScanControls, ScanStore, ScanTiming

spec = importlib.util.spec_from_file_location('map_timing', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class MapTimingTests(unittest.TestCase):
    def test_duration_formats(self):
        for seconds, expected in [(0, '0:00'), (1, '0:01'), (59, '0:59'),
                (72, '1:12'), (3682, '1:01:22'), (90671, '25:11:11'),
                (172800, '48:00:00')]:
            self.assertEqual(tui.format_elapsed(seconds), expected)

    def test_timer_sums_mode_processing_and_excludes_pause(self):
        clock = [10.]
        with patch('vfs.scanner.time.monotonic', side_effect=lambda: clock[0]):
            timer = ScanTiming((1., 2., 3.))
            timer.switch(1)
            clock[0] += 2
            self.assertEqual(timer.snapshot(), (1, (3., 2., 3.)))
            timer.switch(3)
            clock[0] += 4
            timer.switch(0)
            clock[0] += 100
            self.assertEqual(timer.snapshot(), (0, (3., 2., 7.)))
            timer.switch(3)
            clock[0] += 1
            self.assertEqual(timer.snapshot(), (3, (3., 2., 8.)))

    def test_worker_attributes_modes_and_stops_timer_on_error(self):
        fs = VirtualFS({'files': {}})
        clock = [10.]
        controls = ScanControls((True, True, True))
        with patch('vfs.scanner.time.monotonic', side_effect=lambda: clock[0]):
            scanner = DriveScanner(fs.db, '/', Queue(), Event(), controls=controls)

            def discover(db, mode=1, **kwargs):
                clock[0] += 2 if mode == 1 else 3

            def verify(db, mode):
                clock[0] += 4 if mode == 2 else 5

            with patch.object(scanner, 'discover', side_effect=discover), patch.object(
                    scanner, 'verify_pending', side_effect=verify):
                scanner.scan_once(fs.db)
            self.assertEqual(scanner.timing.snapshot(), (0, (2., 7., 5.)))
            clock[0] += 100
            self.assertEqual(scanner.timing.snapshot(), (0, (2., 7., 5.)))
            with patch.object(scanner, 'discover', side_effect=RuntimeError('failed')):
                with self.assertRaises(RuntimeError):
                    scanner.scan_once(fs.db)
            self.assertEqual(scanner.timing.snapshot()[0], 0)

    def test_counts_and_timing_save_reopen_and_reset(self):
        for backend in ['memory', 'sqlite']:
            with self.subTest(backend=backend), tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
                data = {'files': {'/disk/file': {'MD5:abc:3'}}}
                if backend == 'sqlite':
                    fs = VirtualFS(None, 'sqlite', db_path=str(Path(directory) / 'cache.sqlite'))
                    fs.update(data)
                else:
                    fs = VirtualFS(data)
                fs.enter('disk')
                try:
                    with patch.object(fs, 'start_in_current_directory'):
                        browser = tui.DriveBrowser(fs, input=pipe, output=DummyOutput())
                    screen = tui.ScannerView(browser, startup=False)
                    screen.controls.heavy_order = 'expert'
                    screen.controls.modes = (False, False, True)
                    screen.controls.expert_queue.extend([('a',), ('b',), ('c',)])
                    screen.update_expert()
                    self.assertEqual(screen.expert_selected_count, 3)
                    screen.controls.claim_expert()
                    screen.update_expert()
                    self.assertEqual(screen.expert_selected_count, 3)
                    screen.controls.finish_expert()
                    screen.update_expert()
                    self.assertEqual(screen.expert_selected_count, 2)
                    clock = [100.]
                    with patch('vfs.scanner.time.monotonic', side_effect=lambda: clock[0]):
                        screen.timing = ScanTiming((1., 60., 3600.))
                        screen.timing.switch(3)
                        clock[0] += 82
                        text = screen.stats_text()
                        self.assertEqual(len(text.splitlines()), 2)
                        self.assertEqual(text.splitlines()[1], 'Last path: /disk')
                        controls_text = ''.join(value for _, value in screen.controls_text())
                        self.assertTrue(controls_text.startswith('1 Lite '))
                        self.assertIn('2 Medium ', controls_text)
                        self.assertIn('3 Heavy ', controls_text)
                        self.assertTrue(controls_text.endswith(
                            'Expert selected 2 buckets · 1:22 / 1:02:23'))
                        self.assertNotIn('elapsed', controls_text)
                        self.assertNotIn('Map total', controls_text)
                        self.assertNotIn('1:01:22', text)
                        screen.save()
                        self.assertEqual(ScanStore(fs.db).get('map', '/disk')['mode_elapsed'], [1., 60., 3682.])
                    if backend == 'sqlite':
                        fs.db.conn.close()
                        fs = VirtualFS(None, 'sqlite', db_path=str(Path(directory) / 'cache.sqlite'))
                        fs.enter('disk')
                        browser.vfs = fs
                    reopened = tui.ScannerView(browser, startup=False)
                    self.assertEqual(reopened.timing.snapshot(), (0, (1., 60., 3682.)))
                    browser.reset_current_map()
                    reset = tui.ScannerView(browser, startup=False)
                    self.assertEqual(reset.timing.snapshot(), (0, (0., 0., 0.)))
                finally:
                    if backend == 'sqlite':
                        fs.db.conn.close()
