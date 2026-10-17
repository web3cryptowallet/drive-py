"""On-demand button playback, frame delivery, worker failure and cleanup."""
import asyncio
import ctypes.util
import importlib.util
import os
from pathlib import Path
from queue import Queue
from prompt_toolkit.layout.screen import WritePosition
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.data_structures import Size
from vfs import VirtualFS
from vfs.video_preview import VideoPreview, video_rotation_filter

spec = importlib.util.spec_from_file_location('video_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


def abort_decoder(path, size, connection, library):
    os._exit(23)  # Simulate a fatal libmpv assertion, not a catchable exception.


class WorkerTests(unittest.TestCase):
    def test_missing_library_is_error_not_crash(self):
        player = VideoPreview('/missing.mov', (16, 16), lambda image: image)
        with patch.dict(sys.modules, {'mpv': None}):
            player.start()
            player.thread.join(2)
        self.assertFalse(player.thread.is_alive())
        self.assertEqual(player.events.get_nowait()[0], 'error')
        self.assertEqual(player.events.get_nowait()[0], 'end')
        player.seek(1)
        player.seek(12)
        self.assertEqual(player.seeks.get_nowait(), 12)

    def test_rotation_matrix_is_applied_explicitly(self):
        for angle, expected in [(-90, 'transpose=clock,'), (90, 'transpose=cclock,'),
                                (180, 'hflip,vflip,'), (0, '')]:
            result = SimpleNamespace(stdout='{"streams":[{"side_data_list":[{"rotation":' + str(angle) + '}]}]}')
            with patch('vfs.video_preview.subprocess.run', return_value=result):
                self.assertEqual(video_rotation_filter('/video.mov'), expected)
        with patch('vfs.video_preview.subprocess.run', side_effect=FileNotFoundError):
            self.assertEqual(video_rotation_filter('/video.mov'), '')

    @unittest.skipUnless(os.environ.get('DRIVE_TEST_VIDEO'), 'Set DRIVE_TEST_VIDEO for exact-file regression')
    def test_exact_portrait_file_without_native_abort(self):
        # Exercise production software decoding in an outer process; use silent
        # audio to make this check independent of a desktop audio server.
        code = r"""
import ctypes.util
import mpv
from vfs.video_preview import _decode
original = mpv.MPV.__init__
def init(self, **options):
    options['ao'] = 'null'
    original(self, **options)
mpv.MPV.__init__ = init
class Connection:
    frames = 0
    def poll(self): return False
    def send(self, event):
        if event[0] == 'frame': self.frames += 1
        if event[0] == 'error': raise RuntimeError(event[1])
    def close(self): pass
connection = Connection()
import os
_decode(os.environ['DRIVE_TEST_VIDEO'], (288, 208), connection, ctypes.util.find_library('mpv'))
assert connection.frames >= 20, connection.frames
print(connection.frames)
"""
        result = subprocess.run([sys.executable, '-c', code], capture_output=True,
                                text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreaterEqual(int(result.stdout.strip()), 20)

    def test_frame_serialization(self):
        tui.configure_image_terminal()
        frame = tui.serialize_video_frame(Image.new('RGB', (16, 16), 'red'), (4, 2))
        self.assertEqual(len(frame['lines']), 2)
        self.assertTrue(any('#ff0000' in style for row in frame['lines'] for style, _ in row))

    def test_native_payload_strips_layout_newlines_and_cursor_moves(self):
        raw = '\x1b[32C\n\x1b_Ga=T,z=731;FRAME\x1b\\\x1b[10C\n\x1b[0m'
        payload = tui.native_graphics_payload(raw)
        self.assertEqual(payload, '\x1b_Ga=T,z=731,C=1,q=2;FRAME\x1b\\')
        self.assertNotIn('\n', payload)
        self.assertNotIn('[32C', payload)
        self.assertEqual(tui.native_graphics_payload('no graphics'), '')

    def test_fragmented_graphics_replies_and_chunk_quiet_flags(self):
        from prompt_toolkit.input.vt100_parser import Vt100Parser
        keys = []
        parser = tui.KittyReplyFilter(Vt100Parser(keys.append))
        for chunk in ['a\x1b_', 'Gi=731;', 'OK\x1b', '\\b']:
            parser.feed(chunk)
        parser.flush()
        self.assertEqual([key.data for key in keys], ['a', 'b'])
        payload = tui.native_graphics_payload('\x1b_Ga=T,q=1,m=1;AAAA\x1b\\\x1b_Gq=1,m=0;BBBB\x1b\\')
        self.assertEqual(payload.count('q=2'), 2)
        self.assertNotIn('q=1', payload)

    def test_video_frames_are_replaced_before_previous_frame_deleted(self):
        browser = object.__new__(tui.DriveBrowser)
        browser.draw_grid_native = Mock()
        browser.screen_stack = []
        browser.video_path = '/clip.mov'
        browser.video_dimensions = (10, 2)
        browser.video_panel_visible = Mock(return_value=True)
        browser.native_visible = False
        browser.native_drawn = None
        browser.video_image_id = None
        window = Mock()
        window.render_info = SimpleNamespace(window_width=20, window_height=5,
                                             input_line_to_visible_line={i: i for i in range(5)})
        browser.video_area = SimpleNamespace(window=window)
        browser.native_preview = ('\x1b_Ga=T,z=731;FIRST\x1b\\', (10, 2), 0)
        output = Mock()
        browser.app = SimpleNamespace(output=output, is_done=False, renderer=SimpleNamespace(
            _last_screen=SimpleNamespace(visible_windows_to_write_positions={
                window: WritePosition(40, 2, 20, 5)})))
        browser.draw_native_preview(browser.app)
        first = output.write_raw.call_args.args[0]
        self.assertIn('i=731001', first)
        browser.native_preview = ('\x1b_Ga=T,z=731;SECOND\x1b\\', (10, 2), 0)
        browser.draw_native_preview(browser.app)
        second = output.write_raw.call_args.args[0]
        self.assertIn('i=731002', second)
        self.assertLess(second.index('SECOND'), second.index('d=I,i=731001'))
        self.assertNotIn('d=Z', second)

    def test_native_frame_fits_a_shorter_viewport(self):
        browser = object.__new__(tui.DriveBrowser)
        browser.draw_grid_native = Mock()
        browser.screen_stack = []
        browser.video_path = '/portrait.mov'
        browser.video_dimensions = (10, 20)
        browser.video_panel_visible = Mock(return_value=True)
        browser.native_visible = False
        browser.native_drawn = None
        browser.video_image_id = None
        window = Mock()
        window.render_info = SimpleNamespace(window_width=20, window_height=3,
                                             input_line_to_visible_line={0: 0, 1: 1, 2: 2})
        browser.video_area = SimpleNamespace(window=window)
        browser.native_preview = ('\x1b_Ga=T,c=10,r=20,z=731;FRAME\x1b\\', (10, 20), 0)
        output = Mock()
        browser.app = SimpleNamespace(output=output, is_done=False, renderer=SimpleNamespace(
            _last_screen=SimpleNamespace(visible_windows_to_write_positions={
                window: WritePosition(40, 2, 20, 3)})))
        browser.draw_native_preview(browser.app)
        self.assertTrue(browser.native_visible)
        self.assertIn('r=3', output.write_raw.call_args.args[0])
        self.assertEqual(browser.native_preview[1], (1, 3))

    @unittest.skipUnless(os.environ.get('DRIVE_TEST_LIBMPV'), 'Requires libmpv test library')
    def test_native_decoder_abort_is_contained(self):
        original = ctypes.util.find_library
        with patch('ctypes.util.find_library', side_effect=lambda name:
                   os.environ['DRIVE_TEST_LIBMPV'] if name == 'mpv' else original(name)):
            import mpv
        player = VideoPreview('/unused.mov', (40, 40), lambda image: {})
        with patch('vfs.video_preview._decode', abort_decoder):
            player.start()
            player.thread.join(5)
        self.assertFalse(player.thread.is_alive())
        errors = []
        while not player.events.empty():
            errors.append(player.events.get_nowait())
        self.assertTrue(any(kind == 'error' and '23' in message for kind, message in errors))

    @unittest.skipUnless(os.environ.get('DRIVE_TEST_LIBMPV') and shutil.which('ffmpeg'),
                         'Set DRIVE_TEST_LIBMPV to validate real software playback')
    def test_real_software_playback_and_cleanup(self):
        original = ctypes.util.find_library
        with patch('ctypes.util.find_library', side_effect=lambda name:
                   os.environ['DRIVE_TEST_LIBMPV'] if name == 'mpv' else original(name)):
            import mpv
        with tempfile.TemporaryDirectory() as directory:
            video = str(Path(directory) / 'test.mov')
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
                            'testsrc=size=90x160:rate=10:duration=1', '-c:v', 'mpeg4',
                            '-threads', '1', video], check=True, capture_output=True)
            rotated = str(Path(directory) / 'rotated.mov')
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', video, '-c', 'copy',
                            '-metadata:s:v:0', 'rotate=90', rotated], check=True, capture_output=True)
            for source, bounds in ((video, (160, 90)), (rotated, (95, 63))):
                player = VideoPreview(source, bounds, lambda image: {'dimensions': image.size})
                player.start()
                events = []
                try:
                    while True:
                        event = player.events.get(timeout=5)
                        events.append(event)
                        if event[0] == 'end':
                            break
                finally:
                    player.close()
                    player.thread.join(3)
                self.assertFalse(player.thread.is_alive())
                self.assertTrue(any(kind == 'frame' and value['dimensions'] == player.pixels
                                    for kind, value in events))
                self.assertNotIn('error', [event[0] for event in events])



class ControlsTests(unittest.IsolatedAsyncioTestCase):
    async def test_graphics_replies_do_not_navigate_or_toggle_previews(self):
        with create_pipe_input() as pipe:
            fs = VirtualFS({'files': {'/disk/sub/file.txt': {'MD5:a:1'}}})
            fs.enter('disk')
            fs.enter('sub')
            with patch.object(fs, 'start_in_current_directory'):
                browser = tui.DriveBrowser(fs, input=pipe, output=DummyOutput())
            task = asyncio.create_task(browser.app.run_async(set_exception_handler=False))
            try:
                await asyncio.sleep(.03)
                pipe.send_text('\x1b_Gi=731001;OK\x1b\\')
                pipe.send_text('\x1b_Gi=731002;ENOENT:missing image\x1b\\')
                await asyncio.sleep(.05)
                self.assertEqual(fs.pwd(), '/disk/sub')
                self.assertTrue(browser.image_previews)
                self.assertFalse(task.done())
                # Deliberate Escape still navigates, and i still toggles.
                pipe.send_text('i')
                await asyncio.sleep(.03)
                self.assertFalse(browser.image_previews)
                pipe.send_text('\x1b')
                await asyncio.sleep(.7)
                self.assertEqual(fs.pwd(), '/disk')
            finally:
                browser.app.exit()
                await task

    async def test_failed_video_poster_and_small_resize_keep_files_usable(self):
        class ResizableOutput(DummyOutput):
            rows = 24
            def get_size(self):
                return Size(rows=self.rows, columns=80)
        with create_pipe_input() as pipe:
            output = ResizableOutput()
            fs = VirtualFS({'files': {}})
            with patch.object(fs, 'start_in_current_directory'):
                browser = tui.DriveBrowser(fs, input=pipe, output=output)
            browser.auto_quick_view = True
            browser.rows = []
            for name in ('notes.txt', 'clip.mov'):
                node = SimpleNamespace(id='/disk/' + name, name=name, is_dir=False, size=10, info={})
                browser.rows.append({'name': name, 'node': node, 'indicator': 'green',
                                     'color': 'white', 'label': name, 'size': '10', 'dups': '0'})
            with patch.object(fs, 'get_full_info', return_value={'exists': True, 'size': 10}), \
                    patch.object(tui, 'prepare_grid_thumbnail', side_effect=RuntimeError('decoder failure')):
                task = asyncio.create_task(browser.app.run_async(set_exception_handler=False))
                try:
                    await asyncio.sleep(.03)
                    pipe.send_text('\x1b[B')
                    for _ in range(100):
                        if 'decoder failure' in browser.video_status:
                            break
                        await asyncio.sleep(.01)
                    self.assertIn('decoder failure', browser.video_status)
                    self.assertEqual(browser.selected, 1)
                    output.rows = 8
                    browser.app.invalidate()
                    await asyncio.sleep(.05)
                    self.assertFalse(task.done())
                    self.assertIn(browser.files, browser.app.renderer._last_screen.visible_windows_to_write_positions)
                    pipe.send_text('\x1b[A')
                    await asyncio.sleep(.04)
                    self.assertEqual(browser.selected, 0)
                    browser.app.layout.focus(browser.play_button)
                    browser.show_info(directory=True)
                    self.assertTrue(browser.app.layout.has_focus(browser.control))
                    pipe.send_text('q')
                    await asyncio.wait_for(task, timeout=2)
                finally:
                    if not task.done():
                        browser.app.exit()
                        await task

    async def test_select_video_loads_large_still_without_playback(self):
        with create_pipe_input() as pipe:
            fs = VirtualFS({'files': {}})
            with patch.object(fs, 'start_in_current_directory'):
                browser = tui.DriveBrowser(fs, input=pipe, output=DummyOutput())
            rows = []
            for name in ('notes.txt', 'clip.mov'):
                node = SimpleNamespace(id='/disk/' + name, name=name, is_dir=False, size=10, info={})
                rows.append({'name': name, 'node': node, 'indicator': 'green'})
            browser.rows = rows
            item = {'native': None, 'lines': [[('', 'POSTER')]],
                    'record': {'file_id': '/disk/clip.mov'}}
            with patch.object(fs, 'get_full_info', return_value={'exists': True, 'size': 10}), \
                    patch.object(tui, 'prepare_grid_thumbnail', return_value=item) as prepare, \
                    patch.object(tui, 'VideoPreview') as player:
                browser.auto_quick_view = True
                browser.select(1)
                for _ in range(100):
                    if 'POSTER' in browser.video_area.text:
                        break
                    await asyncio.sleep(.01)
                self.assertIn('POSTER', browser.video_area.text)
                prepare.assert_called_once()
                self.assertEqual(prepare.call_args.args[2], 256)
                player.assert_not_called()
                self.assertIsNone(browser.video_player)
                self.assertEqual(browser.video_status, 'Press Play')

    async def test_play_button_no_autoplay_frames_and_stop_on_view_change(self):
        with create_pipe_input() as pipe:
            fs = VirtualFS({'files': {}})
            with patch.object(fs, 'start_in_current_directory'):
                browser = tui.DriveBrowser(fs, input=pipe, output=DummyOutput())
            node = SimpleNamespace(id='/disk/video.mov', name='video.mov', is_dir=False,
                                   size=10, info={})
            browser.rows = [{'name': node.name, 'node': node, 'indicator': 'green',
                             'color': 'white', 'label': node.name, 'size': '10', 'dups': '0'}]
            fake = SimpleNamespace(events=Queue(), thread=Mock(), start=Mock(), close=Mock(), seek=Mock())
            with patch.object(fs, 'get_full_info', return_value={'exists': True, 'size': 10, 'dups': ['/first-copy.mov'], 'dups_states': [{'exists': True}]}), \
                    patch.object(tui, 'VideoPreview', return_value=fake) as factory:
                browser.open()
                factory.assert_not_called()
                task = asyncio.create_task(browser.app.run_async())
                try:
                    await asyncio.sleep(.03)
                    pipe.send_text('\t\t\r')  # files -> info -> Play, activate.
                    for _ in range(100):
                        if fake.start.called:
                            break
                        await asyncio.sleep(.01)
                    fake.start.assert_called_once()
                    factory.assert_called_once()
                    height = browser.video_dimensions[1]
                    fake.events.put(('frame', {'native': None,
                                             'lines': [[('', 'FRAME')] for _ in range(height)]}))
                    await asyncio.sleep(.06)
                    self.assertIn('FRAME', browser.video_area.text)
                    self.assertEqual(browser.video_status, 'Playing')
                    # Cursor movement must retain all playback/Info state,
                    # including the automatic quick-view and graphics triggers.
                    original = (browser.video_path, browser.video_metadata.text,
                                browser.info.text, browser.video_epoch,
                                browser.video_area.text, browser.info_paths.copy())
                    for suffix, auto, graphics in [('mov', False, False),
                                                   ('txt', True, False),
                                                   ('png', False, True)]:
                        other = SimpleNamespace(id='/disk/other.' + suffix,
                                                name='other.' + suffix, is_dir=False,
                                                size=20, info={})
                        browser.rows.append({'name': other.name, 'node': other,
                                             'indicator': 'green', 'color': 'white',
                                             'label': other.name, 'size': '20', 'dups': '0'})
                        browser.auto_quick_view = auto
                        browser.graphics_mode = graphics
                        browser.select(len(browser.rows) - 1)
                        self.assertEqual(browser.current_name(), other.name)
                        self.assertIs(browser.video_player, fake)
                        fake.close.assert_not_called()
                        self.assertEqual((browser.video_path, browser.video_metadata.text,
                                          browser.info.text, browser.video_epoch,
                                          browser.video_area.text, browser.info_paths), original)
                    browser.auto_quick_view = browser.graphics_mode = False
                    browser.video_duration = 30
                    browser.seek_video(12)
                    fake.seek.assert_called_with(12)
                    browser.seek_video(50, relative=True)
                    fake.seek.assert_called_with(30)
                    browser.seek_video(-50, relative=True)
                    fake.seek.assert_called_with(0)
                    screen = browser.app.renderer._last_screen
                    positions = screen.visible_windows_to_write_positions
                    video_position = positions[browser.video_area.window]
                    play_position = positions[browser.play_button.window]
                    self.assertGreaterEqual(play_position.ypos, video_position.ypos + video_position.height)
                    metadata_position = positions[browser.video_metadata.window]
                    duplicates_position = positions[browser.info.window]
                    self.assertIn('Modified:', browser.video_metadata.text)
                    self.assertIn('Other Duplicates', browser.info.text)
                    self.assertLess(metadata_position.ypos, video_position.ypos)
                    self.assertGreater(duplicates_position.ypos, play_position.ypos)
                    first_duplicate = next(iter(browser.info_paths))
                    self.assertIn(first_duplicate, browser.info.window.render_info.input_line_to_visible_line)
                    with patch.object(browser.app.output, 'get_size', return_value=Size(rows=22, columns=80)):
                        browser.app._on_resize()
                        await asyncio.sleep(.06)
                        self.assertIn(first_duplicate, browser.info.window.render_info.input_line_to_visible_line)
                        positions = browser.app.renderer._last_screen.visible_windows_to_write_positions
                        self.assertIn(browser.play_button.window, positions)
                        self.assertLessEqual(positions[browser.video_area.window].height, 5)
                    pipe.send_text('\t\r')  # Stop button.
                    await asyncio.sleep(.04)
                    fake.close.assert_called()
                    self.assertIsNone(browser.video_player)
                    browser.play_video()
                    browser.push(tui.HelpView(browser, 'Help', ['Help']))
                    self.assertIsNone(browser.video_player)
                finally:
                    browser.app.exit()
                    await task
