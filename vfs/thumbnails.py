"""Content-versioned JPEG thumbnail files; database linking belongs to the UI thread."""
# IMPORT THUMBNAILS DEPENDENCIES [
from contextlib import contextmanager
from io import BytesIO
import shutil
import subprocess
import hashlib
import json
import os
from pathlib import Path
import tempfile
import warnings

from PIL import Image, ImageOps
import pillow_avif  # Registers AVIF decoding for Pillow 10 / term-image.
from pillow_heif import register_heif_opener

register_heif_opener()
# IMPORT THUMBNAILS DEPENDENCIES ]
# PREPARE THUMBNAILS SHARED STATE [
SIZES = (128, 256)
JPEG_QUALITY = 60
PREFIX_BYTES = 1024 * 1024


IMAGE_SUFFIXES = {'.png', '.apng', '.jpg', '.jpeg', '.jpe', '.jfif', '.mpo',
                  '.gif', '.bmp', '.dib', '.webp', '.web', '.heic', '.heif', '.heics', '.heifs', '.hif', '.avif', '.avifs', '.tif', '.tiff',
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
# PREPARE THUMBNAILS SHARED STATE ]
# DECODE AN IMAGE OR A REPRESENTATIVE FRAME FROM THE FIRST 30 VIDEO FRAMES [
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
# DECODE AN IMAGE OR A REPRESENTATIVE FRAME FROM THE FIRST 30 VIDEO FRAMES ]
# RETURN A CACHE LINK AFTER ATOMICALLY PUBLISHING A BOUNDED JPEG THUMBNAIL [
def thumbnail(path, file_id, size=128, cache_root='.cache', cache_only=False, cached_record=None):
    """Return a cache link after atomically publishing a bounded JPEG thumbnail."""
    if size not in SIZES:
        raise ValueError('Thumbnail size must be 128 or 256')
    source = Path(path)
    before = source.stat()
    fingerprint = [str(source.resolve()), before.st_size, before.st_mtime_ns,
                   before.st_ctime_ns]
    # A saved prefix is valid while every source fingerprint field still matches.
    reusable = (isinstance(cached_record, dict)
                and cached_record.get('source') == fingerprint
                and cached_record.get('size') == size
                and cached_record.get('quality') == JPEG_QUALITY
                and cached_record.get('prefix_bytes') == min(before.st_size, PREFIX_BYTES)
                and isinstance(cached_record.get('prefix_sha256'), str)
                and len(cached_record['prefix_sha256']) == 64
                and all(c in '0123456789abcdef' for c in cached_record['prefix_sha256']))
    if reusable:
        prefix_sha256 = cached_record['prefix_sha256']
        prefix_length = cached_record['prefix_bytes']
    else:
        with source.open('rb') as stream:
            prefix = stream.read(PREFIX_BYTES)
        prefix_length = len(prefix)
        prefix_sha256 = hashlib.sha256(prefix).hexdigest()
        after_prefix = source.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after_prefix.st_size, after_prefix.st_mtime_ns, after_prefix.st_ctime_ns):
            raise ValueError('Thumbnail source changed during prefix hashing')
    uid = hashlib.sha256(repr((file_id, fingerprint, size, JPEG_QUALITY, prefix_sha256)).encode()).hexdigest()
    name = f'{size}x{size}-{before.st_size}-{prefix_sha256}-{uid}'
    destination = Path(cache_root) / f'image-{size}x{size}' / f'{name}.jpg'
    valid_cache = False
    if destination.is_file():
        try:
            with Image.open(destination) as cached:
                valid_cache = (cached.format == 'JPEG' and max(cached.size) <= size)
                cached.verify()
        except (OSError, ValueError):
            valid_cache = False
    if not valid_cache and cache_only:
        return None
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
    record = {'id': uid, 'file_id': file_id, 'size': size,
            'path': str(destination.resolve()), 'source': fingerprint, 'quality': JPEG_QUALITY,
            'prefix_sha256': prefix_sha256, 'prefix_bytes': prefix_length, 'source_size': before.st_size}
    # Provenance permits directory-scoped deletion even for obsolete versions.
    metadata = destination.with_suffix('.json')
    if not metadata.exists() and not cache_only:
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=destination.parent, suffix='.json', delete=False) as stream:
                temporary = stream.name
                json.dump(record, stream)
            os.replace(temporary, metadata)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
    return record
# RETURN A CACHE LINK AFTER ATOMICALLY PUBLISHING A BOUNDED JPEG THUMBNAIL ]
# REMOVE ONLY GENERATED THUMBNAILS IN THE REQUESTED SOURCE SCOPE [
def cache_record_in_scope(record, directory):
    try:
        source = record['source'][0]
        root = os.path.realpath(directory)
        return os.path.commonpath((root, os.path.realpath(source))) == root
    except (KeyError, IndexError, TypeError, ValueError):
        return False


def clear_thumbnail_cache(cache_root='.cache', directory=None, records=()):
    """Remove generated JPEGs/sidecars; retain unrelated cache files and sources."""
    root = Path(cache_root)
    linked = {str(Path(record['path']).absolute()) for record in records
              if 'path' in record and (directory is None or cache_record_in_scope(record, directory))}
    deleted = 0
    for bucket in root.glob('image-*x*'):
        if bucket.is_symlink() or not bucket.is_dir():
            continue
        for jpeg in bucket.glob('*.jpg'):
            metadata = jpeg.with_suffix('.json')
            matched = directory is None or str(jpeg.absolute()) in linked
            if not matched and metadata.is_file():
                try:
                    matched = cache_record_in_scope(json.loads(metadata.read_text()), directory)
                except (OSError, ValueError, TypeError):
                    pass
            if matched:
                jpeg.unlink(missing_ok=True)
                metadata.unlink(missing_ok=True)
                deleted += 1
    return deleted
# REMOVE ONLY GENERATED THUMBNAILS IN THE REQUESTED SOURCE SCOPE ]
