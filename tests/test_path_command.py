"""Home and path command shortcuts through actual terminal input."""
# VERIFY HOME AND PATH COMMAND NAVIGATION [
import asyncio
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS, aliases

spec = importlib.util.spec_from_file_location('path_command_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class PathCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_home_root_input_cancel_relative_and_unavailable(self):
        with tempfile.TemporaryDirectory() as folder, create_pipe_input() as pipe, patch.dict(aliases, {}, clear=True):
            root = Path(folder)
            home = root / 'home'
            target = home / 'bqjx'
            target.mkdir(parents=True)
            expanduser = tui.os.path.expanduser
            with patch.object(tui.os.path, 'expanduser', side_effect=lambda p: str(home) if p == '~' else expanduser(p)), patch.object(tui, 'HISTORY_PATH', root / 'history.llog'):
                fs = VirtualFS({'files': {}})
                browser = tui.DriveBrowser(fs, path=folder, input=pipe, output=DummyOutput())
                task = asyncio.create_task(browser.app.run_async())
                async def send(text):
                    pipe.send_text(text)
                    await asyncio.sleep(.1)
                try:
                    await send('~')
                    self.assertEqual(fs.pwd(), str(home))
                    await send('/')
                    self.assertIsInstance(browser.screen_stack[-1][0], tui.PathCommandView)
                    await send('\r')
                    self.assertEqual(fs.pwd(), '/')
                    self.assertFalse(browser.screen_stack)
                    await send('/')
                    await send(str(target))
                    self.assertEqual(browser.screen_stack[-1][0].path.text, str(target))
                    await send('\r')
                    self.assertEqual(fs.pwd(), str(target))
                    await send('/')
                    await send('missing/path\r')
                    self.assertIn('unavailable', browser.screen_stack[-1][0].message.text)
                    self.assertEqual(fs.pwd(), str(target))
                    await send('\x1b')
                    await asyncio.sleep(.5)
                    self.assertFalse(browser.screen_stack)
                    await send('~')
                    await send('/')
                    await send('cd bqjx\r')
                    self.assertEqual(fs.pwd(), str(target))
                    self.assertEqual(browser.action_history.entries[-1]['action'], 'chdir')
                finally:
                    browser.app.exit()
                    await task
# VERIFY HOME AND PATH COMMAND NAVIGATION ]
