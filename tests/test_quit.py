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
    async def test_f1_context_help_and_f10_from_search(self):
        with create_pipe_input() as pipe:
            fs = VirtualFS({'files': {}})
            with patch.object(fs, 'start_in_current_directory'):
                browser = tui.DriveBrowser(fs, input=pipe, output=DummyOutput())
            task = asyncio.create_task(browser.app.run_async(set_exception_handler=False))
            try:
                await asyncio.sleep(.05)
                pipe.send_text('\x1bOP')  # F1
                await asyncio.sleep(.05)
                self.assertIsInstance(browser.screen_stack[-1][0], tui.HelpView)
                pipe.send_text('\x1bOP')
                await asyncio.sleep(.05)
                self.assertFalse(browser.screen_stack)
                scanner = tui.ScannerView(browser, startup=False)
                with patch.object(scanner, 'start'):
                    browser.push(scanner)
                pipe.send_text('\x1bOP')
                await asyncio.sleep(.05)
                view = browser.screen_stack[-1][0]
                self.assertIsInstance(view, tui.HelpView)
                self.assertEqual({entry.key for entry in view.entries},
                                 {entry.key for entry in tui.help_entries(tui.SCANNER_HELP, tui.plain_markup)})
                view.search_focus()
                pipe.send_text('\x1b[21~')  # F10, even with editable search focus
                await asyncio.wait_for(asyncio.shield(task), 2)
                self.assertIn('Quitting', browser.clipboard_notice)
            finally:
                if not task.done():
                    browser.app.exit()
                await task

    async def test_function_bar_replaced_by_scan_status(self):
        from types import SimpleNamespace
        from prompt_toolkit.utils import get_cwidth
        with create_pipe_input() as pipe:
            fs = VirtualFS({'files': {}})
            with patch.object(fs, 'start_in_current_directory'), \
                    patch.object(tui.DriveBrowser, 'scan_progress', return_value='SCAN STATUS'):
                browser = tui.DriveBrowser(fs, input=pipe, output=DummyOutput())
            task = asyncio.create_task(browser.app.run_async(set_exception_handler=False))
            def rendered():
                screen = browser.app.renderer.last_rendered_screen
                return '\n'.join(''.join(cell.char for _, cell in sorted(row.items()))
                                 for _, row in sorted(screen.data_buffer.items()))
            try:
                await asyncio.sleep(.05)
                self.assertIn('F1', rendered())
                self.assertIn('F10', rendered())
                for key in ('F2', 'F8', 'F9', 'F11', 'F12'):
                    self.assertNotIn(key, rendered())
                self.assertNotIn('SCAN STATUS', rendered())
                scanner = tui.ScannerView(browser, startup=False)
                browser.scanners.append(scanner)
                browser.app.invalidate()
                await asyncio.sleep(.05)
                self.assertIn('SCAN STATUS', rendered())
                self.assertNotIn('F10', rendered())
                browser.scanners.clear()
                browser.app.invalidate()
                await asyncio.sleep(.05)
                self.assertIn('F10', rendered())
                for width in (1, 24, 80, 120):
                    with patch.object(browser.app.output, 'get_size', return_value=SimpleNamespace(columns=width)):
                        text = ''.join(value for _, value in browser.function_keys())
                        self.assertEqual(get_cwidth(text), width)
                with patch.object(browser.app.output, 'get_size', return_value=SimpleNamespace(columns=160)):
                    text = ''.join(value for _, value in browser.function_keys())
                    for label in ('Help', 'Scan', 'Status', 'Refresh', 'Stats', 'Paths', 'Quit'):
                        self.assertIn(label, text)
                    key_fragments = [(style, value) for style, value in browser.function_keys()
                                     if value.startswith('F')]
                    self.assertEqual([value for _, value in key_fragments],
                                     ['F1', 'F3', 'F4', 'F5', 'F6', 'F7', 'F10'])
                    self.assertTrue(all('fg:#ffffff' in style and 'bg:#000000' in style
                                        for style, _ in key_fragments))
            finally:
                browser.scanners.clear()
                browser.app.exit()
                await task

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
                pipe.send_text('\x1bOQ')
                await asyncio.sleep(.08)
                self.assertEqual(browser.clipboard_notice, 'Unknown key f2')
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
