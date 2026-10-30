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
    async def test_path_action_shortcuts(self):
        with create_pipe_input() as pipe:
            fs = VirtualFS({'files': {'/disk/a file;test': {'MD5:abc:3'}}})
            fs.enter('disk')
            with patch.object(fs, 'start_in_current_directory'):
                browser = tui.DriveBrowser(fs, input=pipe, output=DummyOutput())
            browser.refresh('a file;test')
            task = asyncio.create_task(browser.app.run_async())
            try:
                with patch('sys.platform', 'linux'), patch.object(tui, 'get_real_path', return_value='/tmp/a file;test'), patch.object(tui.os.path, 'exists', return_value=True), patch.object(tui.os.path, 'isdir', return_value=False), patch.object(browser, 'copy_text') as copy, patch.object(tui.shutil, 'which', return_value='/usr/bin/xterm'), patch.object(tui.subprocess, 'Popen') as popen, patch.object(tui.subprocess, 'run') as run, patch('vfs.desktop.raise_x11_file_manager'):
                    await asyncio.sleep(.03)
                    for key, mock in [('\x19', copy), ('\x14', popen), ('\x06', run)]:
                        pipe.send_text(key)
                        for _ in range(100):
                            if mock.called:
                                break
                            await asyncio.sleep(.01)
                        self.assertTrue(mock.called)
                    copy.assert_called_once_with('/tmp/a file;test')
                    self.assertEqual(popen.call_args.kwargs['cwd'], '/tmp')
                    self.assertEqual(popen.call_args.args[0], ['x-terminal-emulator'])
                    show = next(c.args[0] for c in run.call_args_list if 'org.freedesktop.FileManager1.ShowItems' in c.args[0])
                    self.assertEqual(show[:3], ['gdbus', 'call', '--session'])
                    self.assertEqual(show[-2], '["file:///tmp/a%20file%3Btest"]')
                    self.assertIsInstance(browser.main_layout.container.children[0], tui.FloatContainer)
                    browser.app.layout.focus(browser.info)
                    browser.info_paths = {0: '/disk/duplicate'}
                    browser.info.buffer.cursor_position = 0
                    self.assertEqual(browser.selected_action_path(), '/disk/duplicate')
                    browser.info_paths = {}
                    self.assertEqual(browser.selected_action_path(), '/disk/a file;test')
            finally:
                browser.app.exit()
                await task

    # VERIFY CTRL O AND LAUNCHER ERROR ]
# VERIFY OPEN DEFAULT BEHAVIOR ]

# VERIFY PLATFORM REVEAL ARGUMENTS URI ENCODING AND PORTABLE FALLBACK [
class RevealFileTests(unittest.TestCase):
    def test_finder_reveals_file_as_a_single_argument(self):
        from vfs.desktop import reveal_file
        with patch('sys.platform', 'darwin'), patch('vfs.desktop.subprocess.run') as run:
            reveal_file('/tmp/a file;猫.png')
            self.assertEqual(run.call_args_list[0].args[0], ['open', '-R', '/tmp/a file;猫.png'])
            self.assertEqual(run.call_args_list[1].args[0], ['open', '-a', 'Finder'])

    def test_windows_explorer_selects_file(self):
        from vfs.desktop import reveal_file
        with patch('sys.platform', 'win32'), patch('vfs.desktop.subprocess.Popen') as popen:
            reveal_file('C:\\photos\\a file.png')
            self.assertEqual(popen.call_args.args[0], ['explorer.exe', '/select,C:\\photos\\a file.png'])

    def test_linux_showitems_and_manager_fallback(self):
        from vfs.desktop import reveal_file
        import json
        with patch('sys.platform', 'linux'), patch('vfs.desktop.shutil.which', return_value='/tool'), \
                patch('vfs.desktop.subprocess.run') as run, patch('vfs.desktop.subprocess.Popen') as popen, \
                patch('vfs.desktop.raise_x11_file_manager'):
            reveal_file('/tmp/a #猫.png')
            command = run.call_args_list[0].args[0]
            self.assertIn('org.freedesktop.FileManager1.ShowItems', command)
            self.assertEqual(json.loads(command[-2]), [Path('/tmp/a #猫.png').as_uri()])
            run.side_effect = subprocess.CalledProcessError(1, 'gdbus')
            reveal_file('/tmp/a #猫.png')
            self.assertEqual(popen.call_args.args[0], ['nautilus', '--select', '/tmp/a #猫.png'])
        with patch('sys.platform', 'linux'), patch('vfs.desktop.shutil.which', return_value=None), \
                patch('vfs.desktop.subprocess.run') as run:
            reveal_file('/tmp/a.png')
            self.assertEqual(run.call_args.args[0], ['xdg-open', '/tmp'])
# VERIFY PLATFORM REVEAL ARGUMENTS URI ENCODING AND PORTABLE FALLBACK ]

# VERIFY REVEAL REQUESTS FOREGROUND WITHOUT ACTIVATING A NEW HOME WINDOW [
class ManagerActivationTests(unittest.TestCase):
    def test_ubuntu_reveal_forwards_startup_id_and_raises_existing_window(self):
        import os
        from vfs.desktop import reveal_file
        with patch('sys.platform', 'linux'), patch('vfs.desktop.shutil.which', return_value='/gdbus'), \
                patch.dict(os.environ, {'DESKTOP_STARTUP_ID': 'startup', 'DISPLAY': ':test'}), \
                patch('vfs.desktop.subprocess.run') as run, patch('vfs.desktop.raise_x11_file_manager') as raise_window:
            reveal_file('/tmp/photos/image.png')
            self.assertEqual(run.call_args_list[0].args[0][-1], 'startup')
            raise_window.assert_called_once_with('/tmp/photos')
            self.assertFalse(any('org.freedesktop.Application.Activate' in c.args[0] for c in run.call_args_list))

    def test_x11_raises_matching_folder_without_changing_selection(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from vfs.desktop import raise_x11_file_manager
        from Xlib import X
        root = Mock()
        root.get_full_property.return_value = SimpleNamespace(value=[1, 2])
        connection = Mock()
        connection.screen.return_value.root = root
        other, matching = Mock(), Mock()
        for window, title in ((other, b'Other folder'), (matching, b'photos')):
            window.get_wm_class.return_value = ('org.gnome.Nautilus', 'org.gnome.Nautilus')
            window.get_full_property.return_value = SimpleNamespace(value=title)
        connection.create_resource_object.side_effect = lambda kind, xid: matching if xid == 1 else other
        with patch('Xlib.display.Display', return_value=connection), patch('Xlib.protocol.event.ClientMessage') as event:
            raise_x11_file_manager('/tmp/photos')
        self.assertIs(event.call_args.kwargs['window'], matching)
        self.assertEqual(event.call_args.kwargs['data'], (32, [2, X.CurrentTime, 0, 0, 0]))
        root.send_event.assert_called_once()
        connection.close.assert_called_once()
# VERIFY REVEAL REQUESTS FOREGROUND WITHOUT ACTIVATING A NEW HOME WINDOW ]
