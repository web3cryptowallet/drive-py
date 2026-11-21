"""Live status uses cached data, scrolls, and preserves background playback."""
import asyncio
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from prompt_toolkit.data_structures import Size
from prompt_toolkit.input import create_pipe_input, DummyInput
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS

spec = importlib.util.spec_from_file_location('status_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class ShortOutput(DummyOutput):
    def get_size(self):
        return Size(rows=18, columns=90)


class StatusTests(unittest.IsolatedAsyncioTestCase):
    async def test_f4_live_refresh_scroll_and_close_preserve_playback(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=pipe, output=ShortOutput())
            browser.stop_video = Mock()
            task = asyncio.create_task(browser.app.run_async(set_exception_handler=False))
            try:
                await asyncio.sleep(.04)
                pipe.send_text('\x1bOS')  # F4
                await asyncio.sleep(.05)
                view = browser.screen_stack[-1][0]
                self.assertIsInstance(view, tui.StatusView)
                browser.stop_video.assert_not_called()
                for label in ('Files', 'Quick View', 'Thumbnails', 'Scanning', 'Conversions', 'Activity and errors'):
                    self.assertIn(label, view.table.text)
                view.table.buffer.cursor_position = len(view.table.text)
                await asyncio.sleep(.04)
                self.assertGreater(view.table.window.vertical_scroll, 0)
                browser.clipboard_notice = 'new activity'
                await asyncio.sleep(.4)
                self.assertIn('new activity', view.table.text)
                self.assertGreater(view.table.window.vertical_scroll, 0)
                pipe.send_text('\x1bOS')
                await asyncio.sleep(.04)
                self.assertFalse(browser.screen_stack)
                self.assertTrue(view.task.cancelled())
                browser.stop_video.assert_not_called()
            finally:
                browser.app.exit()
                await task

    async def test_status_snapshot_reads_cached_state_only(self):
        with tempfile.TemporaryDirectory() as directory:
            fs = VirtualFS({'files': {}})
            browser = tui.DriveBrowser(fs, path=directory, input=DummyInput(), output=DummyOutput())
            browser.thumbnail_errors = 3
            browser.action_history.error = 'history write failed'
            with patch.object(fs, 'get_full_info', side_effect=AssertionError('disk stat')), \
                    patch.object(fs.db, 'get_children', side_effect=AssertionError('catalog traversal')):
                text = '\n'.join(browser.status_lines())
            self.assertIn('errors: 3', text)
            self.assertIn('history write failed', text)
            self.assertIn('No scan session', text)
            scanner = tui.ScannerView(browser, startup=False)
            scanner.projection_error = RuntimeError('projection failed')
            browser.scanners.append(scanner)
            with patch.object(fs.db, 'get_children', side_effect=AssertionError('catalog traversal')):
                text = '\n'.join(browser.status_lines())
            self.assertIn('Processing time:', text)
            self.assertIn('projection failed', text)
            self.assertIn('Directory size/count updates:', text)
