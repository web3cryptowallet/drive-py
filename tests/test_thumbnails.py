"""Thumbnail cache invalidation, durable links and actual grid controls."""
# IMPORT TEST THUMBNAILS DEPENDENCIES [
import asyncio
from functools import partial
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import threading
import shutil
import subprocess
from prompt_toolkit.input import DummyInput

from PIL import Image
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS
from vfs.adapter.sqlite import SQLiteDBAdapter
from vfs.scanner import ScanStore
from vfs.thumbnails import thumbnail
# IMPORT TEST THUMBNAILS DEPENDENCIES ]
# PREPARE TEST THUMBNAILS SHARED STATE [
spec = importlib.util.spec_from_file_location('thumbnail_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)
# PREPARE TEST THUMBNAILS SHARED STATE ]
# VERIFY CACHE BEHAVIOR [
class CacheTests(unittest.TestCase):
    # VERIFY SIZES UNIQUE IDS REUSE AND SOURCE CHANGES [
    def test_sizes_unique_ids_reuse_and_source_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.png'
            Image.new('RGBA', (512, 256), (255, 0, 0, 100)).save(source)
            ids = []
            for size in (128, 256):
                record = thumbnail(source, '/drive/source.png', size, root / '.cache')
                ids.append(record['id'])
                self.assertEqual(record['quality'], 60)
                cache = Path(record['path'])
                self.assertEqual(cache.parent.name, f'image-{size}x{size}')
                self.assertEqual(cache.name, record['id'] + '.jpg')
                with Image.open(cache) as image:
                    self.assertEqual(image.format, 'JPEG')
                    self.assertEqual(image.size, (size, size // 2))
                stamp = cache.stat().st_mtime_ns
                self.assertEqual(thumbnail(source, '/drive/source.png', size, root / '.cache'), record)
                self.assertEqual(cache.stat().st_mtime_ns, stamp)
            self.assertEqual(len(set(ids)), 2)
            Image.new('RGB', (101, 101), 'blue').save(source)
            self.assertNotEqual(thumbnail(source, '/drive/source.png', 128, root / '.cache')['id'], ids[0])
            for invalid in (16, 32, 64, 512):
                with self.assertRaises(ValueError):
                    thumbnail(source, '/drive/source.png', invalid, root / '.cache')
            self.assertFalse(list((root / '.cache').rglob('tmp*')))
    # VERIFY SIZES UNIQUE IDS REUSE AND SOURCE CHANGES ]
    # VERIFY WEBP AVIF AND ADDITIONAL IMAGE FORMATS [
    def test_webp_avif_and_additional_image_formats(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for suffix, format_name in [('webp', 'WEBP'), ('avif', 'AVIF'),
                                        ('tga', 'TGA'), ('pnm', 'PPM')]:
                with self.subTest(format=format_name):
                    source = root / ('image.' + suffix)
                    Image.new('RGB', (180, 90), 'red').save(source, format=format_name)
                    record = thumbnail(source, str(source), cache_root=root / '.cache')
                    with Image.open(record['path']) as cached:
                        self.assertEqual(cached.size, (128, 64))
                        self.assertEqual(cached.format, 'JPEG')
                    self.assertIn('.' + suffix, tui.THUMBNAIL_SUFFIXES)
    # VERIFY WEBP AVIF AND ADDITIONAL IMAGE FORMATS ]
    # VERIFY REAL MOV MP4 FRAMES AND INVALID VIDEO [
    @unittest.skipUnless(shutil.which('ffmpeg'), 'Requires ffmpeg')
    def test_real_mov_mp4_frames_and_invalid_video(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for suffix in ('mov', 'mp4'):
                source = root / ('clip.' + suffix)
                subprocess.run([shutil.which('ffmpeg'), '-nostdin', '-v', 'error',
                                '-f', 'lavfi', '-i', 'color=c=red:s=64x48:r=5:d=0.4',
                                '-c:v', 'mpeg4', '-threads', '1', str(source)],
                               check=True, capture_output=True, timeout=20)
                record = thumbnail(source, str(source), cache_root=root / '.cache')
                with Image.open(record['path']) as cached:
                    self.assertEqual(cached.size, (128, 96))
                    self.assertGreater(cached.getpixel((0, 0))[0], 200)
                self.assertIn('.' + suffix, tui.THUMBNAIL_SUFFIXES)
            invalid = root / 'broken.mov'
            invalid.write_text('invalid video')
            with self.assertRaises(ValueError):
                thumbnail(invalid, str(invalid), cache_root=root / '.cache')
            with patch('vfs.thumbnails.shutil.which', return_value=None):
                with self.assertRaisesRegex(ValueError, 'ffmpeg'):
                    thumbnail(source, str(source), 256, cache_root=root / '.cache')
    # VERIFY REAL MOV MP4 FRAMES AND INVALID VIDEO ]
    # VERIFY MEDIA FILTER AUDIO AND MIXED HEIGHT NAVIGATION [
    def test_media_filter_audio_and_mixed_height_navigation(self):
        fs = VirtualFS({'files': {'/disk/photo.png': {'MD5:one:1'},
                                  '/disk/song.mp3': {'MD5:two:1'},
                                  '/disk/clip.MOV': {'MD5:three:1'},
                                  '/disk/notes.txt': {'MD5:four:1'},
                                  '/disk/folder/readme.txt': {'MD5:five:1'}}})
        fs.enter('disk')
        with patch.object(fs, 'start_in_current_directory'):
            browser = tui.DriveBrowser(fs, input=DummyInput(), output=DummyOutput())
        browser.graphics_mode = True
        browser.control.create_content(60, 30)
        notes = next(index for index, row in enumerate(browser.rows) if row['name'] == 'notes.txt')
        browser.select(notes)
        self.assertFalse(browser.grid_positions[notes][3])
        self.assertEqual(browser.rows[notes]['color'], 'white')
        notes_line = browser.grid_positions[notes][1]
        self.assertIn('class:muted', browser.control.create_content(60, 30).get_line(notes_line)[0][0])
        browser.move_grid_row(1)
        self.assertNotEqual(browser.selected, notes)
        browser.toggle_media_filter()
        self.assertEqual({row['name'] for row in browser.rows}, {'..', 'folder', 'photo.png', 'song.mp3', 'clip.MOV'})
        browser.control.create_content(60, 30)
        self.assertIn('song.mp3', [row['name'] for row in browser.rows if browser.is_media(row)])
        selected = browser.current_name()
        browser.toggle_media_filter()
        self.assertEqual(browser.current_name(), selected)
        self.assertIn('notes.txt', [row['name'] for row in browser.rows])
        self.assertIn('folder', [row['name'] for row in browser.rows])
        browser.control.create_content(60, 30)
        folder = next(index for index, row in enumerate(browser.rows) if row['name'] == 'folder')
        folder_line = browser.grid_positions[folder][1]
        self.assertNotIn('class:muted', browser.control.create_content(60, 30).get_line(folder_line)[0][0])
        browser.graphics_mode = False
        for mode in (1, 2, 3):
            browser.display_mode = mode
            browser.refresh('notes.txt')
            self.assertTrue(all(row['color'] != 'muted' for row in browser.rows))
            browser.media_only = True
            browser.refresh('folder')
            self.assertIn('folder', [row['name'] for row in browser.rows])
            browser.media_only = False
    # VERIFY MEDIA FILTER AUDIO AND MIXED HEIGHT NAVIGATION ]
    # VERIFY DISPLAY ZOOM MINIMUM ONE LINE PRESERVES CACHE RESOLUTION [
    def test_display_zoom_minimum_one_line_preserves_cache_resolution(self):
        fs = VirtualFS({'files': {}})
        with patch.object(fs, 'start_in_current_directory'):
            browser = tui.DriveBrowser(fs, input=DummyInput(), output=DummyOutput())
        browser.graphics_mode = True
        with patch('term_image.utils.get_cell_size', return_value=(8, 16)):
            for _ in range(40):
                browser.resize_icons(-1)
            self.assertEqual(browser.icon_dimensions(), (2, 1))
            self.assertEqual(browser.icon_size, 128)
            for _ in range(40):
                browser.resize_icons(1)
            self.assertEqual(browser.icon_dimensions(), (32, 16))
            self.assertEqual(browser.icon_size, 256)
    # VERIFY DISPLAY ZOOM MINIMUM ONE LINE PRESERVES CACHE RESOLUTION ]
    # VERIFY FIT SMALL WIDE AND TALL IMAGES WITHOUT STDOUT [
    def test_fit_small_wide_and_tall_images_without_stdout(self):
        tui.configure_image_terminal()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(tui, 'thumbnail', partial(thumbnail, cache_root=root / '.cache')):
                for size in [(2, 2), (96, 16), (16, 96)]:
                    source = root / f'{size[0]}-{size[1]}.png'
                    Image.new('RGB', size, 'red').save(source)
                    item = tui.prepare_grid_thumbnail(source, str(source), 128, (12, 4), .5)
                    width, height = item['dimensions']
                    self.assertLessEqual(width, 12)
                    self.assertLessEqual(height, 4)
                    self.assertTrue(width == 12 or height == 4)
    # VERIFY FIT SMALL WIDE AND TALL IMAGES WITHOUT STDOUT ]
    # VERIFY EXPAND SUBDIRS LEVELS SCOPE AND NESTED NAVIGATION [
    def test_expand_subdirs_levels_scope_and_nested_navigation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ['1/2/3/deep.png', '1/2/two.txt', '1/a/a.txt', 'other/o.txt']:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture')
            (root / '1' / 'loop').symlink_to(root / '1', target_is_directory=True)
            fs = VirtualFS({'files': {}})
            browser = tui.DriveBrowser(fs, path=str(root), input=DummyInput(), output=DummyOutput())
            browser.toggle_graphics()
            browser.selected = next(i for i, row in enumerate(browser.rows) if row['name'] == '1')
            original_cwd = fs.pwd()
            browser.expand_subdirs()
            names = [row['name'] for row in browser.rows]
            self.assertIn('1/2', names)
            self.assertNotIn('1/2/3', names)
            self.assertNotIn('other/o.txt', names)
            self.assertEqual(fs.pwd(), original_cwd)
            browser.expand_subdirs()  # Same directory toggles closed.
            self.assertNotIn('1/2', [row['name'] for row in browser.rows])
            browser.expand_subdirs()
            browser.selected = next(i for i, row in enumerate(browser.rows) if row['name'] == '1/2')
            browser.expand_subdirs()
            browser.selected = next(i for i, row in enumerate(browser.rows) if row['name'] == '1/a')
            browser.expand_subdirs()
            names = [row['name'] for row in browser.rows]
            self.assertIn('1/2/3', names)
            self.assertIn('1/a/a.txt', names)
            self.assertLess(names.index('1/2/two.txt'), names.index('1/a'))
            self.assertNotIn('1/2/3/deep.png', names)
            browser.selected = next(i for i, row in enumerate(browser.rows) if row['name'] == '1/2/3')
            browser.expand_subdirs()
            self.assertIn('1/2/3/deep.png', [row['name'] for row in browser.rows])
            content = browser.grid_content(60, 20)
            index = next(i for i, row in enumerate(browser.rows) if row['name'] == '1/2')
            fragments = content.get_line(browser.grid_positions[index][1])
            self.assertIn('class:expanded-dir-name', fragments[0][0])
            self.assertTrue(all('class:expanded-dir' in style for style, _ in fragments))
            self.assertEqual(sum(tui.get_cwidth(text) for _, text in fragments), 60)
            browser.selected = next(i for i, row in enumerate(browser.rows) if row['name'] == '..')
            browser.toggle_expansion_depth()
            browser.expand_subdirs()
            self.assertIn('other/o.txt', [row['name'] for row in browser.rows])
            self.assertFalse(any('/loop/' in row['name'] for row in browser.rows))
            browser.toggle_graphics()
            self.assertIn('1/2', [row['name'] for row in browser.rows])
            browser.toggle_graphics()
            browser.selected = next(i for i, row in enumerate(browser.rows) if row['name'] == '1/2/3')
            browser.open()
            self.assertEqual(fs.pwd(), original_cwd + '/1/2/3')
            self.assertFalse(browser.expanded_dirs)
    # VERIFY EXPAND SUBDIRS LEVELS SCOPE AND NESTED NAVIGATION ]
    # VERIFY GRID GUTTER AND PURPLE AUDIO PLAY ICON [
    def test_grid_gutter_and_purple_audio_play_icon(self):
        fs = VirtualFS({'files': {}})
        with patch.object(fs, 'start_in_current_directory'):
            browser = tui.DriveBrowser(fs, input=DummyInput(), output=DummyOutput())
        browser.graphics_mode = True
        browser.rows = [dict(name=name, node=SimpleNamespace(id=name, is_dir=False), color='white')
                        for name in ['first.png', 'song.mp3', 'last.png']]
        with patch.object(browser, 'icon_dimensions', return_value=(8, 4)):
            content = browser.grid_content(44, 20)
        self.assertEqual([browser.grid_positions[i][0] for i in range(3)], [0, 15, 30])
        fragments = content.get_line(2)
        self.assertTrue(any('class:audio-play' in style and '▶' in text for style, text in fragments))
        for line in range(content.line_count):
            text = ''.join(text for _, text in content.get_line(line))
            self.assertEqual(text[14], ' ')
            self.assertEqual(text[29], ' ')
    # VERIFY GRID GUTTER AND PURPLE AUDIO PLAY ICON ]
    # VERIFY CENTERED GRID PENDING AND FILENAME ONLY ITEMS [
    def test_centered_grid_pending_and_filename_only_items(self):
        fs = VirtualFS({'files': {}})
        with patch.object(fs, 'start_in_current_directory'):
            browser = tui.DriveBrowser(fs, input=DummyInput(), output=DummyOutput())
        browser.graphics_mode = True
        browser.icon_size = 128
        browser.rows = [dict(name=name, node=SimpleNamespace(id=name, is_dir=is_dir), color='white')
                        for name, is_dir in [('photo.png', False), ('folder', True), ('notes.txt', False)]]
        browser.thumbnails = {'photo.png': {'native': None, 'dimensions': (4, 1),
                                           'lines': [[('', '****')]]}}
        with patch.object(browser, 'icon_dimensions', return_value=(8, 4)):
            content = browser.grid_content(42, 20)
            lines = [''.join(part[1] for part in content.get_line(i)) for i in range(content.line_count)]
            self.assertEqual(lines[1][:14], '     ****     ')
            self.assertIn(' photo.png ', lines[4])
            self.assertEqual(lines[6].strip(), 'folder/')
            self.assertEqual(lines[7].strip(), 'notes.txt')
            self.assertEqual(content.line_count, 8)
            self.assertEqual(content.cursor_position.y, 4)  # Include filename in scroll metrics.
            browser.select(2)
            self.assertEqual(browser.grid_content(42, 20).cursor_position.y, 7)
            self.assertIn('class:muted', content.get_line(7)[0][0])
            self.assertNotIn('[DIR]', ''.join(lines))
            self.assertNotIn('[FILE]', ''.join(lines))
            browser.thumbnails = {}
            content = browser.grid_content(42, 20)
            pending = ''.join(part[1] for part in content.get_line(2))
            self.assertEqual(pending[:14].strip(), '.')
            self.assertEqual(pending[14:].strip(), '')
        self.assertEqual(tui.fit_filename('0123456789.png', 8), '…789.png')
        self.assertEqual(tui.fit_filename('abc.png', 8), 'abc.png ')
        self.assertEqual(tui.get_cwidth(tui.fit_filename('猫猫猫猫.png', 8)), 8)
    # VERIFY CENTERED GRID PENDING AND FILENAME ONLY ITEMS ]
# VERIFY CACHE BEHAVIOR ]
# VERIFY GRID BEHAVIOR [
class GridTests(unittest.IsolatedAsyncioTestCase):
    # VERIFY EXPANSION KEY BINDINGS [
    async def test_expansion_key_bindings(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
            root = Path(directory)
            (root / 'one' / 'two').mkdir(parents=True)
            (root / 'one' / 'two' / 'file.txt').write_text('test')
            fs = VirtualFS({'files': {}})
            browser = tui.DriveBrowser(fs, path=str(root), input=pipe, output=DummyOutput())
            browser.selected = next(i for i, row in enumerate(browser.rows) if row['name'] == 'one')
            task = asyncio.create_task(browser.app.run_async())
            try:
                await asyncio.sleep(.05)
                browser.app.layout.focus(browser.info)
                pipe.send_text('ou')
                for _ in range(100):
                    if any(row['name'] == 'one/two/file.txt' for row in browser.rows):
                        break
                    await asyncio.sleep(.01)
                self.assertFalse(browser.graphics_mode)
                self.assertTrue(browser.expand_all_levels)
                self.assertIn('one/two/file.txt', [row['name'] for row in browser.rows])
                self.assertEqual(browser.current_name(), 'one')
                directory_index = browser.selected
                browser.selected = 0
                for mode in (1, 2, 3):
                    browser.display_mode = mode
                    content = browser.control.create_content(60, 20)
                    fragments = content.get_line(directory_index)
                    self.assertTrue(any('class:expanded-dir-name' in style for style, _ in fragments))
                    self.assertTrue(all('class:expanded-dir' in style for style, _ in fragments))
                browser.selected = directory_index
                browser.app.layout.focus(browser.info)
                pipe.send_text('u')
                for _ in range(100):
                    if not browser.expanded_dirs:
                        break
                    await asyncio.sleep(.01)
                self.assertFalse(browser.expanded_dirs)
                self.assertTrue(browser.app.layout.has_focus(browser.control))
                browser.app.layout.focus(browser.info)
                pipe.send_text('u')
                for _ in range(100):
                    if any(row['name'] == 'one/two/file.txt' for row in browser.rows):
                        break
                    await asyncio.sleep(.01)
                self.assertIn('one/two/file.txt', [row['name'] for row in browser.rows])
            finally:
                browser.app.exit()
                await task
    # VERIFY EXPANSION KEY BINDINGS ]
    # VERIFY GRID CONVERSION KEYS AND SQLITE REOPEN [
    async def test_grid_conversion_keys_and_sqlite_reopen(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
            root = Path(directory)
            source = root / 'picture.png'
            Image.new('RGB', (100, 100), 'red').save(source)
            db_path = str(root / 'catalog.db')
            fs = VirtualFS({'files': {str(source): {'MD5:test:100'}}}, db_type='sqlite',
                           rebuild_db=True, db_path=db_path)
            with patch.object(fs, 'start_in_current_directory'):
                browser = tui.DriveBrowser(fs, input=pipe, output=DummyOutput())
            fs.cwd = fs.get_from_path(str(root))
            browser.refresh(source.name)
            worker_threads = []
            # CONVERT FOR TEST GRID CONVERSION KEYS AND SQLITE REOPEN [
            def convert(*args):
                worker_threads.append(threading.get_ident())
                return thumbnail(*args, cache_root=root / '.cache')
            # CONVERT FOR TEST GRID CONVERSION KEYS AND SQLITE REOPEN ]
            with patch.object(tui, 'thumbnail', convert):
                task = asyncio.create_task(browser.app.run_async())
                try:
                    await asyncio.sleep(.03)
                    pipe.send_text('g')
                    for _ in range(100):
                        if str(source) in browser.thumbnails:
                            break
                        await asyncio.sleep(.01)
                    self.assertTrue(browser.graphics_mode)
                    self.assertIn(str(source), browser.thumbnails)
                    self.assertTrue(worker_threads)
                    self.assertNotIn(threading.get_ident(), worker_threads)
                    content = browser.control.create_content(60, 20)
                    text = '\n'.join(''.join(part[1] for part in content.get_line(i))
                                     for i in range(content.line_count))
                    self.assertIn('picture.png', text)
                    self.assertEqual(browser.current_name(), source.name)
                    pipe.send_text('++++++')
                    await asyncio.sleep(.08)
                    self.assertEqual(browser.icon_size, 256)
                    pipe.send_text('______')
                    await asyncio.sleep(.08)
                    self.assertEqual(browser.icon_size, 128)
                    pipe.send_text('g')
                    await asyncio.sleep(.03)
                    self.assertFalse(browser.graphics_mode)
                    self.assertEqual(browser.current_name(), source.name)
                finally:
                    browser.app.exit()
                    await task
            record = ScanStore(fs.db).get('thumbnail', '128:' + str(source))
            self.assertEqual(record['file_id'], str(source))
            self.assertTrue(Path(record['path']).is_file())
            fs.db.conn.close()
            reopened = SQLiteDBAdapter(db_path)
            self.assertEqual(ScanStore(reopened).get('thumbnail', '128:' + str(source)), record)
            reopened.conn.close()
    # VERIFY GRID CONVERSION KEYS AND SQLITE REOPEN ]
# VERIFY GRID BEHAVIOR ]
