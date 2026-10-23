"""Audio-only decoder commands and shared UI playback controls."""
# IMPORT TEST AUDIO PLAYBACK DEPENDENCIES [
import asyncio
import ctypes.util
import shutil
import subprocess
import sys
import tempfile
import importlib.util
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS
from vfs.video_preview import _decode_audio
# IMPORT TEST AUDIO PLAYBACK DEPENDENCIES ]
# PREPARE TEST AUDIO PLAYBACK SHARED STATE [
spec = importlib.util.spec_from_file_location('audio_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)
# PREPARE TEST AUDIO PLAYBACK SHARED STATE ]
# VERIFY AUDIO DECODER BEHAVIOR [
class AudioDecoderTests(unittest.TestCase):
    # VERIFY REAL MP3 DECODE TO EOF WITH NULL AUDIO OUTPUT [
    @unittest.skipUnless(ctypes.util.find_library('mpv') and shutil.which('ffmpeg'),
                         'Requires libmpv and ffmpeg')
    def test_real_mp3_decode_to_eof_with_null_audio_output(self):
        code = """
import ctypes.util
import sys
import mpv
from vfs.video_preview import _decode_audio
original = mpv.MPV.__init__
def init(self, **options):
    options['ao'] = 'null'
    original(self, **options)
mpv.MPV.__init__ = init
class Connection:
    events = []
    pending = True
    def poll(self): return self.pending
    def recv(self):
        self.pending = False
        return ('seek', 0.2)
    def send(self, event): self.events.append(event)
    def close(self): pass
connection = Connection()
_decode_audio(sys.argv[1], (2, 2), connection, ctypes.util.find_library('mpv'))
print(connection.events, flush=True)
assert not any(kind == 'error' for kind, _ in connection.events), connection.events
progress = [value for kind, value in connection.events if kind == 'progress']
assert progress and progress[-1][1] > 0, connection.events
assert connection.events[-1][0] == 'end', connection.events
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'tone.mp3'
            subprocess.run([shutil.which('ffmpeg'), '-nostdin', '-v', 'error', '-f', 'lavfi',
                            '-i', 'sine=frequency=440:duration=0.7', '-c:a', 'libmp3lame', str(path)],
                           check=True, capture_output=True, timeout=20)
            result = subprocess.run([sys.executable, '-c', code, str(path)],
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
    # VERIFY REAL MP3 DECODE TO EOF WITH NULL AUDIO OUTPUT ]
    # VERIFY AUDIO PROGRESS SEEK EOF AND NO VIDEO RENDERER [
    def test_audio_progress_seek_eof_and_no_video_renderer(self):
        player = SimpleNamespace(play=Mock(), command=Mock(), terminate=Mock(),
                                 time_pos=2., duration=10., idle_active=True)
        mpv = SimpleNamespace(MPV=Mock(return_value=player))
        connection = Mock()
        connection.poll.side_effect = [True, False]
        connection.recv.return_value = ('seek', 2.)
        with patch.dict('sys.modules', mpv=mpv), patch('vfs.video_preview.os.dup2'):
            _decode_audio('/song.mp3', (2, 2), connection, 'libmpv.so')
        self.assertEqual(mpv.MPV.call_args.kwargs['vid'], 'no')
        self.assertEqual(mpv.MPV.call_args.kwargs['vo'], 'null')
        player.play.assert_called_once_with('/song.mp3')
        player.command.assert_called_once_with('seek', 2., 'absolute+exact')
        self.assertEqual(connection.send.call_args_list[0].args[0], ('progress', (2., 10.)))
        self.assertEqual(connection.send.call_args_list[-1].args[0], ('end', None))
        player.terminate.assert_called_once()
        connection.close.assert_called_once()
    # VERIFY AUDIO PROGRESS SEEK EOF AND NO VIDEO RENDERER ]
    # VERIFY AUDIO STOP AND STARTUP ERROR CLEANUP [
    def test_audio_stop_and_startup_error_cleanup(self):
        player = Mock()
        connection = Mock()
        connection.poll.return_value = True
        connection.recv.return_value = ('stop', None)
        with patch.dict('sys.modules', mpv=SimpleNamespace(MPV=Mock(return_value=player))), \
                patch('vfs.video_preview.os.dup2'):
            _decode_audio('/song.mp3', (2, 2), connection, 'libmpv.so')
        player.terminate.assert_called_once()
        connection.send.assert_called_once_with(('end', None))
        connection = Mock()
        with patch.dict('sys.modules', mpv=SimpleNamespace(MPV=Mock(side_effect=RuntimeError('no output')))), \
                patch('vfs.video_preview.os.dup2'):
            _decode_audio('/song.mp3', (2, 2), connection, 'libmpv.so')
        self.assertIn('no output', connection.send.call_args_list[0].args[0][1])
        connection.close.assert_called_once()
    # VERIFY AUDIO STOP AND STARTUP ERROR CLEANUP ]
# VERIFY AUDIO DECODER BEHAVIOR ]
# VERIFY AUDIO UI BEHAVIOR [
class AudioUITests(unittest.IsolatedAsyncioTestCase):
    # VERIFY MP3 EXPLICIT PLAY PROGRESS SEEK STOP [
    async def test_mp3_explicit_play_progress_seek_stop(self):
        with create_pipe_input() as pipe:
            fs = VirtualFS({'files': {}})
            with patch.object(fs, 'start_in_current_directory'):
                browser = tui.DriveBrowser(fs, input=pipe, output=DummyOutput())
            node = SimpleNamespace(id='/song.mp3', name='song.mp3', size=10, is_dir=False, info={})
            browser.rows = [dict(node=node, name=node.name, label=node.name, size='10', dups='0', color='white', indicator='green')]
            fake = SimpleNamespace(events=Queue(), thread=Mock(), start=Mock(), close=Mock(), seek=Mock())
            with patch.object(fs, 'get_full_info', return_value={'exists': True, 'size': 10}), \
                    patch.object(tui, 'VideoPreview', return_value=fake) as factory, \
                    patch.object(browser, 'load_video_poster', new=Mock(side_effect=AssertionError('audio has no poster'))):
                browser.open()
                self.assertTrue(browser.audio_selected())
                factory.assert_not_called()
                task = asyncio.create_task(browser.app.run_async())
                try:
                    await asyncio.sleep(.05)
                    pipe.send_text('\t\t\r')
                    for _ in range(100):
                        if fake.start.called:
                            break
                        await asyncio.sleep(.01)
                    fake.start.assert_called_once()
                    self.assertEqual(factory.call_args.args[0], '/song.mp3')
                    self.assertNotIn(browser.video_area.window, browser.app.renderer._last_screen.visible_windows_to_write_positions)
                    fake.events.put(('progress', (3., 20.)))
                    await asyncio.sleep(.06)
                    self.assertEqual((browser.video_position, browser.video_duration), (3., 20.))
                    self.assertEqual(browser.video_status, 'Playing')
                    browser.seek_video(7)
                    fake.seek.assert_called_once_with(7)
                    pipe.send_text('\t\r')
                    await asyncio.sleep(.05)
                    fake.close.assert_called()
                    self.assertIsNone(browser.video_player)
                    resumed = SimpleNamespace(events=Queue(), thread=Mock(), start=Mock(), close=Mock(), seek=Mock())
                    factory.return_value = resumed
                    pipe.send_text('p')
                    for _ in range(100):
                        if resumed.start.called:
                            break
                        await asyncio.sleep(.01)
                    resumed.start.assert_called_once()
                    resumed.seek.assert_called_once_with(7)
                    pipe.send_text('p')
                    await asyncio.sleep(.05)
                    resumed.close.assert_called()
                    self.assertIsNone(browser.video_player)
                    # EOF must restart at zero instead of seeking straight to EOF.
                    browser.video_status = 'Finished'
                    browser.video_position = browser.video_duration = 20.
                    replay = SimpleNamespace(events=Queue(), thread=Mock(), start=Mock(), close=Mock(), seek=Mock())
                    factory.return_value = replay
                    pipe.send_text('p')
                    for _ in range(100):
                        if replay.start.called:
                            break
                        await asyncio.sleep(.01)
                    replay.start.assert_called_once()
                    replay.seek.assert_not_called()
                    self.assertEqual(browser.video_position, 0.)
                    browser.stop_video()
                finally:
                    browser.app.exit()
                    await task
    # VERIFY MP3 EXPLICIT PLAY PROGRESS SEEK STOP ]
# VERIFY AUDIO UI BEHAVIOR ]
