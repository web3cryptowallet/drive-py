"""Process-isolated libmpv decoding and bounded terminal-frame delivery."""
import ctypes
import multiprocessing
import os
import json
import subprocess
from queue import Queue, Empty, Full
from threading import Event, Thread
import time


def video_rotation_filter(path):
    """Read the display matrix without libmpv's failing software auto-rotation."""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
             '-show_entries', 'stream_side_data=rotation:stream_tags=rotate',
             '-of', 'json', path], capture_output=True, text=True, timeout=10, check=True)
        streams = json.loads(result.stdout).get('streams', [])
        if not streams:
            return ''
        stream = streams[0]
        rotation = next((item['rotation'] for item in stream.get('side_data_list', [])
                         if 'rotation' in item), stream.get('tags', {}).get('rotate', 0))
        # Display-matrix angles use the opposite direction to FFmpeg transpose.
        angle = round(float(rotation)) % 360
        return {90: 'transpose=cclock,', 180: 'hflip,vflip,',
                270: 'transpose=clock,'}.get(angle, '')
    except (OSError, ValueError, subprocess.SubprocessError):
        return ''


def _decode(path, size, connection, library):
    # A native assertion must not kill the TUI or write into its terminal.
    with open(os.devnull, 'w') as sink:
        os.dup2(sink.fileno(), 2)
    player = context = None
    try:
        import ctypes.util
        original = ctypes.util.find_library
        ctypes.util.find_library = lambda name: library if name == 'mpv' else original(name)
        try:
            import mpv
        finally:
            ctypes.util.find_library = original
        mpv.MpvRenderParam.TYPES.update({
            'sw_size': (17, ctypes.c_void_p), 'sw_format': (18, str),
            'sw_stride': (19, ctypes.c_void_p), 'sw_pointer': (20, ctypes.c_void_p)})
        width, height = size
        dimensions = (ctypes.c_int * 2)(width, height)
        stride = ctypes.c_size_t(width * 4)
        pixels = ctypes.create_string_buffer(width * height * 4)
        rotation_filter = video_rotation_filter(path)
        player = mpv.MPV(vo='libmpv', idle=True, keep_open=False,
                         input_default_bindings=False, input_vo_keyboard=False,
                         osc=False, config=False, load_scripts=False, hwdec='no', vd_lavc_dr=False, video_rotate='no',
                         vf=f'lavfi=[{rotation_filter}scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1]')
        context = mpv.MpvRenderContext(player, 'sw')
        player.play(path)
        started = False
        deadline = time.monotonic() + 15
        while True:
            while connection.poll():
                command, value = connection.recv()
                if command == 'stop':
                    return
                if command == 'seek':
                    player.command('seek', value, 'absolute+exact')
            if context.update():
                context.render(sw_size=ctypes.cast(dimensions, ctypes.c_void_p),
                               sw_format='rgb0',
                               sw_stride=ctypes.cast(ctypes.pointer(stride), ctypes.c_void_p),
                               sw_pointer=ctypes.cast(pixels, ctypes.c_void_p))
                connection.send(('frame', (pixels.raw, size, float(player.time_pos or 0),
                                           float(player.duration or 0))))
                started = True
            if started and player.idle_active:
                break
            if not started and time.monotonic() > deadline:
                raise RuntimeError('No video frame received within 15 seconds')
            time.sleep(.1)
    except (Exception, SystemExit) as exc:
        try:
            connection.send(('error', f'Video preview unavailable: {exc}'))
        except (BrokenPipeError, EOFError, OSError):
            pass
    finally:
        try:
            if context is not None:
                context.free()
        finally:
            if player is not None:
                player.terminate()
        try:
            connection.send(('end', None))
        except (BrokenPipeError, EOFError, OSError):
            pass
        connection.close()


class VideoPreview:
    def __init__(self, path, pixels, serialize):
        self.path, self.serialize = path, serialize
        self.pixels = tuple(max(2, int(value) // 2 * 2) for value in pixels)
        self.stop = Event()
        self.seeks = Queue(maxsize=1)
        self.events = Queue(maxsize=2)
        self.thread = Thread(target=self.run, name='drive-video-preview', daemon=True)

    def start(self):
        self.thread.start()

    def publish(self, kind, value=None):
        while True:
            try:
                self.events.put_nowait((kind, value))
                return
            except Full:
                try:
                    self.events.get_nowait()
                except Empty:
                    pass

    def seek(self, seconds):
        try:
            self.seeks.get_nowait()
        except Empty:
            pass
        self.seeks.put_nowait(max(0., float(seconds)))

    def close(self):
        self.stop.set()

    def run(self):
        process = connection = None
        try:
            import mpv
            from PIL import Image
            spawn = multiprocessing.get_context('spawn')
            connection, child = spawn.Pipe()
            process = spawn.Process(target=_decode,
                                    args=(self.path, self.pixels, child, mpv.backend._name), daemon=True)
            process.start()
            child.close()
            ended = False
            while not self.stop.is_set():
                try:
                    target = self.seeks.get_nowait()
                    connection.send(('seek', target))
                except Empty:
                    pass
                if connection.poll(.05):
                    try:
                        kind, value = connection.recv()
                    except EOFError:
                        break
                    if kind == 'frame':
                        raw, size, position, duration = value
                        frame = self.serialize(Image.frombytes('RGB', size, raw, 'raw', 'RGBX'))
                        frame['_position'], frame['_duration'] = position, duration
                        self.publish('frame', frame)
                    elif kind == 'error':
                        self.publish(kind, value)
                    elif kind == 'end':
                        ended = True
                        break
                elif not process.is_alive():
                    break
            if not ended and not self.stop.is_set():
                process.join(timeout=.2)
                self.publish('error', f'Video decoder stopped unexpectedly (exit {process.exitcode})')
        except (Exception, SystemExit) as exc:
            self.publish('error', f'Video preview unavailable: {exc}')
        finally:
            if process is not None and process.pid is not None:
                try:
                    if process.is_alive() and connection:
                        connection.send(('stop', None))
                except (BrokenPipeError, EOFError, OSError):
                    pass
                process.join(timeout=1)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=1)
                process.close()
            if connection is not None:
                connection.close()
            self.publish('end')
