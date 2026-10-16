"""Content-versioned JPEG thumbnail files; database linking belongs to the UI thread."""
from contextlib import contextmanager
from io import BytesIO
import shutil
import subprocess
import hashlib
import os
from pathlib import Path
import tempfile
import warnings

from PIL import Image, ImageOps
import pillow_avif  # Registers AVIF decoding for Pillow 10 / term-image.

SIZES = (128, 256)
JPEG_QUALITY = 60


IMAGE_SUFFIXES = {'.png', '.apng', '.jpg', '.jpeg', '.jpe', '.jfif', '.mpo',
                  '.gif', '.bmp', '.dib', '.webp', '.avif', '.avifs', '.tif', '.tiff',
                  '.ico', '.icns', '.cur', '.ppm', '.pgm', '.pbm', '.pnm', '.pfm',
                  '.jp2', '.j2k', '.jpc', '.jpf', '.jpx', '.j2c', '.tga', '.pcx',
                  '.dds', '.psd', '.qoi', '.sgi', '.rgb', '.rgba', '.bw', '.xbm', '.xpm'}
VIDEO_SUFFIXES = {'.mov', '.mp4', '.m4v', '.mkv', '.webm', '.avi', '.mpg', '.mpeg',
                  '.mpe', '.mts', '.m2ts', '.ts', '.wmv', '.asf', '.flv', '.3gp',
                  '.3g2', '.ogv', '.vob', '.mxf'}
AUDIO_SUFFIXES = {'.mp3', '.flac', '.wav', '.wave', '.m4a', '.aac', '.ogg', '.oga',
                  '.opus', '.wma', '.aiff', '.aif', '.alac', '.ape', '.amr', '.mid', '.midi'}
THUMBNAIL_SUFFIXES = IMAGE_SUFFIXES | VIDEO_SUFFIXES
MEDIA_SUFFIXES = THUMBNAIL_SUFFIXES | AUDIO_SUFFIXES


@contextmanager
def media_image(source, size):
    """Decode an image or a representative frame from the first 30 video frames."""
    if source.suffix.lower() in VIDEO_SUFFIXES:
        executable = shutil.which('ffmpeg')
        if not executable:
            raise ValueError('Video thumbnails require ffmpeg on PATH')
        try:
            result = subprocess.run(
                [executable, '-nostdin', '-v', 'error', '-threads', '1',
                 '-protocol_whitelist', 'file,pipe', '-i', str(source.resolve()),
                 '-map', '0:v:0', '-an', '-sn', '-dn', '-vf',
                 f'scale={size}:{size}:force_original_aspect_ratio=decrease,thumbnail=30',
                 '-frames:v', '1', '-threads', '1', '-f', 'image2pipe', '-vcodec', 'png', 'pipe:1'],
                capture_output=True, timeout=20, check=True)
        except (subprocess.SubprocessError, OSError) as exc:
            raise ValueError('Video frame unavailable') from exc
        with Image.open(BytesIO(result.stdout)) as image:
            yield image
    else:
        with Image.open(source) as image:
            yield image


def thumbnail(path, file_id, size=128, cache_root='.cache'):
    """Return a cache link after atomically publishing a bounded JPEG thumbnail."""
    if size not in SIZES:
        raise ValueError('Thumbnail size must be 128 or 256')
    source = Path(path)
    before = source.stat()
    fingerprint = [str(source.resolve()), before.st_size, before.st_mtime_ns,
                   before.st_ctime_ns]
    uid = hashlib.sha256(repr((file_id, fingerprint, size, JPEG_QUALITY)).encode()).hexdigest()
    destination = Path(cache_root) / f'image-{size}x{size}' / f'{uid}.jpg'
    valid_cache = False
    if destination.is_file():
        try:
            with Image.open(destination) as cached:
                valid_cache = (cached.format == 'JPEG' and max(cached.size) <= size)
                cached.verify()
        except (OSError, ValueError):
            valid_cache = False
    if not valid_cache:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with media_image(source, size) as image:
                if image.width * image.height > 20_000_000:
                    raise ValueError('Thumbnail source exceeds 20 megapixels')
                image = ImageOps.exif_transpose(image).convert('RGBA')
                image.thumbnail((size, size), Image.Resampling.LANCZOS)
                background = Image.new('RGBA', image.size, 'white')
                background.alpha_composite(image)
                image = background.convert('RGB')
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary = None
                try:
                    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix='.jpg', delete=False) as stream:
                        temporary = stream.name
                        image.save(stream, format='JPEG', quality=JPEG_QUALITY, optimize=True)
                    after = source.stat()
                    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                            after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                        raise ValueError('Thumbnail source changed during conversion')
                    os.replace(temporary, destination)
                finally:
                    if temporary and os.path.exists(temporary):
                        os.unlink(temporary)
    return {'id': uid, 'file_id': file_id, 'size': size,
            'path': str(destination.resolve()), 'source': fingerprint, 'quality': JPEG_QUALITY}
