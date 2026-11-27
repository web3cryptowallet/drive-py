"""Video posters fit the actual viewport left by metadata and duplicates."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS

spec = importlib.util.spec_from_file_location('video_sizing_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class VideoSizingTests(unittest.IsolatedAsyncioTestCase):
    def test_block_video_is_centered_without_losing_styles(self):
        browser = object.__new__(tui.DriveBrowser)
        browser.video_area = SimpleNamespace(lexer=SimpleNamespace(image_lines={}), text='')
        browser.video_poster_bounds = lambda: (10, 6)
        frame = {'native': None, 'lines': [[('fg:red', 'ABCD')], [('fg:blue', 'EFGH')]]}
        browser.apply_video_frame(frame)
        self.assertIsNone(browser.native_preview)
        self.assertEqual(browser.video_area.text.split('\n'),
                         ['', '', '   ABCD', '   EFGH', '', ''])
        self.assertIn(('fg:red', 'ABCD'), browser.video_area.lexer.image_lines[2])
        browser.video_poster_bounds = lambda: (8, 4)
        browser.apply_video_frame(frame)
        self.assertEqual(browser.video_area.text.split('\n'),
                         ['', '  ABCD', '  EFGH', ''])

    async def test_poster_refits_to_actual_viewport_and_duplicate_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'clip.mp4').write_bytes(b'fixture')
            with patch.object(tui, 'HISTORY_PATH', root / 'history.llog'):
                browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                           input=DummyInput(), output=DummyOutput())
            browser.image_previews = False
            browser.show_info(preview_node=browser.vfs.get_from_path(str(root / 'clip.mp4')))
            browser.video_dimensions = (60, 30)
            def poster(path, file_id, size, bounds, cell_ratio):
                return {'record': {}, 'native': None,
                        'lines': [[('', 'FRAME')] for _ in range(bounds[1])]}
            with patch.object(tui, 'probe_media_type', return_value='video'), patch.object(tui, 'prepare_grid_thumbnail', side_effect=poster) as prepare:
                for height in (3, 7, 2):
                    browser.video_area.window.render_info = SimpleNamespace(window_width=31, window_height=height)
                    await browser._load_video_poster(browser.video_path, browser.video_epoch)
                    self.assertEqual(prepare.call_args.args[3], (30, height))
                    self.assertEqual(len(browser.video_area.text.splitlines()), height)
            browser.info_paths = {}
            larger = browser.video_frame_height()
            browser.info_paths = {index: '/copy' for index in range(9)}
            self.assertEqual(browser.video_info_height(), 6)
            self.assertLess(browser.video_frame_height(), larger)

    async def test_audio_only_mp4_skips_video_poster(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'Trance Classics The Final Chapter.mp4'
            path.write_bytes(b'fixture')
            with patch.object(tui, 'HISTORY_PATH', root / 'history.llog'):
                browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                           input=DummyInput(), output=DummyOutput())
            browser.image_previews = False
            browser.show_info(preview_node=browser.vfs.get_from_path(str(path)))
            with patch.object(tui, 'probe_media_type', return_value='audio') as probe, patch.object(tui, 'prepare_grid_thumbnail', side_effect=AssertionError('no video stream')):
                await browser._load_video_poster(str(path), browser.video_epoch)
            probe.assert_called_once_with(str(path))
            self.assertTrue(browser.audio_selected())
            self.assertIsNone(browser.native_preview)
            self.assertEqual(browser.video_status, 'Audio only · Press Play')
