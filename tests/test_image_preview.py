"""ASCII rendering and quick-view integration using real image files."""
# IMPORT TEST IMAGE PREVIEW DEPENDENCIES [
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
from types import SimpleNamespace
from contextlib import redirect_stdout
from io import StringIO

from PIL import Image
from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS
# IMPORT TEST IMAGE PREVIEW DEPENDENCIES ]
# PREPARE TEST IMAGE PREVIEW SHARED STATE [
spec = importlib.util.spec_from_file_location('image_preview', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)
# PREPARE TEST IMAGE PREVIEW SHARED STATE ]
# VERIFY IMAGE PREVIEW BEHAVIOR [
class ImagePreviewTests(unittest.TestCase):
    # VERIFY ASCII BOUNDS ASPECT AND TRANSPARENCY [
    def test_ascii_bounds_aspect_and_transparency(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.png'
            Image.new('RGB', (200, 100), 'white').save(path)
            rows = tui.ascii_image_preview(path, 20, 20)
            self.assertEqual(rows[0], 'Image: 200 x 100')
            self.assertEqual(rows[1:], [' ' * 20] * 5)
            colored = tui.ascii_image_preview(path, 20, 20, color=True)
            self.assertTrue(any('48;2;255;255;255' in row for row in colored[1:]))
            Image.new('RGBA', (200, 100), (0, 0, 0, 0)).save(path)
            self.assertEqual(tui.ascii_image_preview(path, 20, 20)[1:], [' ' * 20] * 5)
    # VERIFY ASCII BOUNDS ASPECT AND TRANSPARENCY ]
    # VERIFY EXTREME ASPECT AND TINY IMAGES FIT [
    def test_extreme_aspect_and_tiny_images_fit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.png'
            for size in [(1000, 1), (1, 1000), (1, 1)]:
                Image.new('RGB', size, 'white').save(path)
                rows = tui.ascii_image_preview(path, 10, 4)[1:]
                self.assertTrue(rows)
                self.assertLessEqual(len(rows), 4)
                self.assertTrue(all(len(row) <= 10 for row in rows))
    # VERIFY EXTREME ASPECT AND TINY IMAGES FIT ]
    # VERIFY SMALL IMAGE KEEPS PIXEL SIZE AND LARGE IMAGE FILLS BOUND [
    def test_small_image_keeps_pixel_size_and_large_image_fills_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'size.png'
            for size, expected in [((16, 16), (2, 1)), ((1600, 800), (20, 5)),
                                   ((800, 1600), (8, 8))]:
                Image.new('RGB', size, 'white').save(path)
                with patch('term_image.utils.get_cell_size', return_value=(8, 16)):
                    rows = tui.ascii_image_preview(path, 20, 8)[1:]
                self.assertEqual((len(rows[0]), len(rows)), expected)
    # VERIFY SMALL IMAGE KEEPS PIXEL SIZE AND LARGE IMAGE FILLS BOUND ]
    # VERIFY NATIVE DRAW EMITS KITTY PROTOCOL OUTSIDE TEXT [
    def test_native_draw_emits_kitty_protocol_outside_text(self):
        tui.configure_image_terminal()
        from term_image.image import KittyImage
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'native.png'
            Image.new('RGB', (40, 20), 'red').save(path)
            native = Mock()
            output = StringIO()
            with patch('term_image.image.auto_image_class', return_value=KittyImage), \
                    patch.object(KittyImage, 'is_supported', return_value=True), redirect_stdout(output):
                rows = tui.ascii_image_preview(path, 20, 10, color=True, native=native)
            self.assertEqual(output.getvalue(), '')
            native.assert_called_once()
            art, dimensions = native.call_args.args
            self.assertIn('\x1b_G', art)
            self.assertIn('z=731', art)
            self.assertNotIn('\x1b', ''.join(rows))
            self.assertEqual(len(rows) - 1, dimensions[1])
    # VERIFY NATIVE DRAW EMITS KITTY PROTOCOL OUTSIDE TEXT ]
    # VERIFY NATIVE OVERLAY PLACEMENT CLEANUP AND CLIPPING [
    def test_native_overlay_placement_cleanup_and_clipping(self):
        browser = object.__new__(tui.DriveBrowser)
        window = Mock()
        window.render_info = SimpleNamespace(
            window_width=20, window_height=10,
            input_line_to_visible_line={9: 2, 10: 3})
        browser.info = SimpleNamespace(window=window)
        browser.native_preview = ('\x1b_G;KITTY_PAYLOAD\x1b\\', (5, 2), 9)
        browser.native_visible = False
        browser.screen_stack = []
        output = Mock()
        app = SimpleNamespace(output=output, is_done=False, renderer=SimpleNamespace(
            _last_screen=SimpleNamespace(visible_windows_to_write_positions={
                window: SimpleNamespace(xpos=40, ypos=4)})))
        browser.app = app
        browser.draw_native_preview(app)
        self.assertTrue(browser.native_visible)
        self.assertIn('\x1b[7;48H\x1b_G,C=1,q=2;KITTY_PAYLOAD', output.write_raw.call_args.args[0])
        output.reset_mock()
        browser.draw_native_preview(app)
        output.write_raw.assert_not_called()  # Unchanged cursor redraw retains graphics.
        browser.screen_stack = [(object.__new__(tui.BookmarksView), None)]
        browser.draw_native_preview(app)
        output.write_raw.assert_not_called()  # Bookmarks shares the native quick-view layer.
        browser.screen_stack = [(Mock(), None)]  # Other popups hide graphics.
        browser.draw_native_preview(app)
        self.assertFalse(browser.native_visible)
        self.assertIn('d=Z,z=731', output.write_raw.call_args.args[0])
        output.reset_mock()
        browser.screen_stack = []
        window.render_info.input_line_to_visible_line = {9: 9}  # Partly offscreen.
        browser.draw_native_preview(app)
        output.write_raw.assert_not_called()
    # VERIFY NATIVE OVERLAY PLACEMENT CLEANUP AND CLIPPING ]
    # VERIFY ROOT LOGO IS NATIVE ONLY AND HALF SIZE [
    def test_root_logo_is_native_only_and_half_size(self):
        tui.configure_image_terminal()
        from term_image.image import KittyImage
        fs = VirtualFS({'files': {}})
        with patch.object(fs, 'start_in_current_directory'):
            browser = tui.DriveBrowser(fs, input=DummyInput(), output=DummyOutput())
        self.assertIsNone(browser.native_preview)
        self.assertIn('╭────────╮', browser.info.text)
        browser.info.window.render_info = SimpleNamespace(window_width=61, window_height=30)
        with patch('term_image.image.auto_image_class', return_value=KittyImage), \
                patch.object(KittyImage, 'is_supported', return_value=True):
            browser.show_info(directory=True)
        art, (width, height), row = browser.native_preview
        self.assertIn('\x1b_G', art)
        self.assertEqual(width, 30)  # Half the 60 available columns.
        self.assertLessEqual(height, 10)
        self.assertEqual(row, 1)
        self.assertNotIn('\x1b', browser.info.text)
        self.assertIn('h: Open help view', browser.info.text)
        self.assertNotIn('╭────────╮', browser.info.text)
        browser.reset_current_map()
        self.assertIsNone(browser.native_preview)
    # VERIFY ROOT LOGO IS NATIVE ONLY AND HALF SIZE ]
    # VERIFY AUTO LANDSCAPE TO PORTRAIT USES OUTER VIEWPORT [
    def test_auto_landscape_to_portrait_uses_outer_viewport(self):
        with tempfile.TemporaryDirectory() as directory:
            fs = VirtualFS({'files': {}})
            with patch.object(fs, 'start_in_current_directory'):
                browser = tui.DriveBrowser(fs, input=DummyInput(), output=DummyOutput())
            browser.auto_quick_view = True
            browser.graphics_mode = True
            browser.rows = []
            for name, size in [('landscape.png', (800, 100)), ('portrait.png', (100, 800))]:
                path = Path(directory) / name
                Image.new('RGB', size, 'white').save(path)
                node = SimpleNamespace(id=str(path), name=name, size=10, is_dir=False, info={})
                browser.rows.append(dict(node=node, name=name, indicator='green'))
            # Simulate the small preferred height left behind by landscape art.
            browser.info.window.render_info = SimpleNamespace(window_width=41, window_height=13)
            with patch.object(fs, 'get_full_info', return_value={'exists': True, 'size': 10}), \
                    patch.object(tui, 'ascii_image_preview', wraps=tui.ascii_image_preview) as decode:
                browser.show_info()
                browser.move(1)
            self.assertEqual(decode.call_args.args[2], browser.app.output.get_size().rows - 20)
            self.assertGreater(decode.call_args.args[2], 3)
            self.assertIn('portrait.png', browser.info.text)
    # VERIFY AUTO LANDSCAPE TO PORTRAIT USES OUTER VIEWPORT ]
    # VERIFY AUTO SELECTION AND IMAGE DISABLE SKIP DECODING [
    def test_auto_selection_and_image_disable_skip_decoding(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / name for name in ['first.png', 'second.png']]
            for path in paths:
                Image.new('RGB', (12, 8), 'red').save(path)
            fs = VirtualFS({'files': {}})
            with patch.object(fs, 'start_in_current_directory'):
                browser = tui.DriveBrowser(fs, input=DummyInput(), output=DummyOutput())
            browser.rows = []
            for path in paths:
                node = SimpleNamespace(id=str(path), name=path.name, size=10,
                                       is_dir=False, info={})
                browser.rows.append({'node': node, 'name': path.name, 'indicator': 'green'})
            details = {'exists': True, 'size': 10}
            with patch.object(fs, 'get_full_info', return_value=details), \
                    patch.object(tui, 'ascii_image_preview', return_value=['Image preview']) as decode:
                browser.open()
                first_text = browser.info.text
                browser.move(1)
                self.assertEqual(browser.info.text, first_text)  # Manual by default.
                self.assertEqual(decode.call_count, 1)
                browser.toggle_auto_quick_view()
                self.assertIn('second.png', browser.info.text)
                browser.move(-1)
                self.assertIn('first.png', browser.info.text)
                decode.reset_mock()
                browser.toggle_image_previews()
                self.assertFalse(browser.image_previews)
                browser.move(1)
                browser.open()
                decode.assert_not_called()
                self.assertIn('second.png', browser.info.text)
                self.assertNotIn('Image preview', browser.info.text)
                browser.toggle_image_previews()
                decode.assert_called_once()
                browser.toggle_auto_quick_view()
                second_text = browser.info.text
                browser.move(-1)
                self.assertEqual(browser.info.text, second_text)
    # VERIFY AUTO SELECTION AND IMAGE DISABLE SKIP DECODING ]
    # VERIFY Y CONTROLS ALL FILE TYPES AND MODES [
    def test_y_controls_all_file_types_and_modes(self):
        fs = VirtualFS({'files': {}})
        with patch.object(fs, 'start_in_current_directory'):
            browser = tui.DriveBrowser(fs, input=DummyInput(), output=DummyOutput())
        browser.rows = [dict(name=name, node=SimpleNamespace(name=name, id='/disk/' + name,
                            is_dir=name in ('folder', '..')))
                        for name in ['notes.txt', 'photo.png', 'clip.mov', 'song.mp3', 'folder', '..']]
        for graphics in (False, True):
            for mode in (1, 2, 3):
                with self.subTest(graphics=graphics, mode=mode), patch.object(browser, 'show_info') as show:
                    browser.graphics_mode, browser.display_mode = graphics, mode
                    browser.auto_quick_view = False
                    for index in range(len(browser.rows)):
                        browser.select(index)
                    show.assert_not_called()
                    for index in range(4):
                        browser.select(index)
                        browser.open()
                    self.assertEqual(show.call_count, 4)  # Enter still opens every media type.
                    browser.toggle_auto_quick_view()
                    show.reset_mock()
                    for index in range(len(browser.rows)):
                        browser.select(index)
                        show.assert_called_once_with(directory=index == 5)
                        show.reset_mock()
                    browser.toggle_auto_quick_view()
                    browser.select(0)
                    show.assert_not_called()
    # VERIFY Y CONTROLS ALL FILE TYPES AND MODES ]
    # VERIFY MISSING CORRUPT AND OVERSIZED [
    def test_missing_corrupt_and_oversized(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.jpg'
            self.assertIn('unavailable', tui.ascii_image_preview(path)[0])
            path.write_text('not an image')
            self.assertIn('unavailable', tui.ascii_image_preview(path)[0])
            Image.new('1', (5000, 4001)).save(path, format='PNG')
            self.assertIn('20 megapixels', tui.ascii_image_preview(path)[0])
    # VERIFY MISSING CORRUPT AND OVERSIZED ]
    # VERIFY ENTER OPENS PREVIEW WITHOUT LOSING DUPLICATE PATHS [
    def test_enter_opens_preview_without_losing_duplicate_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'picture.PNG'
            Image.new('RGB', (12, 8), 'red').save(path)
            fs = VirtualFS({'files': {}})
            with patch.object(fs, 'start_in_current_directory'):
                browser = tui.DriveBrowser(fs, input=DummyInput(), output=DummyOutput())
            node = type('Node', (), {'id': str(path), 'name': path.name, 'size': 10,
                                    'is_dir': False, 'info': {}})()
            browser.rows = [{'node': node, 'name': path.name, 'indicator': 'green'}]
            details = {'exists': True, 'size': 10, 'dups': ['/other/picture.PNG'],
                       'dups_states': [{'exists': True}]}
            with patch.object(fs, 'get_full_info', return_value=details):
                browser.open()
            self.assertIn('Image: 12 x 8', browser.info.text)
            self.assertIn('Size:', browser.info.text)
            self.assertNotIn('\x1b', browser.info.text)
            self.assertTrue(any('#ff0000' in style
                                for fragments in browser.info_lexer.image_lines.values()
                                for style, _ in fragments))
            document = browser.info.buffer.document
            lexer_line = browser.info_lexer.lex_document(document)
            for index, fragments in browser.info_lexer.image_lines.items():
                self.assertEqual(lexer_line(index), fragments)
            for index, duplicate in browser.info_paths.items():
                self.assertEqual(browser.info.text.splitlines()[index], '● ' + browser.display_path(duplicate))
            self.assertEqual(list(browser.info_paths.values()), ['/other/picture.PNG'])
    # VERIFY ENTER OPENS PREVIEW WITHOUT LOSING DUPLICATE PATHS ]
# VERIFY IMAGE PREVIEW BEHAVIOR ]
