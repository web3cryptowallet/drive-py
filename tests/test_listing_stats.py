"""Visible-list counts include expanded descendants and active filters."""
# IMPORT TEST LISTING STATS DEPENDENCIES [
import importlib.util
from pathlib import Path
import unittest
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
class ListingStatsTests(unittest.TestCase):
    # VERIFY COUNTS EXPANSION FILTERS AND METADATA ROW [
    def test_counts_expansion_filters_and_metadata_row(self):
        fs = VirtualFS({'files': {f'/disk/{name}': {'MD5:test:1'} for name in
                         ['folder/a.txt', 'folder/nested/child.txt', '.hidden.txt', 'photo.png', 'plain.txt']}})
        fs.enter('disk')
        with patch.object(fs, 'start_in_current_directory'):
            browser = tui.DriveBrowser(fs, input=DummyInput(), output=DummyOutput())
        self.assertEqual(browser.listing_stats(), 'Dirs: 1 · Files: 3')
        lines = browser.info.text.splitlines()
        size_row = next(i for i, line in enumerate(lines) if line.startswith('Size:'))
        self.assertEqual(lines[size_row + 1], browser.listing_stats())
        browser.selected = next(i for i, row in enumerate(browser.rows) if row['name'] == 'folder')
        player = object()
        browser.video_player = player
        browser.expand_subdirs()
        self.assertIs(browser.video_player, player)
        browser.video_player = None
        self.assertEqual(browser.listing_stats(), 'Dirs: 2 · Files: 4')
        self.assertIn(browser.listing_stats(), browser.info.text)
        browser.toggle_graphics()
        self.assertEqual(browser.listing_stats(), 'Dirs: 2 · Files: 4')
        browser.toggle_dotfiles()
        self.assertEqual(browser.listing_stats(), 'Dirs: 2 · Files: 3')
        browser.toggle_media_filter()
        self.assertEqual(browser.listing_stats(), 'Dirs: 2 · Files: 1')
        browser.rows = []
        self.assertEqual(browser.listing_stats(), 'Dirs: 0 · Files: 0')
    # VERIFY COUNTS EXPANSION FILTERS AND METADATA ROW ]
# VERIFY LISTING STATS BEHAVIOR ]
