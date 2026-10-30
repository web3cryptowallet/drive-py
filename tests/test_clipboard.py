"""Clipboard utility failures, Unicode transport and real Ctrl+X dispatch."""
# VERIFY CLIPBOARD TRANSPORT WITHOUT MODIFYING THE DESKTOP CLIPBOARD [
import asyncio
import base64
import importlib.util
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS
from vfs.clipboard import copy_native, clipboard_escape


class ClipboardTransportTests(unittest.TestCase):
    def test_mac_uses_pbcopy_and_preserves_unicode(self):
        with patch.dict(os.environ, {}, clear=True), patch('sys.platform', 'darwin'), \
                patch('vfs.clipboard.shutil.which', return_value='/usr/bin/pbcopy'), \
                patch('vfs.clipboard.subprocess.run') as run:
            self.assertTrue(copy_native('猫\npath'))
            self.assertEqual(run.call_args.args[0], ['pbcopy'])
            self.assertEqual(run.call_args.kwargs['input'], '猫\npath')
            self.assertEqual(run.call_args.kwargs['timeout'], 3)
            self.assertEqual(run.call_args.kwargs['stdout'], subprocess.DEVNULL)

    def test_wayland_failure_tries_x11_and_timeout_reaches_fallback(self):
        with patch.dict(os.environ, {'WAYLAND_DISPLAY': 'test'}, clear=True), \
                patch('sys.platform', 'linux'), patch('vfs.clipboard.shutil.which', return_value='/tool'), \
                patch('vfs.clipboard.subprocess.run', side_effect=[subprocess.CalledProcessError(1, 'wl-copy'), None]) as run:
            self.assertTrue(copy_native('text'))
            self.assertEqual([c.args[0][0] for c in run.call_args_list], ['wl-copy', 'xclip'])
        with patch.dict(os.environ, {}, clear=True), patch('sys.platform', 'linux'), \
                patch('vfs.clipboard.shutil.which', return_value='/tool'), \
                patch('vfs.clipboard.subprocess.run', side_effect=subprocess.TimeoutExpired('tool', 3)):
            self.assertFalse(copy_native('text'))

    def test_ssh_uses_terminal_packet_and_tmux_preserves_payload(self):
        with patch.dict(os.environ, {'SSH_CONNECTION': 'test'}, clear=True), \
                patch('vfs.clipboard.subprocess.run') as run:
            self.assertFalse(copy_native('猫'))
            run.assert_not_called()
            expected = '\x1b]52;c;' + base64.b64encode('猫'.encode()).decode() + '\x07'
            self.assertEqual(clipboard_escape('猫'), expected)
            os.environ['TMUX'] = 'test'
            self.assertEqual(clipboard_escape('猫'), expected + '\x1bPtmux;' + expected.replace('\x1b', '\x1b\x1b') + '\x1b\\')

    def test_windows_uses_encoded_text_without_shell_interpolation(self):
        with patch.dict(os.environ, {}, clear=True), patch('sys.platform', 'win32'), \
                patch('vfs.clipboard.shutil.which', return_value='powershell.exe'), \
                patch('vfs.clipboard.subprocess.run') as run:
            self.assertTrue(copy_native("a'猫\n$()"))
            command = run.call_args.args[0]
            self.assertEqual(command[0], 'powershell.exe')
            self.assertIn(base64.b64encode("a'猫\n$()".encode()).decode(), command[-1])
            self.assertNotIn('shell', run.call_args.kwargs)
# VERIFY CLIPBOARD TRANSPORT WITHOUT MODIFYING THE DESKTOP CLIPBOARD ]
# VERIFY INFO COPY SHORTCUT AND TERMINAL FALLBACK IN A RUNNING APPLICATION [
class ClipboardInputTests(unittest.IsolatedAsyncioTestCase):
    async def test_ctrl_x_from_info_reaches_fallback(self):
        spec = importlib.util.spec_from_file_location('clipboard_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
        tui = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tui)
        fs = VirtualFS({'files': {}})
        with create_pipe_input() as pipe, patch.object(fs, 'start_in_current_directory'):
            output = DummyOutput()
            b = tui.DriveBrowser(fs, input=pipe, output=output)
            b.info.text = 'clipboard 猫\nsecond line'
            task = asyncio.create_task(b.app.run_async())
            try:
                await asyncio.sleep(.04)
                b.app.layout.focus(b.info)
                with patch('vfs.clipboard.copy_native', return_value=False) as native, \
                        patch.dict(os.environ, {}, clear=True), patch.object(output, 'write_raw') as write:
                    pipe.send_text('\x18')
                    expected = clipboard_escape(b.info.text)
                    for _ in range(100):
                        if any(expected == c.args[0] for c in write.call_args_list):
                            break
                        await asyncio.sleep(.01)
                    native.assert_called_once_with(b.info.text)
                    self.assertEqual(b.clipboard_notice, 'Clipboard request sent')
                    self.assertTrue(any(expected == c.args[0] for c in write.call_args_list))
            finally:
                b.app.exit()
                await task
# VERIFY INFO COPY SHORTCUT AND TERMINAL FALLBACK IN A RUNNING APPLICATION ]

# VERIFY NATIVE X11 FALLBACK SELECTION WITHOUT TOUCHING THE DESKTOP CLIPBOARD [
class ClipboardX11Tests(unittest.TestCase):
    def test_linux_without_clipboard_utilities_uses_x11(self):
        with patch.dict(os.environ, {'DISPLAY': ':test'}, clear=True), patch('sys.platform', 'linux'), \
                patch('vfs.clipboard.shutil.which', return_value=None), \
                patch('vfs.clipboard_x11.copy_x11', return_value=True) as copy:
            self.assertTrue(copy_native('/path/猫.png'))
            copy.assert_called_once_with('/path/猫.png')

    def test_x11_unicode_and_large_selection_roundtrip(self):
        import select
        import time
        import uuid
        from Xlib import X, display
        from vfs.clipboard_x11 import X11ClipboardOwner
        try:
            reader = display.Display()
        except Exception as exc:
            self.skipTest('X11 test display unavailable: ' + str(exc))
        # A private selection atom ensures this test never owns CLIPBOARD/PRIMARY.
        selection_name = '_DRIVE_CLIPBOARD_TEST_' + uuid.uuid4().hex
        try:
            for payload in ('/path/猫 image.png', '猫\n' * 20000):
                owner = X11ClipboardOwner(payload, selection_name)
                self.assertTrue(owner.start())
                window = reader.screen().root.create_window(0, 0, 1, 1, 0, X.CopyFromParent,
                    X.InputOnly, X.CopyFromParent, event_mask=X.PropertyChangeMask)
                prop = reader.intern_atom('_DRIVE_TEST_RESULT')
                utf8 = reader.intern_atom('UTF8_STRING')
                incr = reader.intern_atom('INCR')
                deadline = time.monotonic() + 3
                def next_event(kind):
                    while time.monotonic() < deadline:
                        if reader.pending_events():
                            event = reader.next_event()
                            if event.type == kind:
                                return event
                        else:
                            select.select([reader.fileno()], [], [], .02)
                    self.fail('X11 selection transfer timed out')
                try:
                    window.convert_selection(reader.intern_atom(selection_name), utf8, prop, X.CurrentTime)
                    reader.flush()
                    notify = next_event(X.SelectionNotify)
                    self.assertEqual(notify.property, prop)
                    value = window.get_full_property(prop, X.AnyPropertyType)
                    if value.property_type == incr:
                        chunks = []
                        window.delete_property(prop); reader.flush()
                        while True:
                            event = next_event(X.PropertyNotify)
                            if event.atom != prop or event.state != X.PropertyNewValue:
                                continue
                            value = window.get_full_property(prop, X.AnyPropertyType)
                            if value is None:
                                continue
                            chunk = bytes(value.value)
                            window.delete_property(prop); reader.flush()
                            if not chunk:
                                break
                            chunks.append(chunk)
                        actual = b''.join(chunks)
                    else:
                        actual = bytes(value.value)
                    self.assertEqual(actual.decode('utf-8'), payload)
                finally:
                    owner.stop.set(); owner.thread.join(timeout=1)
                    window.destroy(); reader.flush()
        finally:
            reader.close()
# VERIFY NATIVE X11 FALLBACK SELECTION WITHOUT TOUCHING THE DESKTOP CLIPBOARD ]

# VERIFY CTRL Y REACHES THE NATIVE UBUNTU FALLBACK [
class ClipboardPathInputTests(unittest.IsolatedAsyncioTestCase):
    async def test_ctrl_y_files_and_info_use_x11_without_terminal_escape(self):
        spec = importlib.util.spec_from_file_location('clipboard_path_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
        tui = importlib.util.module_from_spec(spec); spec.loader.exec_module(tui)
        fs = VirtualFS({'files': {'/disk/image.png': {'MD5:test:1'}}})
        fs.enter('disk')
        with create_pipe_input() as pipe, patch.object(fs, 'start_in_current_directory'):
            output = DummyOutput()
            b = tui.DriveBrowser(fs, input=pipe, output=output)
            b.refresh('image.png')
            task = asyncio.create_task(b.app.run_async())
            try:
                await asyncio.sleep(.04)
                with patch('sys.platform', 'linux'), patch.dict(os.environ, {'DISPLAY': ':test'}, clear=True), \
                        patch('vfs.clipboard.shutil.which', return_value=None), \
                        patch('vfs.clipboard_x11.copy_x11', return_value=True) as copy, \
                        patch.object(tui, 'get_real_path', return_value='/tmp/猫 path.png'), \
                        patch.object(output, 'write_raw') as write:
                    for index, focus in enumerate((b.control, b.info), start=1):
                        b.app.layout.focus(focus)
                        pipe.send_text('\x19')
                        for _ in range(100):
                            if copy.call_count == index:
                                break
                            await asyncio.sleep(.01)
                        self.assertEqual(copy.call_count, index)
                        copy.assert_called_with('/tmp/猫 path.png')
                        self.assertEqual(b.clipboard_notice, 'Copied to clipboard')
                    self.assertFalse(any('\x1b]52;' in call.args[0] for call in write.call_args_list))
            finally:
                b.app.exit(); await task
# VERIFY CTRL Y REACHES THE NATIVE UBUNTU FALLBACK ]
