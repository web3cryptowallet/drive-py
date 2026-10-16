"""On-demand libmpv software frames; no terminal or database access from worker."""
import ctypes
from queue import Queue, Empty, Full
from threading import Event, Thread
import time


class VideoPreview:
    def __init__(self, path, pixels, serialize):
        self.path, self.pixels, self.serialize = path, pixels, serialize
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
        player = context = None
        try:
            import mpv
            from PIL import Image
            # python-mpv 1.0 exposes the render API but omits its software params.
            # These parameter IDs/types are defined by libmpv's render.h ABI.
            mpv.MpvRenderParam.TYPES.update({
                'sw_size': (17, ctypes.c_void_p), 'sw_format': (18, str),
                'sw_stride': (19, ctypes.c_void_p), 'sw_pointer': (20, ctypes.c_void_p)})
            width, height = self.pixels
            dimensions = (ctypes.c_int * 2)(width, height)
            stride = ctypes.c_size_t(width * 4)
            pixels = ctypes.create_string_buffer(width * height * 4)
            player = mpv.MPV(vo='libmpv', idle=True, keep_open=False,
                             input_default_bindings=False, input_vo_keyboard=False,
                             osc=False, config=False, load_scripts=False)
            context = mpv.MpvRenderContext(player, 'sw')
            player.play(self.path)
            started = False
            deadline = time.monotonic() + 15
            while not self.stop.wait(.1):
                try:
                    target = self.seeks.get_nowait()
                except Empty:
                    target = None
                if target is not None:
                    player.command('seek', target, 'absolute+exact')
                if context.update():
                    context.render(sw_size=ctypes.cast(dimensions, ctypes.c_void_p),
                                   sw_format='rgb0',
                                   sw_stride=ctypes.cast(ctypes.pointer(stride), ctypes.c_void_p),
                                   sw_pointer=ctypes.cast(pixels, ctypes.c_void_p))
                    image = Image.frombytes('RGB', (width, height), pixels.raw, 'raw', 'RGBX')
                    frame = self.serialize(image)
                    frame['_position'] = float(player.time_pos or 0)
                    frame['_duration'] = float(player.duration or 0)
                    self.publish('frame', frame)
                    started = True
                if started and player.idle_active:
                    break
                if not started and time.monotonic() > deadline:
                    raise RuntimeError('No video frame received within 15 seconds')
        except (Exception, SystemExit) as exc:
            self.publish('error', f'Video preview unavailable: {exc}')
        finally:
            try:
                if context is not None:
                    context.free()
            finally:
                if player is not None:
                    player.terminate()
            self.publish('end')
