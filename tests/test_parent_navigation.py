"""Main Backspace goes to parent even while the read-only info pane is focused."""
# IMPORT TEST PARENT NAVIGATION DEPENDENCIES [
import asyncio
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS
# IMPORT TEST PARENT NAVIGATION DEPENDENCIES ]
# PREPARE TEST PARENT NAVIGATION SHARED STATE [
spec = importlib.util.spec_from_file_location('parent_navigation', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)
# PREPARE TEST PARENT NAVIGATION SHARED STATE ]
# VERIFY PARENT NAVIGATION BEHAVIOR [
class ParentNavigationTests(unittest.IsolatedAsyncioTestCase):
    # VERIFY BACKSPACE FROM FILES AND INFO RESTORES SELECTION [
    async def test_backspace_from_files_and_info_restores_selection(self):
        for focus in ['files', 'info']:
            for key in ['\x7f', '\x08']:  # Terminal Backspace encodings.
                with self.subTest(focus=focus, key=repr(key)), create_pipe_input() as pipe:
                    fs = VirtualFS({'files': {'/disk/child/file': {'MD5:abc:3'}}})
                    fs.enter('disk')
                    with patch.object(fs, 'start_in_current_directory'):
                        browser = tui.DriveBrowser(fs, input=pipe, output=DummyOutput())
                    browser.refresh('child')
                    browser.open()
                    self.assertEqual(fs.pwd(), '/disk/child')
                    if focus == 'info':
                        browser.app.layout.focus(browser.info)
                    task = asyncio.create_task(browser.app.run_async())
                    try:
                        await asyncio.sleep(.03)
                        pipe.send_text(key)
                        for _ in range(50):
                            if fs.pwd() == '/disk':
                                break
                            await asyncio.sleep(.01)
                        self.assertEqual(fs.pwd(), '/disk')
                        self.assertEqual(browser.current_name(), 'child')
                        self.assertTrue(browser.app.layout.has_focus(browser.control))
                        browser.push(tui.HelpView(browser, 'Help', ['Help']))
                        pipe.send_text(key)
                        await asyncio.sleep(.03)
                        self.assertEqual(fs.pwd(), '/disk')
                        self.assertTrue(browser.screen_stack)
                    finally:
                        browser.app.exit()
                        await task
    # VERIFY BACKSPACE FROM FILES AND INFO RESTORES SELECTION ]
# VERIFY PARENT NAVIGATION BEHAVIOR ]
