"""Blocking shutdown stages report activity, elapsed waits, and completion."""
import importlib.util
import io
from pathlib import Path
from threading import Event
import tempfile
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch
from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS

spec = importlib.util.spec_from_file_location('shutdown_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class ShutdownProgressTests(unittest.TestCase):
    def test_blocking_stage_prints_heartbeat_and_completion(self):
        stream = io.StringIO()
        with patch.object(tui.sys, 'stderr', stream):
            result = tui.shutdown_step('Saving map', lambda: (time.sleep(1.1), 7)[1])
        self.assertEqual(result, 7)
        self.assertIn('Quitting: Saving map', stream.getvalue())
        self.assertIn('Still waiting: Saving map', stream.getvalue())
        self.assertIn('Done (', stream.getvalue())
        with patch.object(tui.sys, 'stderr', stream), self.assertRaises(ValueError):
            tui.shutdown_step('Bad save', lambda: (_ for _ in ()).throw(ValueError('bad')))
        self.assertIn('Failed: Bad save', stream.getvalue())

    def test_run_reports_joins_saves_and_owned_thumbnail_jobs(self):
        with tempfile.TemporaryDirectory() as directory:
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=DummyInput(), output=DummyOutput())
            thread = Mock()
            scanner = NS(path='/scan', stop=Event(), controls=NS(wake=Event()),
                         projection_wake=Event(), projection_thread=thread, worker=thread,
                         mode_thread=None, order_thread=None, model=NS(entries={'/file': None}),
                         drain_all=Mock(), save=Mock())
            browser.scanners = [scanner]
            browser.stop_video = Mock(side_effect=lambda: self.assertTrue(scanner.stop.is_set()))
            browser.conversions.close = Mock()
            browser.clear_native_preview = Mock()
            browser.clear_grid_native = Mock()
            browser.scan_statistics.save = Mock()
            browser.action_history.close_writer = Mock()
            executor = Mock()
            browser.thumbnail_executors = [executor]
            stream = io.StringIO()
            with patch.object(browser.app, 'run'), patch.object(tui.sys, 'stderr', stream):
                browser.run()
            executor.shutdown.assert_called_once_with(wait=True, cancel_futures=True)
            scanner.drain_all.assert_called_once()
            scanner.save.assert_called_once()
            browser.action_history.close_writer.assert_called_once()
            for label in ('Stopping media', 'thumbnail worker', 'scan worker',
                          'Saving scan map (1 paths)', 'Saving scan statistics',
                          'Flushing action history', 'cleanup complete'):
                self.assertIn(label, stream.getvalue())
