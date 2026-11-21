"""Persistent, sequential FFmpeg exports; source files are never overwritten."""
from dataclasses import dataclass, asdict
from pathlib import Path
from queue import Queue, Empty
from threading import Event, Thread
import json
import errno
import math
import os
import shlex
import signal
import shutil
import subprocess
import tempfile
import time
import uuid

from .adapter.sqlite import SQLiteDBAdapter
from .scanner import ScanStore
from .thumbnails import VIDEO_SUFFIXES

NETWORKS = ('youtube', 'instagram', 'threads', 'facebook', 'LQ', 'instagram-25MB', 'youtube-25MB')
RESOLUTIONS = ('orig', '1280', '1980', '4k', '1920')


def parse_time(text):
    parts = str(text).strip().split(':')
    if not 1 <= len(parts) <= 3:
        raise ValueError('Use seconds or HH:MM:SS.s')
    result = 0.
    for part in parts:
        value = float(part)
        if not math.isfinite(value) or value < 0:
            raise ValueError('Time must be finite and nonnegative')
        result = result * 60 + value
    return result


@dataclass
class ConversionOptions:
    network: str = 'youtube'
    codec: str = 'h264'
    quality: str = 'high'
    crf: int = 20
    resolution: str = 'orig'
    bitrate: int = 0  # video kbps; zero selects CRF
    max_mb: float = 0
    start: float = 0
    end: float | None = None
    extra: str = ''

    @classmethod
    def preset(cls, network):
        if network not in NETWORKS:
            raise ValueError('Unknown export preset')
        return cls(network=network, resolution='1280' if network == 'LQ' else
                   '1920' if network != 'youtube' else 'orig',
                   quality='low' if network == 'LQ' else 'high',
                   crf=30 if network == 'LQ' else 20,
                   max_mb=25 if network.endswith('25MB') else 0)


def probe_media(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                             'stream=codec_type,width,height,duration:format=duration',
                             '-of', 'json', str(path)], capture_output=True, text=True, timeout=20, check=True)
    info = json.loads(result.stdout)
    video = next((stream for stream in info.get('streams', []) if stream.get('codec_type') == 'video'), None)
    if video is None:
        raise ValueError('This file has no video stream')
    duration = float(info.get('format', {}).get('duration') or video.get('duration') or 0)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Cannot determine video duration')
    return duration


def video_files(path):
    path = Path(path).absolute()
    if path.is_file():
        if path.suffix.lower() not in VIDEO_SUFFIXES:
            raise ValueError('Select a video file or a directory')
        return [str(path)]
    if not path.is_dir():
        raise ValueError('Source is unavailable')
    result = []
    for root, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = sorted(name for name in dirs if name != 'youtube-conv')
        result.extend(str(Path(root) / name) for name in sorted(files)
                      if Path(name).suffix.lower() in VIDEO_SUFFIXES)
    return result


def extra_arguments(text):
    # Encoding options only: no additional inputs/outputs, command scripts or
    # overrides of queue-controlled trim, codecs, output paths and size budgeting.
    allowed = {'-preset', '-tune', '-profile:v', '-level:v', '-r', '-g', '-bf',
               '-threads', '-metadata', '-x264-params', '-x265-params', '-af', '-vf'}
    tokens = shlex.split(text)
    if len(tokens) % 2 or any(tokens[i] not in allowed for i in range(0, len(tokens), 2)):
        raise ValueError('Extra options require option/value pairs: ' + ', '.join(sorted(allowed)))
    return tokens


def command(source, output, options, duration, bitrate_override=None):
    o = options
    values = (o.start, o.end if o.end is not None else duration, o.max_mb, o.bitrate, o.crf)
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError('Options must be finite numbers')
    if o.codec not in ('h264', 'h265') or o.resolution not in RESOLUTIONS or o.network not in NETWORKS:
        raise ValueError('Unknown codec, resolution or network preset')
    end = min(duration, o.end if o.end is not None else duration)
    if not 0 <= o.start < end or o.max_mb < 0 or o.bitrate < 0 or not 0 <= o.crf <= 51:
        raise ValueError('Invalid trim, bitrate, size limit or CRF (0..51)')
    length = end - o.start
    budget = int((o.max_mb * 1_000_000 * 8 * .94 / length - 128000) / 1000) if o.max_mb else 0
    if o.max_mb and budget < 32:
        raise ValueError('Size target too small for this duration; shorten selection or increase MB')
    bitrate = bitrate_override or o.bitrate
    if budget:
        bitrate = min(bitrate, budget) if bitrate else budget
    args = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
            '-ss', f'{o.start:.3f}', '-i', str(source), '-t', f'{length:.3f}',
            '-map', '0:v:0', '-map', '0:a:0?', '-c:v', 'libx264' if o.codec == 'h264' else 'libx265',
            '-preset', 'medium', '-pix_fmt', 'yuv420p']
    if bitrate:
        args += ['-b:v', f'{bitrate}k', '-maxrate', f'{bitrate}k', '-bufsize', f'{bitrate * 2}k']
    else:
        args += ['-crf', str(o.crf)]
    filters = []
    if o.network.startswith('instagram') and o.resolution != 'orig':
        height = {'1280': 1280, '1980': 1980, '1920': 1920, '4k': 3840}[o.resolution]
        width = int(height * 9 / 16) // 2 * 2
        filters += [f'scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2',
                    f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2']
    elif o.resolution != 'orig':
        limit = {'1280': 1280, '1980': 1980, '1920': 1920, '4k': 3840}[o.resolution]
        filters += [f"scale='if(gte(iw,ih),min(iw,{limit}),-2)':'if(gte(iw,ih),-2,min(ih,{limit}))'"]
    else:
        filters += ['scale=trunc(iw/2)*2:trunc(ih/2)*2']
    extra = extra_arguments(o.extra)
    # A custom vf augments rather than replacing the preset geometry.
    if '-vf' in extra:
        index = extra.index('-vf')
        filters.insert(0, extra[index + 1])
        del extra[index:index + 2]
    args += ['-vf', ','.join(filters), '-c:a', 'aac', '-b:a', '128k', '-ar', '48000',
             '-movflags', '+faststart']
    if o.network.startswith('instagram') or o.network in ('threads', 'facebook'):
        args += ['-r', '30']
    if o.codec == 'h265':
        args += ['-tag:v', 'hvc1']
    return args + extra + ['-progress', 'pipe:1', '-f', 'mp4', str(output)]


class ConversionQueue:
    def __init__(self, db):
        self.db, self.store = db, ScanStore(db)
        if isinstance(db, SQLiteDBAdapter):
            db.conn.execute('CREATE TABLE IF NOT EXISTS conversion_queue (id TEXT PRIMARY KEY, value TEXT NOT NULL)')
            db.conn.commit()
            self.jobs = [json.loads(row[0]) for row in db.conn.execute('SELECT value FROM conversion_queue ORDER BY rowid')]
        else:
            self.jobs = list(self.store.get('conversion', 'queue', []))
        for job in self.jobs:
            if job['status'] in ('running', 'paused'):
                job.update(status='queued', progress=0)
        self.enabled = self.paused = False
        self.worker = self.process = self.current = None
        self.cancel = Event()
        self.events = Queue()
        self.dirty = True
        self.last_save = 0
        self.save()

    def save(self):
        if not self.dirty:
            return
        if isinstance(self.db, SQLiteDBAdapter):
            with self.db.write_transaction():
                self.db.conn.execute('DELETE FROM conversion_queue')
                self.db.conn.executemany('INSERT INTO conversion_queue VALUES (?,?)',
                                         [(job['id'], json.dumps(job)) for job in self.jobs])
        else:
            self.store.put('conversion', 'queue', self.jobs)
        self.dirty = False
        self.last_save = time.monotonic()

    def submit(self, sources, options, job_id=None):
        for source in sources:
            source = str(Path(source).absolute())
            job = next((item for item in self.jobs if item['id'] == job_id), None) if job_id else next(
                (item for item in self.jobs if item['source'] == source and item['status'] == 'queued'
                 and item['options']['network'] == options.network), None)
            if job and job['status'] in ('running', 'paused'):
                raise ValueError('Stop the active conversion before editing it')
            if job is None:
                job = {'id': uuid.uuid4().hex, 'source': source}
                self.jobs.append(job)
            job.update(options=asdict(options), status='queued', progress=0., error='', output='')
        self.dirty = True
        self.save()

    def remove(self, source):
        root = str(Path(source).absolute())
        removed = {job['id'] for job in self.jobs if job['source'] == root or job['source'].startswith(root + os.sep)}
        if self.current in removed:
            self.stop()
        self.jobs[:] = [job for job in self.jobs if job['id'] not in removed]
        self.dirty = True
        self.save()

    def clear(self):
        self.stop()
        self.jobs.clear()
        self.dirty = True
        self.save()

    def start(self):
        self.enabled = True
        if self.paused:
            self.pause()

    def stop(self):
        self.enabled = False
        self.cancel.set()
        process = self.process
        if process and process.poll() is None:
            try:
                if self.paused and hasattr(signal, 'SIGCONT'):
                    process.send_signal(signal.SIGCONT)
                process.terminate()
            except ProcessLookupError:
                pass
        self.paused = False

    def pause(self):
        self.paused = not self.paused
        process = self.process
        if process and process.poll() is None:
            try:
                if hasattr(signal, 'SIGSTOP'):
                    process.send_signal(signal.SIGSTOP if self.paused else signal.SIGCONT)
                elif self.paused:
                    self.cancel.set()
                    process.terminate()
            except ProcessLookupError:
                pass
        for job in self.jobs:
            if job['id'] == self.current and job['status'] in ('running', 'paused'):
                job['status'] = 'paused' if self.paused else 'running'
        self.dirty = True
        self.save()

    def convert_now(self, job_id):
        job = next(item for item in self.jobs if item['id'] == job_id)
        if self.current and self.current != job_id:
            self.stop()
        if job['status'] not in ('running', 'paused'):
            job.update(status='queued', progress=0, error='', output='')
            self.jobs.remove(job)
            self.jobs.insert(0, job)
        self.start()
        self.dirty = True
        self.save()

    def tick(self):
        while True:
            try:
                job_id, kind, value = self.events.get_nowait()
            except Empty:
                break
            job = next((item for item in self.jobs if item['id'] == job_id), None)
            if job is not None:
                if kind == 'progress':
                    job['progress'] = value
                else:
                    job.update(value)
                self.dirty = True
        if self.worker is not None and not self.worker.is_alive():
            self.worker.join()
            self.worker = self.current = None
        if self.enabled and not self.paused and self.worker is None:
            job = next((item for item in self.jobs if item['status'] == 'queued'), None)
            if job is not None:
                job.update(status='running', error='')
                self.current = job['id']
                self.cancel.clear()
                self.worker = Thread(target=self._convert, args=(dict(job),), daemon=True, name='drive-ffmpeg')
                self.worker.start()
                self.dirty = True
            else:
                self.enabled = False
        if self.dirty and time.monotonic() - self.last_save >= 1:
            self.save()

    def _convert(self, job):
        temporary = None
        try:
            source = Path(job['source'])
            duration = probe_media(source)
            options = ConversionOptions(**job['options'])
            output_dir = source.parent / 'youtube-conv'
            output = output_dir / f'{source.stem}-{options.network}-{job["id"][:8]}.mp4'
            # Validate all options before creating files.
            command(source, output, options, duration)
            output_dir.mkdir(exist_ok=True)
            temporary = output_dir / f'.{job["id"]}.partial.mp4'
            for attempt in range(3):
                if self.cancel.is_set():
                    raise InterruptedError()
                if temporary.exists():
                    temporary.unlink()
                args = command(source, temporary, options, duration,
                               bitrate_override=(max(32, int((options.max_mb * 1_000_000 * 8 * .94 /
                                   (min(options.end or duration, duration) - options.start) - 128000) / 1000 * .8 ** attempt))
                                                 if attempt and options.max_mb else None))
                with tempfile.TemporaryFile() as errors:
                    self.process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=errors, text=True)
                    if self.cancel.is_set():
                        self.process.terminate()
                    elif self.paused and hasattr(signal, 'SIGSTOP'):
                        self.process.send_signal(signal.SIGSTOP)
                    for line in self.process.stdout:
                        if line.startswith('out_time_us='):
                            try:
                                progress = float(line.split('=', 1)[1]) / 1_000_000 / (min(options.end or duration, duration) - options.start)
                                self.events.put((job['id'], 'progress', min(.99, max(0, progress))))
                            except ValueError:
                                pass
                    code = self.process.wait()
                    self.process.stdout.close()
                    errors.seek(0)
                    message = errors.read().decode('utf-8', errors='replace')[-3000:]
                if self.cancel.is_set():
                    raise InterruptedError()
                if code:
                    raise RuntimeError(message or f'FFmpeg exit {code}')
                if options.max_mb and temporary.stat().st_size > options.max_mb * 1_000_000:
                    if attempt < 2:
                        continue
                    raise ValueError('Output exceeds size cap after three attempts; reduce resolution/duration')
                # Atomic no-overwrite publication, even for repeated Convert now.
                if output.exists():
                    output = output_dir / f'{source.stem}-{options.network}-{uuid.uuid4().hex[:8]}.mp4'
                try:
                    os.link(temporary, output)
                except OSError as exc:
                    if exc.errno not in (errno.EXDEV, errno.EPERM, errno.ENOTSUP):
                        raise
                    # Shared/FAT filesystems may not implement hard links.
                    with output.open('xb') as target, temporary.open('rb') as data:
                        shutil.copyfileobj(data, target)
                temporary.unlink()
                self.events.put((job['id'], 'done', dict(status='done', progress=1., output=str(output), error='')))
                break
        except InterruptedError:
            self.events.put((job['id'], 'stopped', dict(status='queued', progress=0., error='Stopped; restart begins this job again')))
        except Exception as exc:
            self.events.put((job['id'], 'error', dict(status='error', error=str(exc))))
        finally:
            self.process = None
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def close(self):
        self.stop()
        if self.worker:
            self.worker.join(3)
            if self.worker.is_alive() and self.process:
                self.process.kill()
                self.worker.join(2)
        self.tick()
        self.save()
