"""Home and path command shortcuts through actual terminal input."""
# VERIFY HOME AND PATH COMMAND NAVIGATION [
import asyncio
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from prompt_toolkit.document import Document
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS, aliases

spec = importlib.util.spec_from_file_location('path_command_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class PathCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_immediate_directory_listing_and_persistent_selected_path_history(self):
        with tempfile.TemporaryDirectory() as folder, create_pipe_input() as pipe, \
                patch.dict(aliases, {}, clear=True), \
                patch.object(tui, 'HISTORY_PATH', Path(folder) / 'history.llog'):
            child = Path(folder) / 'pictures'
            child.mkdir()
            (child / 'cat.jpg').touch()
            fs = VirtualFS({'files': {}})
            b = tui.DriveBrowser(fs, path=folder, input=pipe, output=DummyOutput())
            task = asyncio.create_task(b.app.run_async(set_exception_handler=False))
            async def wait_for(predicate):
                for _ in range(100):
                    if predicate():
                        return
                    await asyncio.sleep(.02)
                self.fail('Path input did not update')
            try:
                await asyncio.sleep(.05)
                pipe.send_text('/')
                await wait_for(lambda: b.screen_stack and b.screen_stack[-1][0].matches)
                view = b.screen_stack[-1][0]
                self.assertEqual(view.path.text, '/')
                view.path.buffer.document = Document(folder + '/', len(folder) + 1)
                await wait_for(lambda: 'pictures/' in [c.text for c in view.matches])
                view.path.buffer.document = Document(str(child) + '/', len(str(child)) + 1)
                await wait_for(lambda: [c.text for c in view.matches] == ['cat.jpg'])
                pipe.send_text('\t')
                await wait_for(lambda: view.path.text.endswith('cat.jpg'))
                pipe.send_text('\r')
                await wait_for(lambda: not b.screen_stack)
                pipe.send_text('/')
                await wait_for(lambda: bool(b.screen_stack))
                view = b.screen_stack[-1][0]
                self.assertEqual(view.history_paths, [str(child / 'cat.jpg')])
                from vfs.action_history import ActionHistory
                saved = ActionHistory(Path(folder) / 'history.llog')
                self.assertEqual([e['path'] for e in saved.entries if e['action'] == 'path command'],
                                 [str(child / 'cat.jpg')])
                pipe.send_text('\x12\r')
                await wait_for(lambda: not b.screen_stack)
                self.assertEqual(b.current_name(), 'cat.jpg')
            finally:
                b.app.exit()
                await asyncio.wait_for(task, 3)

    async def test_partial_paths_suggest_and_tab_completes_without_navigation(self):
        with tempfile.TemporaryDirectory() as folder, create_pipe_input() as pipe, \
                patch.dict(aliases, {}, clear=True), \
                patch.object(tui, 'HISTORY_PATH', Path(folder) / 'history.llog'):
            (Path(folder) / 'pictures').mkdir()
            (Path(folder) / 'pictures' / 'cat.jpg').touch()
            fs = VirtualFS({'files': {}})
            b = tui.DriveBrowser(fs, path=folder, input=pipe, output=DummyOutput())
            task = asyncio.create_task(b.app.run_async(set_exception_handler=False))
            try:
                await asyncio.sleep(.05)
                pipe.send_text('/\x15' + folder + '/pic')
                for _ in range(100):
                    await asyncio.sleep(.02)
                    if b.screen_stack and b.screen_stack[-1][0].matches:
                        break
                view = b.screen_stack[-1][0]
                self.assertEqual([c.text for c in view.matches], ['pictures/'])
                self.assertEqual(fs.pwd(), folder)
                pipe.send_text('\t')
                for _ in range(100):
                    if view.path.text == folder + '/pictures/':
                        break
                    await asyncio.sleep(.02)
                self.assertEqual(view.path.text, folder + '/pictures/')
                view.path.text = 'cd pictures/ca'
                view.path.buffer.cursor_position = len(view.path.text)
                from prompt_toolkit.completion import CompleteEvent
                results = [c async for c in view.completer.get_completions_async(
                    view.path.buffer.document, CompleteEvent())]
                self.assertEqual([c.text for c in results], ['cat.jpg'])
                self.assertEqual(results[0].start_position, -2)
                b.show_notification('Test popup')
                await asyncio.sleep(.05)
                self.assertTrue(b.app.layout.has_focus(view.path))
                self.assertIsInstance(b.app.layout.container.children[0], tui.FloatContainer)
                self.assertEqual(b.clipboard_notice, 'Test popup')
            finally:
                b.app.exit()
                await asyncio.wait_for(task, 3)

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
                    self.assertEqual(browser.screen_stack[-1][0].path.text, '/')
                    await send('~')
                    self.assertEqual(browser.screen_stack[-1][0].path.text, str(home) + '/')
                    await send('\r')
                    self.assertEqual(fs.pwd(), str(home))
                    await send('/\r')
                    self.assertEqual(fs.pwd(), '/')
                    self.assertFalse(browser.screen_stack)
                    await send('/')
                    await send('\x15' + str(target))
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
                    await send('\x15cd bqjx\r')
                    self.assertEqual(fs.pwd(), str(target))
                    self.assertEqual(browser.action_history.entries[-1]['action'], 'chdir')
                finally:
                    browser.app.exit()
                    await asyncio.wait_for(task, 3)
# VERIFY HOME AND PATH COMMAND NAVIGATION ]
