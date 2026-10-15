"""Incremental blue overlays, including regrouping and paused scans."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch, PropertyMock

from vfs.scanner import ScanControls
from views.ScannerScreen import ScannerScreen


class CountingLocations(dict):
    reads = 0

    def __contains__(self, key):
        self.reads += 1
        return super().__contains__(key)

    def __getitem__(self, key):
        self.reads += 1
        return super().__getitem__(key)


class HighlightTests(unittest.TestCase):
    def make_screen(self, size):
        controls = ScanControls((False, False, True), heavy_order='expert')
        controls.buckets = tuple((str(index),) for index in range(size))
        grid = SimpleNamespace(expert_selected=set(), expert_mode=False)
        model = SimpleNamespace(entries=dict.fromkeys(str(i) for i in range(size)),
                                locations=CountingLocations((str(i), i) for i in range(size)),
                                buckets=list(controls.buckets))
        return SimpleNamespace(controls=controls, model=model, query_one=lambda _: grid), grid

    def update(self, screen):
        ScannerScreen.update_expert_selection(screen)

    def test_new_ranges_and_completions_only_map_changed_work(self):
        screen, grid = self.make_screen(5020)
        controls = screen.controls
        controls.expert_queue.extend(controls.buckets[:5000])
        self.update(screen)
        blue = grid.expert_selected
        screen.model.locations.reads = 0
        with patch.object(ScanControls, 'selected_buckets', new_callable=PropertyMock,
                          side_effect=AssertionError('Full queue snapshot on a color update')):
            controls.expert_queue.extend(controls.buckets[5000:])
            self.update(screen)
            self.assertEqual(screen.model.locations.reads, 40)  # Just 20 new anchors.
            controls.claim_expert()
            self.update(screen)
            controls.finish_expert()
            self.update(screen)
            self.assertEqual(screen.model.locations.reads, 40)
        self.assertIs(grid.expert_selected, blue)
        self.assertEqual(blue, set(range(1, 5020)))
        self.assertEqual(controls.selection_changes, {})

    def test_pause_repack_and_shared_anchors_keep_membership_correct(self):
        screen, grid = self.make_screen(3)
        controls = screen.controls
        controls.expert_queue.extend(controls.buckets[:2])
        self.update(screen)
        screen.model.locations = {'0': 0, '1': 0, '2': 1}
        screen.model.buckets = [('0', '1'), ('2',)]
        self.update(screen)
        self.assertEqual(grid.expert_selected, {0})
        controls.claim_expert()
        controls.finish_expert()
        self.update(screen)
        self.assertEqual(grid.expert_selected, {0})  # Second work bucket shares this cell.
        controls.toggle(3)
        controls.expert_queue.append(controls.buckets[2])
        self.update(screen)
        self.assertEqual(grid.expert_selected, set())
        controls.toggle(3)
        self.update(screen)
        self.assertEqual(grid.expert_selected, {0, 1})
        controls.expert_queue.clear()
        self.update(screen)
        self.assertEqual(grid.expert_selected, set())
        self.assertEqual(screen._expert_work, {})

    def test_fast_completion_and_interrupted_head_coalesce_color_changes(self):
        screen, grid = self.make_screen(2)
        controls = screen.controls
        controls.expert_queue.extend(controls.buckets)
        controls.claim_expert()
        controls.finish_expert()
        self.update(screen)
        self.assertEqual(grid.expert_selected, {1})
        controls.claim_expert()
        controls.finish_expert(interrupted=True)
        self.assertEqual(controls.selection_changes, {})
        self.update(screen)
        self.assertEqual(grid.expert_selected, {1})
