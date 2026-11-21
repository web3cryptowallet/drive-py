"""Conversion arguments, persistence, real encoding and mouse-driven trim editing."""
import asyncio
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from prompt_toolkit.data_structures import Point
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType, MouseButton
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS
from vfs.conversion import ConversionOptions, ConversionQueue, NETWORKS, command, probe_media, video_files, parse_time

spec = importlib.util.spec_from_file_location('conversion_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


def sample(path):
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
                    'testsrc=size=64x36:rate=10:duration=1', '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p', '-threads', '1', str(path)], check=True, capture_output=True)


class ConversionTests(unittest.TestCase):
    def test_command_presets_validation_and_size_budget(self):
        self.assertAlmostEqual(parse_time('1:02.3'), 62.3)
        for codec in ('h264', 'h265'):
            options = ConversionOptions(codec=codec, resolution='1980', start=1, end=3, extra='-threads 1')
            args = command('/a file;touch no.mp4', '/export.mp4', options, 4)
            self.assertIn('libx264' if codec == 'h264' else 'libx265', args)
            self.assertEqual(args[args.index('-t') + 1], '2.000')
            self.assertIn('/a file;touch no.mp4', args)
        options = ConversionOptions.preset('instagram-25MB')
        args = command('/a.mp4', '/out.mp4', options, 60)
        self.assertIn('-b:v', args)
        self.assertIn('pad=1080:1920', args[args.index('-vf') + 1])
        for invalid in (replace(options, end=0), replace(options, start=float('nan')),
                        replace(options, extra='-y /source.mp4'), replace(options, extra='-i /other.mp4')):
            with self.assertRaises(ValueError):
                command('/a.mp4', '/out.mp4', invalid, 60)

    def test_database_restore_directory_remove_and_pause_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            fs = VirtualFS(None, 'sqlite', db_path=str(Path(directory) / 'db.sqlite'))
            queue = ConversionQueue(fs.db)
            try:
                queue.submit([str(Path(directory) / 'a.mp4')], ConversionOptions(start=.1, end=.7, codec='h265'))
                job = queue.jobs[0]
                job['status'] = 'running'
                queue.dirty = True
                queue.save()
                restored = ConversionQueue(fs.db)
                self.assertFalse(restored.enabled)
                self.assertEqual(restored.jobs[0]['status'], 'queued')
                self.assertEqual(restored.jobs[0]['options']['start'], .1)
                process = Mock()
                process.poll.return_value = None
                restored.process = process
                restored.current = restored.jobs[0]['id']
                restored.jobs[0]['status'] = 'running'
                restored.pause()
                if hasattr(signal, 'SIGSTOP'):
                    process.send_signal.assert_called_with(signal.SIGSTOP)
                restored.stop()
                process.terminate.assert_called()
                restored.process = None
                restored.remove(directory)
                self.assertFalse(restored.jobs)
                self.assertFalse(ConversionQueue(fs.db).jobs)
            finally:
                queue.close()
                fs.db.conn.close()

    def test_stop_during_probe_returns_job_to_queue(self):
        from threading import Event
        entered, release = Event(), Event()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.mp4'
            source.write_bytes(b'unchanged source')
            queue = ConversionQueue(VirtualFS({'files': {}}).db)
            other = Path(directory) / 'other.mp4'
            other.write_bytes(b'other')
            queue.submit([str(source), str(other)], ConversionOptions())
            next_id = queue.jobs[1]['id']
            def slow_probe(path):
                entered.set()
                release.wait(3)
                return 1
            with patch('vfs.conversion.probe_media', side_effect=slow_probe):
                queue.start()
                queue.tick()
                self.assertTrue(entered.wait(2))
                queue.convert_now(next_id)
                self.assertEqual(queue.jobs[0]['id'], next_id)
                self.assertTrue(queue.enabled)
                self.assertTrue(queue.cancel.is_set())
                queue.stop()
                release.set()
                queue.worker.join(3)
                queue.tick()
                self.assertEqual(queue.jobs[0]['status'], 'queued')
                self.assertFalse(queue.enabled)
                self.assertEqual(source.read_bytes(), b'unchanged source')
                self.assertFalse(list((source.parent / 'youtube-conv').glob('*.mp4')))
            queue.close()

    @unittest.skipUnless(hasattr(signal, 'SIGSTOP'), 'Requires POSIX suspend/resume')
    def test_real_pause_resume_ffmpeg_process(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.mp4'
            sample(source)
            queue = ConversionQueue(VirtualFS({'files': {}}).db)
            options = ConversionOptions.preset('instagram')
            options.extra = '-threads 1'
            queue.submit([str(source)], options)
            queue.start()
            queue.tick()
            try:
                deadline = time.monotonic() + 5
                while queue.process is None and time.monotonic() < deadline:
                    time.sleep(.005)
                self.assertIsNotNone(queue.process)
                process = queue.process
                queue.pause()
                time.sleep(.05)
                self.assertIsNone(process.poll())
                status = Path(f'/proc/{process.pid}/status')
                if status.exists():
                    self.assertIn('T (stopped)', status.read_text())
                queue.pause()
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    queue.tick()
                    if queue.jobs[0]['status'] in ('done', 'error'):
                        break
                    time.sleep(.02)
                self.assertEqual(queue.jobs[0]['status'], 'done', queue.jobs[0]['error'])
            finally:
                queue.close()

    def test_real_network_and_hevc_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.mp4'
            sample(source)
            for network in NETWORKS:
                options = ConversionOptions.preset(network)
                options.end = .3
                options.extra = '-threads 1'
                output = Path(directory) / f'{network}.mp4'
                result = subprocess.run(command(source, output, options, 1),
                                        capture_output=True, text=True, timeout=25)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertGreater(probe_media(output), 0)
                if options.max_mb:
                    self.assertLessEqual(output.stat().st_size, options.max_mb * 1000000)
                if network.startswith('instagram'):
                    data = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                           '-show_entries', 'stream=width,height', '-of', 'json', str(output)],
                                          capture_output=True, text=True, check=True)
                    video = json.loads(data.stdout)['streams'][0]
                    self.assertEqual((video['width'], video['height']), (1080, 1920))
            options = ConversionOptions(codec='h265', end=.3,
                                        extra='-threads 1 -x265-params pools=1:frame-threads=1')
            result = subprocess.run(command(source, Path(directory) / 'hevc.mp4', options, 1),
                                    capture_output=True, text=True, timeout=25)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_real_trim_encoding_cap_original_unchanged_and_no_output_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.mp4'
            sample(source)
            original = source.read_bytes()
            queue = ConversionQueue(VirtualFS({'files': {}}).db)
            try:
                options = ConversionOptions(start=.1, end=.6, max_mb=.1, extra='-threads 1')
                queue.submit([str(source)], options)
                queue.start()
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    queue.tick()
                    if queue.jobs[0]['status'] in ('done', 'error'):
                        break
                    time.sleep(.02)
                job = queue.jobs[0]
                self.assertEqual(job['status'], 'done', job['error'])
                output = Path(job['output'])
                self.assertEqual(output.parent, source.parent / 'youtube-conv')
                self.assertLessEqual(output.stat().st_size, 100000)
                self.assertAlmostEqual(probe_media(output), .5, delta=.12)
                self.assertEqual(source.read_bytes(), original)
                queue.convert_now(job['id'])
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    queue.tick()
                    if job['status'] in ('done', 'error'):
                        break
                    time.sleep(.02)
                self.assertEqual(job['status'], 'done', job['error'])
                self.assertNotEqual(job['output'], str(output))
                self.assertTrue(output.is_file())
                self.assertEqual(video_files(directory), [str(source)])
                queue.clear()
                self.assertTrue(output.is_file())
            finally:
                queue.close()


class ConversionUITests(unittest.IsolatedAsyncioTestCase):
    async def test_editor_seek_drag_submit_restore_and_queue_navigation(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
            source = Path(directory) / 'source.mp4'
            sample(source)
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory, input=pipe, output=DummyOutput())
            browser.image_previews = False
            browser.selected = next(i for i, row in enumerate(browser.rows) if row['name'] == 'source.mp4')
            task = asyncio.create_task(browser.app.run_async(set_exception_handler=False))
            try:
                pipe.send_text('\x05')  # Ctrl+E
                for _ in range(100):
                    if browser.screen_stack and browser.screen_stack[-1][0].duration:
                        break
                    await asyncio.sleep(.02)
                editor = browser.screen_stack[-1][0]
                self.assertIsInstance(editor, tui.ConversionView)
                self.assertGreater(editor.duration, 0)
                for _ in range(100):
                    if browser.video_area.lexer.image_lines:
                        break
                    await asyncio.sleep(.02)
                self.assertTrue(browser.video_area.lexer.image_lines, editor.message)
                with patch.object(editor, 'seek_frame') as seek:
                    browser.app.layout.focus(editor.times['start'])
                    editor.seek.width = 101
                    editor.seek.mouse_handler(MouseEvent(Point(20, 0), MouseEventType.MOUSE_UP, MouseButton.LEFT, frozenset()))
                    self.assertAlmostEqual(editor.value('start'), .2, places=2)
                    seek.assert_called()
                    editor.set_time('length', .3)
                    self.assertAlmostEqual(editor.value('end'), .5)
                    field = editor.times['end']
                    field.control.mouse_handler(MouseEvent(Point(1, 0), MouseEventType.MOUSE_DOWN, MouseButton.LEFT, frozenset()))
                    field.control.mouse_handler(MouseEvent(Point(3, 0), MouseEventType.MOUSE_MOVE, MouseButton.LEFT, frozenset()))
                    self.assertAlmostEqual(editor.value('end'), .7)
                    editor.reset()
                    self.assertEqual(editor.value('start'), 0)
                    self.assertAlmostEqual(editor.value('end'), 1)
                editor.options.codec = 'h265'
                self.assertTrue(editor.submit(), editor.message)
                self.assertEqual(len(browser.conversions.jobs), 1)
                job = browser.conversions.jobs[0]
                queue_view = tui.ConversionQueueView(browser)
                browser.push(queue_view)
                queue_view.edit()
                restored = browser.screen_stack[-1][0]
                self.assertIsInstance(restored, tui.ConversionView)
                self.assertEqual(restored.options.codec, 'h265')
                self.assertEqual(restored.job_id, job['id'])
                self.assertTrue(editor.closed)
                self.assertEqual(len(browser.screen_stack), 1)
                self.assertEqual(browser.current_name(), source.name)
                restored.close()
            finally:
                for screen, _ in list(browser.screen_stack):
                    if isinstance(screen, tui.ConversionView):
                        screen.close()
                browser.app.exit()
                await task
                browser.conversions.close()
