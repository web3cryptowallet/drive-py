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
