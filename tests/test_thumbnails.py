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
                self.assertEqual(cache.name, f"{size}x{size}-{source.stat().st_size}-{record['prefix_sha256']}-{record['id']}.jpg")
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
                                        ('tga', 'TGA'), ('pnm', 'PPM'), ('heic', 'HEIF'),
                                        ('heif', 'HEIF'), ('web', 'WEBP')]:
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
            for suffix in ('mov', 'mp4', 'mts'):
                source = root / ('clip.' + suffix)
                subprocess.run([shutil.which('ffmpeg'), '-nostdin', '-v', 'error',
                                '-f', 'lavfi', '-i', 'color=c=red:s=64x48:r=5:d=0.4',
                                '-c:v', 'libx264' if suffix == 'mts' else 'mpeg4', '-threads', '1',
                                *(['-f', 'mpegts'] if suffix == 'mts' else []), str(source)],
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
        self.enterContext(patch.object(tui.DriveBrowser, 'show_notification'))
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
        self.assertEqual({row['name'] for row in browser.rows}, {'..', 'photo.png', 'song.mp3', 'clip.MOV'})
        browser.control.create_content(60, 30)
        self.assertIn('song.mp3', [row['name'] for row in browser.rows if browser.is_media(row)])
        selected = browser.current_name()
        browser.toggle_media_filter()
        self.assertEqual(browser.media_filter, 'image')
        self.assertEqual({row['name'] for row in browser.rows}, {'..', 'photo.png'})
        browser.toggle_media_filter()
        self.assertEqual(browser.media_filter, 'videos')
        self.assertEqual({row['name'] for row in browser.rows}, {'..', 'clip.MOV'})
        browser.toggle_media_filter()
        self.assertEqual(browser.media_filter, 'all')
        self.assertIn('notes.txt', [row['name'] for row in browser.rows])
        self.assertNotIn('folder', [row['name'] for row in browser.rows])
        browser.graphics_mode = False
        browser.refresh()
        browser.graphics_mode = True
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
            self.assertNotIn('folder', [row['name'] for row in browser.rows])
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
            for name in ['1/2/3/deep.png', '1/2/two.txt', '1/a/a.txt', 'other/o.txt', '1/a/icon.png', 'other/icon.png']:
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
        self.assertEqual([browser.grid_positions[i][0] for i in range(3)], [0, 9, 18])
        fragments = content.get_line(2)
        self.assertTrue(any('class:audio-play' in style and '▶' in text for style, text in fragments))
        for line in range(content.line_count):
            text = ''.join(text for _, text in content.get_line(line))
            self.assertEqual(text[8], ' ')
            self.assertEqual(text[17], ' ')
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
            self.assertEqual(lines[1][:8], '  ****  ')
            self.assertEqual(lines[4], '  …png  ')
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
            self.assertEqual(pending[:8].strip(), '.')
            self.assertEqual(pending[8:].strip(), '')
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
            def convert(*args, **kwargs):
                worker_threads.append(threading.get_ident())
                return thumbnail(*args, cache_root=root / '.cache', **kwargs)
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

# VERIFY GENERATION ORDER COMPLETENESS AND COMPRESSED COVERAGE COLORS [
class GenerationOrderTests(unittest.TestCase):
    def test_orders_visit_every_image_once(self):
        b = SimpleNamespace(thumbnail_seconds=.5, grid_columns=3, grid_tile_height=4,
                            grid_tile_width=14, grid_lines=[None] * 80,
                            grid_positions={i: ((i % 3) * 15, (i // 3) * 4, 14, True)
                                            for i in range(60)},
                            files=SimpleNamespace(render_info=SimpleNamespace(window_height=8)))
        for mode in ('sequence', 'random', 'page-stride', 'range-stride'):
            b.thumbnail_order = mode
            b._thumbnail_visited_pages = set()
            pending = dict.fromkeys(range(60))
            order = []
            while pending:
                index = tui.DriveBrowser.next_thumbnail(b, pending)
                order.append(index)
                pending.pop(index)
            self.assertEqual(sorted(order), list(range(60)))
            if mode == 'sequence':
                self.assertEqual(order, list(range(60)))
            if mode == 'page-stride':
                self.assertEqual(order[:6], [0, 4, 1, 5, 2, 3])
                self.assertEqual(order[6:12], [8, 9, 13, 17, 18, 22])

    def test_page_stride_finishes_visible_page_then_crosses_remaining_pages(self):
        b = SimpleNamespace(thumbnail_order='page-stride', grid_columns=3,
                            grid_tile_height=4, grid_tile_width=14,
                            grid_positions={i: ((i % 3) * 15, (i // 3) * 4, 14, True)
                                            for i in range(24)},
                            files=SimpleNamespace(vertical_scroll=0,
                                render_info=SimpleNamespace(window_height=8)))
        pending = dict.fromkeys(range(24))
        order = []
        while pending:
            index = tui.DriveBrowser.next_thumbnail(b, pending)
            order.append(index)
            pending.pop(index)
        self.assertEqual(order[:6], [0, 4, 1, 5, 2, 3])
        self.assertEqual(order[6:12], [8, 9, 13, 17, 18, 22])
        self.assertEqual(sorted(order), list(range(24)))

    def test_map_uses_first_compressed_row_and_empty_cells(self):
        b = SimpleNamespace(graphics_mode=True, grid_columns=2,
                            rows=[{'node': SimpleNamespace(id=i)} for i in range(8)],
                            grid_lines=[([i, i + 1], 0, True) for i in range(0, 8, 2)],
                            thumbnails={0: {'color': '#ff0000'}, 4: {'color': '#0000ff'}})
        margin = tui.PreviewMapMargin(b)
        self.assertEqual(margin.get_width(None), 2)
        result = margin.create_margin(None, 2, 2)
        self.assertEqual(result, [('bg:#ff0000', ' '), ('', '·'), ('', '\n'),
                                  ('bg:#0000ff', ' '), ('', '·')])
# VERIFY GENERATION ORDER COMPLETENESS AND COMPRESSED COVERAGE COLORS ]

# VERIFY INCREMENTAL NATIVE ARRIVALS KEEP EXISTING PLACEMENTS [
class NativeArrivalTests(unittest.TestCase):
    def test_arrival_draws_only_new_image(self):
        from unittest.mock import Mock
        output = Mock()
        window = object()
        render = SimpleNamespace(input_line_to_visible_line={i: i for i in range(5)},
                                 window_height=5, window_width=50)
        b = SimpleNamespace(graphics_mode=True, image_previews=True, screen_stack=[],
                            files=window, grid_lines=[([0, 1], 0, True)],
                            rows=[{'node': SimpleNamespace(id=i)} for i in range(2)],
                            thumbnails={0: {'native': ('first', (2, 2))}},
                            grid_tile_height=4, grid_tile_width=14,
                            grid_positions={0: (0, 0, 14, True), 1: (15, 0, 14, True)},
                            grid_native_drawn=None)
        # A real Window exposes render_info; use a hashable stand-in.
        class FakeWindow:
            render_info = render
        b.files = FakeWindow()
        app = SimpleNamespace(is_done=False, output=output,
                              renderer=SimpleNamespace(_last_screen=SimpleNamespace(
                                  visible_windows_to_write_positions={b.files: SimpleNamespace(xpos=0, ypos=0)})))
        b.clear_grid_native = lambda: tui.DriveBrowser.clear_grid_native(b)
        b.app = app
        with patch.object(tui, 'native_graphics_payload', side_effect=lambda art: art):
            tui.DriveBrowser.draw_grid_native(b, app)
            output.reset_mock()
            b.thumbnails[1] = {'native': ('second', (2, 2))}
            tui.DriveBrowser.draw_grid_native(b, app)
        payload = output.write_raw.call_args.args[0]
        self.assertIn('second', payload)
        self.assertNotIn('first', payload)
        self.assertNotIn('a=d', payload)
# VERIFY INCREMENTAL NATIVE ARRIVALS KEEP EXISTING PLACEMENTS ]

# VERIFY SLOW EXPANSION CANCELS BEFORE PUBLISHING ANY ROWS [
class ExpansionCancelTests(unittest.IsolatedAsyncioTestCase):
    async def test_second_u_cancels_blocked_disk_work(self):
        fs = VirtualFS({'files': {}})
        with patch.object(fs, 'start_in_current_directory'):
            b = tui.DriveBrowser(fs, input=DummyInput(), output=DummyOutput())
        root = SimpleNamespace(id='/slow', is_dir=True)
        b.rows = [{'name': 'slow', 'node': root}]
        b.selected = 0
        started = asyncio.Event()
        release = asyncio.Event()
        async def blocked(node):
            started.set()
            await release.wait()
            return []
        b.expansion_nodes = blocked
        b.rows[0]['name'] = '..'
        original = b.rows
        b.expand_subdirs()
        task = b.expansion_task
        await asyncio.wait_for(started.wait(), 1)
        b.expand_subdirs()
        await asyncio.sleep(0)
        self.assertTrue(task.cancelled())
        self.assertIsNone(b.expansion_task)
        self.assertIs(b.rows, original)
        self.assertFalse(b.expanded_dirs)

    def test_map_width_matches_grid_at_thresholds(self):
        from prompt_toolkit.layout.screen import WritePosition
        from unittest.mock import Mock
        b = SimpleNamespace(graphics_mode=True, grid_columns=4,
                            icon_dimensions=lambda: (8, 4))
        margin = tui.PreviewMapMargin(b)
        window = tui.FilesWindow(b)
        for total in range(32, 100):
            with patch.object(tui.Window, 'write_to_screen'):
                window.write_to_screen(Mock(), Mock(), WritePosition(0, 0, total, 20), '', False, None)
            width = margin.get_width(None)
            content_width = total - width - 1
            self.assertLessEqual(width, max(1, (content_width + 1) // 9))
            self.assertEqual(width, total // 10)
# VERIFY SLOW EXPANSION CANCELS BEFORE PUBLISHING ANY ROWS ]

# VERIFY MAP MOUSE HIT TARGET SELECTS THE REPRESENTED FILE [
class PreviewMapClickTests(unittest.TestCase):
    def test_click_selects_file_in_compressed_band(self):
        from unittest.mock import Mock
        from prompt_toolkit.mouse_events import MouseEvent, MouseEventType, MouseButton
        from prompt_toolkit.data_structures import Point
        fs = VirtualFS({'files': {}})
        with patch.object(fs, 'start_in_current_directory'):
            b = tui.DriveBrowser(fs, input=DummyInput(), output=DummyOutput())
        b.graphics_mode = True
        b.preview_map_columns = 3
        b.grid_columns = 3
        b.grid_lines = [([i, i + 1, i + 2], 0, True) for i in range(0, 30, 3)]
        b.files.render_info = SimpleNamespace(window_height=5)
        handlers = Mock()
        app = SimpleNamespace(is_done=False, renderer=SimpleNamespace(
            _last_screen=SimpleNamespace(visible_windows_to_write_positions={b.files:
                SimpleNamespace(xpos=2, ypos=3, width=50, height=5)}), mouse_handlers=handlers),
                layout=Mock())
        b.select = Mock()
        b.install_files_scrollbar(app)
        call = handlers.set_mouse_handler_for_range.call_args_list[0]
        self.assertEqual(call.kwargs['x_min'], 48)
        call.kwargs['handler'](MouseEvent(Point(49, 7), MouseEventType.MOUSE_UP, MouseButton.LEFT, frozenset()))
        b.select.assert_called_once_with(25)
# VERIFY MAP MOUSE HIT TARGET SELECTS THE REPRESENTED FILE ]

# VERIFY LIVE UNIQUE FILE COUNTS AND INDICATOR CLEANUP [
class ExpansionProgressTests(unittest.IsolatedAsyncioTestCase):
    async def test_progress_counts_files_once_and_clears_on_exit(self):
        from unittest.mock import AsyncMock
        fs = VirtualFS({'files': {}})
        with patch.object(fs, 'start_in_current_directory'):
            b = tui.DriveBrowser(fs, input=DummyInput(), output=DummyOutput())
        entered, release = asyncio.Event(), asyncio.Event()
        async def expand():
            entered.set()
            await release.wait()
        b.expand_subdirs_async = expand
        b.expansion_task = asyncio.create_task(b.run_expansion())
        await entered.wait()
        self.assertIn('scanning 0 files', b.expansion_status())
        children = [SimpleNamespace(id=f'/file-{i}.png', is_dir=False) for i in range(1000)] + [SimpleNamespace(id='/a.png', is_dir=False),
                    SimpleNamespace(id='/folder', is_dir=True)]
        with patch.object(tui, 'background_call', new=AsyncMock(return_value=children)):
            await b.expansion_nodes(fs.cwd)
            await b.expansion_nodes(fs.cwd)
        self.assertIn('scanning 1000 files', b.expansion_status())
        self.assertIn('scanning 1000 files', ''.join(text for _, text in b.column_header()))
        b.graphics_mode = True
        header = b.grid_content(80, 20, header=True)
        self.assertIn('scanning 1000 files', ''.join(text for _, text in header.get_line(0)))
        task = b.expansion_task
        release.set()
        await task
        self.assertEqual(b.expansion_status(), '')
        self.assertIsNone(b.expansion_task)
# VERIFY LIVE UNIQUE FILE COUNTS AND INDICATOR CLEANUP ]

# VERIFY EXPANSION ONLY ENUMERATES AND BATCHES PROGRESS [
class ExpansionEnumerationTests(unittest.IsolatedAsyncioTestCase):
    async def test_progress_batches_and_reuses_enumeration(self):
        from unittest.mock import AsyncMock, Mock
        fs = VirtualFS({'files': {}})
        with patch.object(fs, 'start_in_current_directory'):
            b = tui.DriveBrowser(fs, input=DummyInput(), output=DummyOutput())
        nodes = [SimpleNamespace(id=str(i), is_dir=False) for i in range(999)]
        with patch.object(tui, 'background_call', new=AsyncMock(return_value=nodes)) as read, \
                patch.object(b.app, 'invalidate') as redraw:
            await b.expansion_nodes(SimpleNamespace(id='first'))
            redraw.assert_not_called()
            await b.expansion_nodes(SimpleNamespace(id='first'))
            self.assertEqual(read.await_count, 1)
            nodes.append(SimpleNamespace(id='999', is_dir=False))
            await b.expansion_nodes(SimpleNamespace(id='second'))
            redraw.assert_called_once()

    async def test_expansion_skips_full_info_and_duplicate_queries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'folder').mkdir()
            (root / 'folder' / 'item.txt').write_text('hello')
            fs = VirtualFS({'files': {}})
            fs.start_in_current_directory(directory)
            b = tui.DriveBrowser(fs, input=DummyInput(), output=DummyOutput())
            fs.start_in_current_directory(directory)
            b.refresh()
            b.selected = next(i for i, row in enumerate(b.rows) if row['name'] == 'folder')
            with patch.object(fs, 'get_full_info', side_effect=AssertionError('extra stat pass')), \
                    patch.object(fs, 'get_hash_dups', side_effect=AssertionError('duplicate scan')):
                await b.expand_subdirs_async()
            self.assertIn('folder/item.txt', [row['name'] for row in b.rows])
# VERIFY EXPANSION ONLY ENUMERATES AND BATCHES PROGRESS ]

# VERIFY MEDIA ANCESTORS, EMPTY MAP CELLS AND DRAG SELECTION [
class MediaMapInteractionTests(unittest.TestCase):
    def test_filter_keeps_nested_media_and_hides_other_directories(self):
        fs = VirtualFS({'files': {'/disk/media/deep/song.MP3': {'MD5:a:1'},
                                  '/disk/text/readme.txt': {'MD5:b:1'},
                                  '/disk/hidden/.secret/photo.png': {'MD5:c:1'}}})
        fs.enter('disk')
        with patch.object(fs, 'start_in_current_directory'):
            b = tui.DriveBrowser(fs, input=DummyInput(), output=DummyOutput())
        b.media_only = True
        for graphics in (False, True):
            b.graphics_mode = graphics
            b.refresh()
            self.assertEqual({r['name'] for r in b.rows}, ({'..', 'hidden'} if graphics else {'..', 'media', 'hidden'}))
            b.hide_dotfiles = True
            b.refresh()
            self.assertEqual({r['name'] for r in b.rows}, ({'..'} if graphics else {'..', 'media'}))
            b.hide_dotfiles = False
        b.media_only = False
        b.graphics_mode = False
        b.refresh()
        self.assertIn('text', [r['name'] for r in b.rows])

    def test_map_empty_tail_and_selection_cursor(self):
        b = SimpleNamespace(graphics_mode=True, grid_columns=3, selected=1,
                            rows=[{'node': SimpleNamespace(id=i)} for i in range(2)],
                            grid_lines=[([0, 1], 0, True)], thumbnails={})
        fragments = tui.PreviewMapMargin(b).create_margin(None, 3, 1)
        self.assertEqual([text for _, text in fragments], ['·', '◆', ' '])
        b.grid_lines = []
        self.assertEqual(tui.PreviewMapMargin(b).create_margin(None, 3, 1), [('', ' ')] * 3)

    def test_map_drag_changes_selection_and_releases_capture(self):
        from unittest.mock import Mock
        from prompt_toolkit.mouse_events import MouseEvent, MouseEventType, MouseButton
        from prompt_toolkit.data_structures import Point
        fs = VirtualFS({'files': {}})
        with patch.object(fs, 'start_in_current_directory'):
            b = tui.DriveBrowser(fs, input=DummyInput(), output=DummyOutput())
        b.graphics_mode = True
        b.preview_map_columns = b.grid_columns = 3
        b.grid_lines = [([i, i + 1, i + 2], 0, True) for i in range(0, 30, 3)]
        b.files.render_info = SimpleNamespace(window_height=5)
        handlers = Mock()
        app = SimpleNamespace(is_done=False, output=SimpleNamespace(get_size=lambda: SimpleNamespace(columns=100, rows=30)),
            renderer=SimpleNamespace(_last_screen=SimpleNamespace(visible_windows_to_write_positions={b.files:
                SimpleNamespace(xpos=2, ypos=3, width=50, height=5)}), mouse_handlers=handlers),
            layout=Mock(), invalidate=Mock())
        b.select = Mock()
        b.install_files_scrollbar(app)
        handler = handlers.set_mouse_handler_for_range.call_args_list[0].kwargs['handler']
        def send(kind, x, y):
            handler(MouseEvent(Point(x, y), kind, MouseButton.LEFT, frozenset()))
        send(MouseEventType.MOUSE_DOWN, 48, 3)
        self.assertTrue(b.preview_map_dragging)
        b.select.assert_called_with(0)
        send(MouseEventType.MOUSE_MOVE, 49, 7)
        b.select.assert_called_with(25)
        send(MouseEventType.MOUSE_UP, 49, 7)
        self.assertFalse(b.preview_map_dragging)
# VERIFY MEDIA ANCESTORS, EMPTY MAP CELLS AND DRAG SELECTION ]

# VERIFY MAP MOUSE ROWS AND CURSOR ROUND TRIP AT NONDIVISIBLE HEIGHTS [
class MapCursorRowTests(unittest.TestCase):
    def test_clicked_row_matches_cursor_for_compressed_and_stretched_maps(self):
        for count, height in ((7, 5), (23, 9), (3, 8), (10, 5)):
            b = SimpleNamespace(graphics_mode=True, grid_columns=1,
                                rows=[{'node': SimpleNamespace(id=i)} for i in range(count)],
                                grid_lines=[([i], 0, True) for i in range(count)], thumbnails={})
            for y in range(height):
                b.selected = y * count // height
                fragments = tui.PreviewMapMargin(b).create_margin(None, 1, height)
                lines = ''.join(text for _, text in fragments).splitlines()
                cursor_y = next(i for i, line in enumerate(lines) if '◆' in line)
                if count >= height:
                    self.assertEqual(cursor_y, y, (count, height, y))
                else:
                    self.assertEqual(cursor_y * count // height, b.selected)
# VERIFY MAP MOUSE ROWS AND CURSOR ROUND TRIP AT NONDIVISIBLE HEIGHTS ]

# VERIFY CACHE REUSE, SCOPED DELETION AND PAGE PRIORITY [
class PreviewRevisionTests(unittest.TestCase):
    def test_cache_only_reuses_jpeg_and_scoped_clear_keeps_other_sources(self):
        from vfs.thumbnails import clear_thumbnail_cache
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            one, two = root / 'one', root / 'two'
            one.mkdir(); two.mkdir()
            source, other = one / 'a.png', two / 'b.png'
            Image.new('RGB', (20, 20), 'red').save(source)
            Image.new('RGB', (20, 20), 'blue').save(other)
            cache = root / '.cache'
            self.assertIsNone(thumbnail(source, '/one/a.png', cache_root=cache, cache_only=True))
            first = thumbnail(source, '/one/a.png', cache_root=cache)
            second = thumbnail(other, '/two/b.png', cache_root=cache)
            with patch('vfs.thumbnails.media_image', side_effect=AssertionError('source decoded')):
                self.assertEqual(thumbnail(source, '/one/a.png', cache_root=cache, cache_only=True), first)
            Image.new('RGB', (21, 20), 'green').save(source)
            newest = thumbnail(source, '/one/a.png', cache_root=cache)
            unrelated = cache / 'keep.txt'; unrelated.write_text('keep')
            self.assertEqual(clear_thumbnail_cache(cache, one), 2)
            self.assertFalse(Path(first['path']).exists())
            self.assertFalse(Path(newest['path']).exists())
            self.assertTrue(Path(second['path']).exists())
            self.assertEqual(clear_thumbnail_cache(cache), 1)
            self.assertTrue(unrelated.exists())
            self.assertTrue(source.exists())
            self.assertTrue(other.exists())

    def test_every_mode_prioritizes_changed_viewport_first_pending_image(self):
        render = SimpleNamespace(window_height=8, vertical_scroll=8)
        b = SimpleNamespace(files=SimpleNamespace(render_info=render), grid_columns=3,
                            grid_tile_width=14, grid_tile_height=4,
                            grid_positions={i: ((i % 3) * 15, (i // 3) * 4, 14, True) for i in range(24)})
        for mode in ('sequence', 'random', 'page-stride', 'range-stride'):
            b.thumbnail_order = mode
            b._thumbnail_view = None
            render.vertical_scroll = 8
            self.assertEqual(tui.DriveBrowser.next_thumbnail(b, dict.fromkeys(range(24))), 6)
            for _ in range(5):
                self.assertIn(tui.DriveBrowser.next_thumbnail(b, dict.fromkeys(range(7, 24))), range(7, 12))
            render.vertical_scroll = 16
            self.assertEqual(tui.DriveBrowser.next_thumbnail(b, dict.fromkeys(range(24))), 12)


class PreviewGenerationPriorityTests(unittest.IsolatedAsyncioTestCase):
    async def test_worker_reprioritizes_after_page_changes(self):
        from concurrent.futures import ThreadPoolExecutor
        fs = VirtualFS({'files': {}})
        with patch.object(fs, 'start_in_current_directory'):
            b = tui.DriveBrowser(fs, input=DummyInput(), output=DummyOutput())
        b.graphics_mode = True
        b.rows = [{'node': SimpleNamespace(id=f'/disk/{i}.png', name=f'{i}.png', is_dir=False)} for i in range(12)]
        b.grid_columns = 3
        b.grid_tile_width, b.grid_tile_height = 14, 4
        b.grid_lines = [(list(range(i, i + 3)), offset, True)
                        for i in range(0, 12, 3) for offset in range(4)]
        b.grid_positions = {i: ((i % 3) * 15, (i // 3) * 4, 14, True) for i in range(12)}
        render = SimpleNamespace(window_height=8, vertical_scroll=0)
        b.files.render_info = render
        generated = []
        def prepare(path, file_id, size, dimensions, ratio, cache_only=False, cached_record=None):
            if cache_only:
                return None
            generated.append(int(Path(file_id).stem))
            if len(generated) == 1:
                render.vertical_scroll = 8
                b.files.vertical_scroll = 8
            return {'record': {'id': file_id}, 'native': None, 'lines': [], 'dimensions': (1, 1)}
        with ThreadPoolExecutor(max_workers=1) as executor, patch.object(tui, 'prepare_grid_thumbnail', prepare):
            b.thumbnail_executor = executor
            await b.generate_thumbnails()
        self.assertEqual(generated[:2], [0, 6])
        self.assertEqual(set(generated[1:7]), set(range(6, 12)))
        self.assertEqual(sorted(generated), list(range(12)))

    async def test_clear_removes_scoped_links_and_restarts(self):
        from unittest.mock import Mock
        fs = VirtualFS({'files': {}})
        with patch.object(fs, 'start_in_current_directory'):
            b = tui.DriveBrowser(fs, input=DummyInput(), output=DummyOutput())
        store = ScanStore(fs.db)
        store.put('thumbnail', 'one', {'path': '/unused', 'source': ['/scope/a.png']})
        store.put('thumbnail', 'two', {'path': '/unused', 'source': ['/other/a.png']})
        b.thumbnail_cache_clearing = True
        b.start_thumbnails = Mock()
        with patch.object(tui, 'get_real_path', return_value='/scope'), patch('vfs.thumbnails.clear_thumbnail_cache'):
            await b.clear_preview_cache_async(False)
        self.assertEqual(set(store.items('thumbnail')), {'two'})
        self.assertFalse(b.thumbnail_cache_clearing)
        b.start_thumbnails.assert_called_once()
        b.thumbnail_cache_clearing = True
        with patch('vfs.thumbnails.clear_thumbnail_cache'):
            await b.clear_preview_cache_async(True)
        self.assertEqual(store.items('thumbnail'), {})
        self.assertEqual(b.start_thumbnails.call_count, 2)
        b.thumbnail_executor.shutdown(wait=True)
# VERIFY CACHE REUSE, SCOPED DELETION AND PAGE PRIORITY ]

# VERIFY GENERATION AND CACHE CLEAR SHORTCUTS THROUGH REAL KEY INPUT [
class PreviewShortcutTests(unittest.IsolatedAsyncioTestCase):
    async def test_uppercase_g_and_directory_all_cache_shortcuts(self):
        fs = VirtualFS({'files': {}})
        with create_pipe_input() as pipe, patch.object(fs, 'start_in_current_directory'):
            b = tui.DriveBrowser(fs, input=pipe, output=DummyOutput())
            b.graphics_mode = True
            b.image_previews = False
            requests = []
            b.clear_preview_cache = lambda all_directories: requests.append(all_directories)
            task = asyncio.create_task(b.app.run_async())
            try:
                await asyncio.sleep(.04)
                b.expansion_cwd = 'previous-directory'
                def blocked_refresh(*args, **kwargs):
                    self.assertEqual(b.clipboard_notice, 'Working… loading folder')
                    raise OSError('disk unavailable')
                with patch.object(b, 'refresh_rows', side_effect=blocked_refresh), patch.object(b.app, '_redraw') as redraw:
                    with self.assertRaisesRegex(OSError, 'disk unavailable'):
                        b.refresh()
                    redraw.assert_called_once()
                self.assertEqual(b.clipboard_notice, '')
                b.expansion_cwd = fs.pwd()
                notice = b.begin_working('Working…')
                b.show_notification('Newer notice')
                b.end_working(notice)
                self.assertEqual(b.clipboard_notice, 'Newer notice')
                pipe.send_text('GkK')
                for _ in range(100):
                    if len(requests) == 2:
                        break
                    await asyncio.sleep(.01)
                self.assertEqual(b.thumbnail_order, 'random')
                self.assertEqual(requests, [False, True])
                self.assertEqual(b.clipboard_notice, 'Preview order: random')
                for mode in ('page-stride', 'range-stride', 'sequence'):
                    pipe.send_text('G')
                    for _ in range(100):
                        if b.thumbnail_order == mode:
                            break
                        await asyncio.sleep(.01)
                    self.assertEqual(b.clipboard_notice, f'Preview order: {mode}')
                for mode in ('media', 'image', 'videos', 'all'):
                    pipe.send_text('v')
                    for _ in range(100):
                        if b.media_filter == mode:
                            break
                        await asyncio.sleep(.01)
                    self.assertEqual(b.media_filter, mode)
                    self.assertEqual(b.clipboard_notice, f'File filter: {mode}')
            finally:
                b.app.exit()
                await task
# VERIFY GENERATION AND CACHE CLEAR SHORTCUTS THROUGH REAL KEY INPUT ]

# VERIFY CACHE FILENAMES INCLUDE BOUNDS, SOURCE BYTES AND BOUNDED CONTENT HASH [
class ThumbnailPrefixIdentityTests(unittest.TestCase):
    def test_large_image_hashes_exactly_first_mebibyte_and_detects_prefix_changes(self):
        import hashlib
        from vfs.thumbnails import PREFIX_BYTES
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'large.png'
            Image.new('RGB', (128, 128), 'red').save(source)
            with source.open('ab') as stream:
                stream.write(b'a' * (3 * PREFIX_BYTES))
            cache = root / '.cache'
            first = thumbnail(source, '/large.png', 128, cache)
            expected = hashlib.sha256(source.read_bytes()[:PREFIX_BYTES]).hexdigest()
            self.assertEqual(first['prefix_sha256'], expected)
            self.assertEqual(first['prefix_bytes'], PREFIX_BYTES)
            self.assertEqual(first['source_size'], source.stat().st_size)
            self.assertEqual(Path(first['path']).stem,
                             f"128x128-{first['source_size']}-{expected}-{first['id']}")
            with source.open('r+b') as stream:
                stream.seek(PREFIX_BYTES + 10)
                stream.write(b'b')
            tail_changed = thumbnail(source, '/large.png', 128, cache)
            self.assertEqual(tail_changed['prefix_sha256'], first['prefix_sha256'])
            self.assertNotEqual(tail_changed['id'], first['id'])
            with source.open('r+b') as stream:
                stream.seek(4096)
                stream.write(b'c')
            prefix_changed = thumbnail(source, '/large.png', 128, cache)
            self.assertNotEqual(prefix_changed['prefix_sha256'], first['prefix_sha256'])
            self.assertNotEqual(prefix_changed['path'], first['path'])

    def test_short_image_and_video_use_same_prefix_contract(self):
        import hashlib
        from contextlib import nullcontext
        for suffix in ('.png', '.mp4'):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / ('source' + suffix)
                source.write_bytes(b'short media fixture')
                with patch('vfs.thumbnails.media_image', return_value=nullcontext(Image.new('RGB', (32, 16), 'blue'))):
                    record = thumbnail(source, str(source), 256, root / '.cache')
                self.assertEqual(record['prefix_sha256'], hashlib.sha256(source.read_bytes()).hexdigest())
                self.assertEqual(record['prefix_bytes'], source.stat().st_size)
                self.assertTrue(Path(record['path']).name.startswith(f'256x256-{source.stat().st_size}-'))
                self.assertTrue(Path(record['path']).with_suffix('.json').exists())
# VERIFY CACHE FILENAMES INCLUDE BOUNDS, SOURCE BYTES AND BOUNDED CONTENT HASH ]

# VERIFY UNCHANGED CACHE HITS AVOID SOURCE PREFIX READS AND TERMINAL REBUILDING [
class FastCachedPreviewTests(unittest.TestCase):
    def test_saved_source_signature_skips_prefix_io_until_source_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'image.png'
            Image.new('RGB', (128, 128), 'green').save(source)
            first = thumbnail(source, str(source), cache_root=root / 'cache')
            with patch.object(Path, 'open', side_effect=AssertionError('source prefix read')):
                self.assertEqual(thumbnail(source, str(source), cache_root=root / 'cache',
                                           cache_only=True, cached_record=first), first)
            with source.open('ab') as stream:
                stream.write(b'changed')
            with patch.object(Path, 'open', side_effect=AssertionError('source prefix read')):
                with self.assertRaisesRegex(AssertionError, 'source prefix read'):
                    thumbnail(source, str(source), cache_root=root / 'cache', cache_only=True, cached_record=first)
            changed = thumbnail(source, str(source), cache_root=root / 'cache', cached_record=first)
            self.assertNotEqual(changed['prefix_sha256'], first['prefix_sha256'])
            self.assertNotEqual(changed['id'], first['id'])

    def test_prepared_render_reuse_geometry_changes_and_cache_clearing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'image.png'
            Image.new('RGB', (128, 128), 'blue').save(source)
            original = tui.thumbnail
            def convert(*args, **kwargs):
                return original(*args, cache_root=root / 'cache', **kwargs)
            tui.GRID_RENDER_CACHE.clear()
            with patch.object(tui, 'thumbnail', convert):
                first = tui.prepare_grid_thumbnail(source, str(source), 128, (12, 4), .5)
                with patch('prompt_toolkit.formatted_text.ANSI', side_effect=AssertionError('terminal rendering repeated')):
                    second = tui.prepare_grid_thumbnail(source, str(source), 128, (12, 4), .5,
                                                        True, first['record'])
                    self.assertIs(first, second)
                resized = tui.prepare_grid_thumbnail(source, str(source), 128, (8, 2), .5, True, first['record'])
                self.assertIsNot(first, resized)
                self.assertNotEqual(first['dimensions'], resized['dimensions'])
                self.assertEqual(tui.clear_grid_cache_files(root / 'cache', root, [first['record']]), 1)
                self.assertFalse(tui.GRID_RENDER_CACHE)
                self.assertIsNone(tui.prepare_grid_thumbnail(source, str(source), 128, (12, 4), .5,
                                                            True, first['record']))
# VERIFY UNCHANGED CACHE HITS AVOID SOURCE PREFIX READS AND TERMINAL REBUILDING ]

# VERIFY IMAGE-WIDTH LABEL ALIGNMENT FOR NATIVE BLOCK AND BOOKMARKED TILES [
class ImageWidthFilenameTests(unittest.TestCase):
    def test_names_fit_actual_image_width_and_keep_column_gutters(self):
        fs = VirtualFS({'files': {}})
        with patch.object(fs, 'start_in_current_directory'):
            b = tui.DriveBrowser(fs, input=DummyInput(), output=DummyOutput())
        b.graphics_mode = True
        name = 'long猫猫image.png'
        b.rows = [dict(name=name, node=SimpleNamespace(id=name, is_dir=False), color='white')]
        for native in (None, ('art', (6, 4))):
            for width in (1, 6, 10):
                b.thumbnails = {name: {'native': native, 'dimensions': (width, 4), 'lines': []}}
                with patch.object(b, 'icon_dimensions', return_value=(10, 4)), \
                        patch.object(b, 'bookmark_path', return_value='/bookmark'):
                    for marked in (False, True):
                        b.bookmarks = ['/bookmark'] if marked else []
                        content = b.grid_content(40, 20)
                        fragments = content.get_line(4)
                        left = (b.grid_tile_width - width) // 2
                        self.assertEqual(fragments[0][1], ' ' * left)
                        self.assertEqual(fragments[-1][1], ' ' * (b.grid_tile_width - left - width))
                        self.assertEqual(sum(tui.get_cwidth(text) for _, text in fragments[1:-1]), width)
                        self.assertEqual(sum(tui.get_cwidth(text) for _, text in fragments), b.grid_tile_width)
                        if marked:
                            self.assertTrue(any('class:bookmark' in style and text == 'B' for style, text in fragments))
# VERIFY IMAGE-WIDTH LABEL ALIGNMENT FOR NATIVE BLOCK AND BOOKMARKED TILES ]

# VERIFY SMALL ZOOM FITS MORE TILES AND NATIVE IMAGES REACH THE CONTENT EDGE [
class CompactGridGeometryTests(unittest.TestCase):
    def test_one_to_three_lines_use_icon_width_without_fixed_borders(self):
        from unittest.mock import Mock
        from prompt_toolkit.layout.screen import WritePosition
        fs = VirtualFS({'files': {}})
        with patch.object(fs, 'start_in_current_directory'):
            b = tui.DriveBrowser(fs, input=DummyInput(), output=DummyOutput())
        b.graphics_mode = True
        b.rows = [dict(name=f'{i}.png', node=SimpleNamespace(id=f'{i}.png', is_dir=False), color='white') for i in range(60)]
        for lines, columns in ((1, 15), (2, 10), (3, 7)):
            b.icon_lines = lines
            with patch('term_image.utils.get_cell_size', return_value=(8, 16)), \
                    patch.object(tui.Window, 'write_to_screen'):
                b.files.write_to_screen(Mock(), Mock(), WritePosition(0, 0, 60, 20), '', False, None)
                content = b.grid_content(60 - b.preview_map_columns - 1, 20)
            self.assertEqual(b.grid_tile_width, lines * 2)
            self.assertEqual(b.grid_columns, columns)
            self.assertEqual(b.preview_map_columns, columns)
            self.assertEqual(b.grid_positions[1][0], lines * 2 + 1)
            row = content.get_line(lines)
            self.assertEqual(sum(tui.get_cwidth(text) for _, text in row), columns * (lines * 2 + 1) - 1)

    def test_native_image_filling_final_content_column_is_drawn(self):
        from unittest.mock import Mock
        render = SimpleNamespace(input_line_to_visible_line={0: 0}, window_height=3, window_width=2)
        class FakeWindow:
            render_info = render
        window = FakeWindow()
        output = Mock()
        app = SimpleNamespace(is_done=False, output=output, renderer=SimpleNamespace(_last_screen=SimpleNamespace(
            visible_windows_to_write_positions={window: SimpleNamespace(xpos=0, ypos=0)})))
        b = SimpleNamespace(graphics_mode=True, image_previews=True, screen_stack=[], files=window,
                            grid_lines=[([0], 0, True)], rows=[{'node': SimpleNamespace(id='image')}],
                            thumbnails={'image': {'native': ('edge-art', (2, 1))}},
                            grid_tile_height=3, grid_tile_width=2, grid_positions={0: (0, 0, 2, True)},
                            grid_native_drawn=None, app=app)
        b.clear_grid_native = lambda: tui.DriveBrowser.clear_grid_native(b)
        with patch.object(tui, 'native_graphics_payload', side_effect=lambda art: art):
            tui.DriveBrowser.draw_grid_native(b, app)
        self.assertIn('edge-art', output.write_raw.call_args.args[0])
# VERIFY SMALL ZOOM FITS MORE TILES AND NATIVE IMAGES REACH THE CONTENT EDGE ]
