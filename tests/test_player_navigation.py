"""Player navigation and double-click preserve playback intent."""
import importlib.util
from pathlib import Path
import unittest
import tempfile
from unittest.mock import Mock, patch
from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS

spec = importlib.util.spec_from_file_location('navigation_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)

class PlayerNavigationTests(unittest.TestCase):
    def setUp(self):
        storage = tempfile.TemporaryDirectory()
        self.addCleanup(storage.cleanup)
        for name, filename in [('BOOKMARKS_PATH', 'bookmarks.json'), ('HISTORY_PATH', 'history.llog')]:
            patcher = patch.object(tui, name, Path(storage.name) / filename)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_buttons_and_double_click_playback_intent(self):
        fs = VirtualFS({'files': {'/disk/a.mp3': {'a:1'}, '/disk/b.txt': {'b:1'}, '/disk/c.mp4': {'c:1'}}})
        fs.enter('disk')
        with patch.object(fs, 'start_in_current_directory'):
            b = tui.DriveBrowser(fs, input=DummyInput(), output=DummyOutput())
        b.image_previews = False
        first = next(i for i, row in enumerate(b.rows) if row['name'] == 'a.mp3')
        last = next(i for i, row in enumerate(b.rows) if row['name'] == 'c.mp4')
        b.selected = first
        b.show_info()
        with patch.object(b, 'play_video') as play:
            b.next_button.handler()
            self.assertEqual(b.selected, last)
            play.assert_not_called()
            b.video_player = Mock()
            b.previous_button.handler()
            self.assertEqual(b.selected, first)
            play.assert_called_once()
            play.reset_mock()
            b.video_player = Mock()
            b.auto_quick_view = True
            with patch.object(tui.time, 'monotonic', side_effect=[10, 10.1, 11, 11.1]):
                b.click_file(last)
                b.click_file(last)
                play.assert_called_once()
                play.reset_mock()
                b.click_file(first)
                b.click_file(first)
                play.assert_not_called()

            b.bookmarks = ['/disk/c.mp4', '/disk/b.txt', '/disk/a.mp3']
            view = tui.BookmarksView(b)
            b.push(view)
            b.video_player = Mock()
            b.step_media(1)
            self.assertEqual(view.table.index, 2)
            self.assertEqual(b.preview_bookmark_path, '/disk/a.mp3')
            play.assert_called_once()
            play.reset_mock()
            b.step_media(1)
            play.assert_not_called()
