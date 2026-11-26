"""Visible-list counts include expanded descendants and active filters."""
# IMPORT TEST LISTING STATS DEPENDENCIES [
import importlib.util
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch

from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS
# IMPORT TEST LISTING STATS DEPENDENCIES ]
# PREPARE TEST LISTING STATS SHARED STATE [
spec = importlib.util.spec_from_file_location('stats_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)
# PREPARE TEST LISTING STATS SHARED STATE ]
# VERIFY LISTING STATS BEHAVIOR [
class ListingStatsTests(unittest.IsolatedAsyncioTestCase):

    # VERIFY COUNTS EXPANSION FILTERS AND METADATA ROW [
    async def test_connected_disk_free_total_and_unavailable(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / 'file.txt'
            file.write_text('hello')
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=DummyInput(), output=DummyOutput())
            browser.image_previews = False
            node = browser.vfs.get_from_path(str(file))
            with patch('shutil.disk_usage', return_value=SimpleNamespace(free=12_000_000_000, total=512_000_000_000)) as usage:
                browser.show_info(preview_node=node)
                lines = browser.info.text.splitlines()
                size_row = next(i for i, line in enumerate(lines) if line.startswith('Size:'))
                self.assertEqual(lines[size_row + 1], 'Disk free: 12.0 GB / 512.0 GB')
                self.assertEqual(lines[size_row + 2:size_row + 4], browser.listing_stats().split(' · '))
                usage.assert_called_once_with(str(file))
            with patch('shutil.disk_usage', side_effect=OSError('offline')):
                browser.show_info(preview_node=node)
                self.assertNotIn('Disk free:', browser.info.text)


class SynchronousListingStatsTests(unittest.TestCase):
    def test_counts_expansion_filters_and_metadata_row(self):
        fs = VirtualFS({'files': {f'/disk/{name}': {'MD5:test:1'} for name in
                         ['folder/a.txt', 'folder/nested/child.txt', '.hidden.txt', 'photo.png', 'plain.txt']}})
        fs.enter('disk')
        with patch.object(fs, 'start_in_current_directory'):
            browser = tui.DriveBrowser(fs, input=DummyInput(), output=DummyOutput())
        self.assertEqual(browser.listing_stats(), 'Dirs: 1 · Files: 3')
        lines = browser.info.text.splitlines()
        size_row = next(i for i, line in enumerate(lines) if line.startswith('Size:'))
        self.assertEqual(lines[size_row + 1:size_row + 3], browser.listing_stats().split(' · '))
        browser.selected = next(i for i, row in enumerate(browser.rows) if row['name'] == 'folder')
        player = object()
        browser.video_player = player
        browser.expand_subdirs()
        self.assertIs(browser.video_player, player)
        browser.video_player = None
        self.assertEqual(browser.listing_stats(), 'Dirs: 2 · Files: 4')
        self.assertIn(browser.listing_stats().replace(' · ', '\n'), browser.info.text)
        browser.toggle_graphics()
        self.assertEqual(browser.listing_stats(), 'Dirs: 0 · Files: 4')
        browser.toggle_dotfiles()
        self.assertEqual(browser.listing_stats(), 'Dirs: 0 · Files: 3')
        with patch.object(browser, 'show_notification'):
            browser.toggle_media_filter()
        self.assertEqual(browser.listing_stats(), 'Dirs: 0 · Files: 1')
        browser.rows = []
        self.assertEqual(browser.listing_stats(), 'Dirs: 0 · Files: 0')
    # VERIFY COUNTS EXPANSION FILTERS AND METADATA ROW ]
# VERIFY LISTING STATS BEHAVIOR ]
