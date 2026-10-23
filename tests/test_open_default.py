"""Desktop opener keyboard integration without launching desktop apps."""
# IMPORT TEST OPEN DEFAULT DEPENDENCIES [
import asyncio
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS
# IMPORT TEST OPEN DEFAULT DEPENDENCIES ]
# PREPARE TEST OPEN DEFAULT SHARED STATE [
spec = importlib.util.spec_from_file_location('open_default_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)
# PREPARE TEST OPEN DEFAULT SHARED STATE ]
# VERIFY OPEN DEFAULT BEHAVIOR [
class OpenDefaultTests(unittest.IsolatedAsyncioTestCase):
    # VERIFY CTRL O AND LAUNCHER ERROR [
    async def test_ctrl_o_and_launcher_error(self):
        with create_pipe_input() as pipe:
            fs = VirtualFS({'files': {'/disk/a file;test': {'MD5:abc:3'}}})
            fs.enter('disk')
            with patch.object(fs, 'start_in_current_directory'):
                browser = tui.DriveBrowser(fs, input=pipe, output=DummyOutput())
            browser.refresh('a file;test')
            task = asyncio.create_task(browser.app.run_async())
            try:
                with patch('sys.platform', 'linux'), patch.object(tui, 'get_real_path', return_value='/tmp/a file;test'), patch.object(tui.os.path, 'exists', return_value=True), patch.object(tui.subprocess, 'run') as run:
                    await asyncio.sleep(.03)
                    pipe.send_text('\x0f')
                    for _ in range(100):
                        if run.called:
                            break
                        await asyncio.sleep(.01)
                    self.assertEqual(run.call_args.args[0], ['xdg-open', '/tmp/a file;test'])
                    self.assertFalse(browser.screen_stack)
                    run.side_effect = subprocess.CalledProcessError(3, ['xdg-open'])
                    pipe.send_text('\x0f')
                    for _ in range(100):
                        if browser.screen_stack:
                            break
                        await asyncio.sleep(.01)
                    self.assertTrue(browser.screen_stack)
                    self.assertEqual(fs.pwd(), '/disk')
            finally:
                browser.app.exit()
                await task
    # VERIFY CTRL O AND LAUNCHER ERROR ]
# VERIFY OPEN DEFAULT BEHAVIOR ]
