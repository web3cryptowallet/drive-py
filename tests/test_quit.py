"""q exits the application even when a secondary view or text widget has focus."""
# IMPORT TEST QUIT DEPENDENCIES [
import asyncio
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS
# IMPORT TEST QUIT DEPENDENCIES ]
# PREPARE TEST QUIT SHARED STATE [
spec = importlib.util.spec_from_file_location('quit_app', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)
# PREPARE TEST QUIT SHARED STATE ]
# VERIFY QUIT BEHAVIOR [
class QuitTests(unittest.IsolatedAsyncioTestCase):
    async def test_unknown_key_notice_and_text_input(self):
        with create_pipe_input() as pipe:
            fs = VirtualFS({'files': {}})
            with patch.object(fs, 'start_in_current_directory'):
                browser = tui.DriveBrowser(fs, input=pipe, output=DummyOutput())
            task = asyncio.create_task(browser.app.run_async())
            try:
                await asyncio.sleep(.05)
                pipe.send_text('z')
                await asyncio.sleep(.08)
                self.assertEqual(browser.clipboard_notice, 'Unknown key z')
                self.assertTrue(browser.clipboard_notice_error)
                pipe.send_text('\x1bOP')
                await asyncio.sleep(.08)
                self.assertEqual(browser.clipboard_notice, 'Unknown key f1')
                epoch = browser.clipboard_notice_epoch
                pipe.send_text('n')
                await asyncio.sleep(.08)
                self.assertEqual(browser.clipboard_notice_epoch, epoch)
                browser.push(tui.PathCommandView(browser))
                pipe.send_text('z')
                await asyncio.sleep(.08)
                self.assertEqual(browser.clipboard_notice_epoch, epoch)
                notice = browser.begin_working('Working… loading folder')
                self.assertIsNotNone(notice)
                self.assertEqual(browser.clipboard_notice, 'Working… loading folder')
                self.assertFalse(browser.clipboard_notice_error)
                browser.end_working(notice)
                browser.show_notification('Another error', error=True)
                self.assertTrue(browser.clipboard_notice_error)
                browser.show_notification('Normal notice')
                self.assertFalse(browser.clipboard_notice_error)
            finally:
                browser.app.exit()
                await task

    # VERIFY Q FROM ALL VIEWS [
    async def test_q_from_all_views(self):
        for context in ['main', 'info', 'help', 'actions', 'scanner', 'scanner-input']:
            with self.subTest(context=context), create_pipe_input() as pipe:
                fs = VirtualFS({'files': {}})
                with patch.object(fs, 'start_in_current_directory'):
                    browser = tui.DriveBrowser(fs, input=pipe, output=DummyOutput())
                if context == 'info':
                    browser.app.layout.focus(browser.info)
                elif context == 'help':
                    browser.push(tui.HelpView(browser, 'Help', ['Help']))
                elif context == 'actions':
                    browser.push(tui.ActionsView(browser))
                elif context.startswith('scanner'):
                    screen = tui.ScannerView(browser, startup=False)
                    with patch.object(screen, 'start'):
                        browser.push(screen)
                    if context == 'scanner-input':
                        browser.app.layout.focus(screen.limit)
                task = asyncio.create_task(browser.app.run_async())
                try:
                    await asyncio.sleep(.03)
                    pipe.send_text('q')
                    await asyncio.wait_for(asyncio.shield(task), 2)
                finally:
                    if not task.done():
                        browser.app.exit()
                        await task
    # VERIFY Q FROM ALL VIEWS ]
# VERIFY QUIT BEHAVIOR ]
