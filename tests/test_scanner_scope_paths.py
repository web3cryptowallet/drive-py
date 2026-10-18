"""Scanner directory scopes color only matching path prefixes."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from vfs.scanner import ScanEntry

spec = importlib.util.spec_from_file_location(
    'scope_paths', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class ScopePathTests(unittest.TestCase):
    def make_view(self, paths):
        view = object.__new__(tui.ScannerView)
        view.model = SimpleNamespace(entries={
            str(i): ScanEntry(str(i), path, is_dir, size=12, progress=30)
            for i, (path, is_dir) in enumerate(paths)})
        view.detail_ids = list(view.model.entries)
        view.details = SimpleNamespace(index=0)
        view.scope_path = view.scope_anchor = view.scope_depth = None
        view.scope_color = None
        view.refresh_colors = Mock()
        view.invalidate = Mock()
        view.save = Mock()
        view.fixed_colors = {}
        return view

    def gold(self, row):
        return ''.join(text for style, text in row if style == 'fg:#ffd700')

    def test_clear_fixed_colors_keeps_scope_and_removes_saved_pins(self):
        view = self.make_view([('/a/file', False), ('/b/file', False)])
        view.model.buckets = [SimpleNamespace(ids=[key]) for key in view.detail_ids]
        view.grid = Mock()
        view.scope_indices = set()
        view.backgrounds = {}
        view.refresh_colors = lambda: tui.ScannerView.refresh_colors(view)
        view.scope_path, view.scope_color = '/a', '#404040'
        view.fixed_colors = {'0': '#202020', '1': '#606060'}
        view.clear_fixed_colors()
        self.assertEqual(view.fixed_colors, {})
        self.assertEqual(view.backgrounds, {0: '#404040'})
        self.assertEqual(view.scope_path, '/a')
        self.assertEqual(self.gold(view.detail_rows()[0]), '/a/')
        view.save.assert_called_once()
        view.invalidate.assert_called_once()
        view.clear_fixed_colors()  # Clearing an empty pin set is harmless.
        self.assertEqual(view.backgrounds, {0: '#404040'})

    def test_scope_preview_overrides_pins_and_restores_them_when_leaving(self):
        view = self.make_view([('/a/b/file', False), ('/a/other', False),
                               ('/x/file', False)])
        view.model.buckets = [SimpleNamespace(ids=[key]) for key in view.detail_ids]
        view.grid = Mock()
        view.scope_indices = set()
        view.backgrounds = {}
        view.refresh_colors = lambda indices=None: tui.ScannerView.refresh_colors(view, indices)
        with patch.object(
                tui.random, 'randint', side_effect=[32] * 3 + [64] * 3 + [96] * 3):
            view.scope(1)
            view.fix_colors()
            self.assertEqual(view.fixed_colors, {'0': '#202020', '1': '#202020'})
            view.scope(1)  # A narrower scope must be visible over the saved pin.
            self.assertEqual(view.backgrounds, {0: '#404040', 1: '#202020'})
            self.assertEqual(view.fixed_colors['0'], '#202020')
            view.refresh_colors([0])  # Live bucket refresh retains the preview.
            self.assertEqual(view.backgrounds[0], '#404040')
            view.fix_colors()  # Explicitly pinning replaces the stored color.
            self.assertEqual(view.fixed_colors['0'], '#404040')
            view.details.index = 2
            view.scope(1)
            self.assertEqual(view.backgrounds, {0: '#404040', 1: '#202020', 2: '#606060'})

    def test_scope_wraps_both_directions_and_resets_for_another_row(self):
        for is_dir, path in [(False, 'a/b/c/file'), (True, 'a/b/c')]:
            with self.subTest(is_dir=is_dir):
                view = self.make_view([(path, is_dir), ('x/y/file', False)])
                for direction, expected in [
                        (-1, ['/a/b/c', '/a/b', '/a', '/a/b/c']),
                        (1, ['/a', '/a/b', '/a/b/c', '/a'])]:
                    view.scope_anchor = view.scope_depth = None
                    for target in expected:
                        view.scope(direction)
                        self.assertEqual(view.scope_path, target)
                        self.assertEqual(self.gold(view.detail_rows()[0]), target.lstrip('/') + '/')
                view.details.index = 1
                view.scope(-1)
                self.assertEqual(view.scope_path, '/x/y')
        for path in ['file', '/a/file']:
            view = self.make_view([(path, False)])
            for direction in [-1, -1, 1, 1]:
                view.scope(direction)
                self.assertEqual(view.scope_path, '/' if path == 'file' else '/a')
        view.detail_ids = []
        view.scope(-1)  # No selected path: no-op.

    def test_brackets_change_only_directory_prefix(self):
        view = self.make_view([('a/b/file1', False), ('a/b/file2', False),
                               ('a/b2/file3', False), ('other/file', False)])
        original = [''.join(text for _, text in row) for row in view.detail_rows()]
        view.scope(1)
        self.assertEqual([self.gold(row) for row in view.detail_rows()],
                         ['a/', 'a/', 'a/', ''])
        view.scope(1)
        rows = view.detail_rows()
        self.assertEqual([self.gold(row) for row in rows], ['a/b/', 'a/b/', '', ''])
        self.assertTrue(''.join(text for _, text in rows[0][-2:]).startswith('file1  '))
        self.assertIn('class:literal', rows[0][-2][0])
        self.assertNotIn('class:literal', rows[0][-1][0])
        self.assertEqual(rows[0][-1][0], '')
        self.assertEqual([''.join(text for _, text in row) for row in rows], original)
        view.scope(-1)
        self.assertEqual(self.gold(view.detail_rows()[0]), 'a/')
        view.clear_colors()
        self.assertTrue(all(not self.gold(row) for row in view.detail_rows()))

    def test_absolute_directory_boundary_and_selected_panned_row(self):
        view = self.make_view([('/a/b/file1', False), ('/a/b', True),
                               ('/a/b2/file', False)])
        view.scope_path = '/a/b'
        rows = view.detail_rows()
        self.assertEqual([self.gold(row) for row in rows], ['/a/b/', '/a/b/', ''])
        # The row's selection style precedes the explicit foreground, and
        # horizontal panning preserves the visible gold suffix of the prefix.
        control = tui.RowsControl(view.detail_rows)
        control.pan = len('S 30% ') + 2 + 3  # progress, status/space, then /a/
        content = control.create_content(80, 3)
        fragments = content.get_line(0)
        self.assertEqual(''.join(text for style, text in fragments if 'fg:#ffd700' in style), 'b/')
        self.assertTrue(all(style.startswith('class:selected ') for style, _ in fragments))
        self.assertTrue(all('fg:#ffd700' not in style for style, text in fragments if text == '1'))
        view.scope_path = '/'
        self.assertEqual(self.gold(view.detail_rows()[0]), '/')
