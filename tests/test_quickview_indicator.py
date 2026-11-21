"""Quick View's gold spinner tracks pending and overlapping preview work."""
import asyncio
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS

spec = importlib.util.spec_from_file_location('indicator_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class QuickviewIndicatorTests(unittest.IsolatedAsyncioTestCase):
    async def test_frames_jobs_pending_preview_and_startup(self):
        with tempfile.TemporaryDirectory() as directory:
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=DummyInput(), output=DummyOutput())
            first = browser.begin_quickview()
            second = browser.begin_quickview()
            for index, frame in enumerate(('\\', '|', '/', '-')):
                with patch.object(tui.time, 'monotonic', return_value=index / 8):
                    self.assertEqual(browser.quickview_heading()[-1], ('fg:#ffd700', ' ' + frame))
            browser.end_quickview(first)
            self.assertTrue(browser.quickview_busy())
            browser.end_quickview(second)
            self.assertFalse(browser.quickview_busy())
            browser.cursor_refresh_pending = True
            browser.auto_quick_view = True
            self.assertTrue(browser.quickview_busy())
            browser.auto_quick_view = False
            self.assertFalse(browser.quickview_busy())
            browser.cursor_refresh_pending = False
            browser.video_status = 'Starting…'
            self.assertTrue(browser.quickview_busy())
            browser.video_status = 'Playing'
            self.assertFalse(browser.quickview_busy())
            if browser.quickview_animation_task:
                await browser.quickview_animation_task

    async def test_work_cleans_up_on_preview_error_and_poster_cancellation(self):
        with tempfile.TemporaryDirectory() as directory:
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=DummyInput(), output=DummyOutput())
            with patch.object(browser, '_show_info', side_effect=RuntimeError('failed')):
                with self.assertRaises(RuntimeError):
                    browser.show_info()
            self.assertFalse(browser.quickview_jobs)
            blocked = asyncio.Event()
            with patch.object(browser, '_load_video_poster', new=AsyncMock(side_effect=lambda *args: None)) as load:
                async def wait(*args):
                    await blocked.wait()
                load.side_effect = wait
                task = asyncio.create_task(browser.load_video_poster('/file', 0))
                await asyncio.sleep(0)
                self.assertTrue(browser.quickview_busy())
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            self.assertFalse(browser.quickview_jobs)
            if browser.quickview_animation_task:
                await browser.quickview_animation_task

    async def test_explicit_open_does_not_force_redraw_or_repeat_idle_preview(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as directory:
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=DummyInput(), output=DummyOutput())
            browser.auto_quick_view = True
            browser.note_cursor_motion(refresh=True)
            idle_task = browser.cursor_idle_task
            with patch.object(browser, '_show_info') as prepare, \
                    patch.object(browser.app, '_redraw') as redraw, \
                    patch.object(browser, 'sync_scan_symbols') as sync:
                browser.show_info()
                prepare.assert_called_once()
                redraw.assert_not_called()
                self.assertFalse(browser.cursor_refresh_pending)
                browser.cursor_idle_until = 0
                await idle_task
                prepare.assert_called_once()
                sync.assert_not_called()
            if browser.quickview_animation_task:
                await browser.quickview_animation_task
