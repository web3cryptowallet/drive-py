"""Quick View keys select duplicate rows without traversing metadata."""
import asyncio
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.data_structures import Point
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType, MouseButton
from prompt_toolkit.application.current import set_app
from vfs import VirtualFS

spec = importlib.util.spec_from_file_location('quickview_navigation_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class QuickViewNavigationTests(unittest.IsolatedAsyncioTestCase):
    async def test_media_reserves_three_duplicate_rows_and_scrolls(self):
        from prompt_toolkit.data_structures import Size
        class Output(DummyOutput):
            def get_size(self):
                return Size(rows=27, columns=120)
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
            root = Path(directory)
            fs = VirtualFS({'files': {}})
            for number in range(8):
                path = root / f'clip{number}.mp4'
                path.write_text('same')
                fs.db.add_scanned_file(str(path), 'md5:' + 'a' * 32, 4)
            with patch.object(tui, 'HISTORY_PATH', root / 'history.llog'):
                browser = tui.DriveBrowser(fs, path=directory, input=pipe, output=Output())
            browser.image_previews = False
            browser.show_info(preview_node=fs.get_from_path(str(root / 'clip0.mp4')))
            browser.video_dimensions = (40, 100)
            task = asyncio.create_task(browser.app.run_async(set_exception_handler=False))
            try:
                await asyncio.sleep(.15)
                render = browser.info.window.render_info
                self.assertGreaterEqual(render.window_height, 6)
                first_three = sorted(browser.info_paths)[:3]
                self.assertTrue(set(first_three).issubset(render.displayed_lines),
                                (first_three, render.displayed_lines))
                browser.app.layout.focus(browser.info)
                pipe.send_text('\x1b[F')
                await asyncio.sleep(.1)
                last = max(browser.info_paths)
                self.assertEqual(browser.info.buffer.document.cursor_position_row, last)
                self.assertIn(last, browser.info.window.render_info.displayed_lines)
                self.assertGreater(browser.info.window.vertical_scroll, 0)
            finally:
                browser.app.exit()
                await task

    async def test_real_path_filter_excludes_selected_aliases_and_toggle(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
            root = Path(directory)
            folder = root / 'folder'
            folder.mkdir()
            original = folder / 'original.txt'
            original.write_text('same')
            (root / 'copy.txt').write_text('same')
            (root / 'link.txt').symlink_to(original)
            (root / 'copy-link.txt').symlink_to(root / 'copy.txt')
            (root / 'alias').symlink_to(folder, target_is_directory=True)
            paths = [original, root / 'link.txt', root / 'alias' / 'original.txt', root / 'copy.txt', root / 'copy-link.txt']
            fs = VirtualFS({'files': {}})
            for path in paths:
                fs.db.add_scanned_file(str(path), 'md5:' + '0' * 32, 4)
            with patch.object(tui, 'HISTORY_PATH', root / 'history.llog'):
                browser = tui.DriveBrowser(fs, path=directory, input=pipe, output=DummyOutput())
            browser.image_previews = False
            browser.selected = next(i for i, row in enumerate(browser.rows) if row['name'] == 'link.txt')
            browser.show_info()
            self.assertIn('Duplicates (1/4)', browser.info.text)
            self.assertEqual(list(browser.info_paths.values()), [str(root / 'copy-link.txt')])
            browser.app.layout.focus(browser.info)
            task = asyncio.create_task(browser.app.run_async(set_exception_handler=False))
            try:
                await asyncio.sleep(.04)
                with patch.object(tui.os.path, 'realpath', side_effect=AssertionError('toggle must use cached paths')), patch.object(browser, 'show_info', side_effect=AssertionError('preview restarted')):
                    browser.app.layout.focus(browser.control)
                    pipe.send_text('f')
                    await asyncio.sleep(.04)
                    self.assertTrue(browser.app.layout.has_focus(browser.control))
                    self.assertEqual(len(browser.info_paths), 4)
                    self.assertEqual(set(browser.info_paths.values()), {str(original), str(root / 'alias' / 'original.txt'), str(root / 'copy-link.txt'), str(root / 'copy.txt')})
                    self.assertIn('Duplicates (4/4)', browser.info.text)
                    self.assertNotIn(str(root / 'link.txt'), browser.info_paths.values())
                    self.assertIn('· all ·', browser.info.text)
                    pipe.send_text('f')
                    await asyncio.sleep(.04)
                    self.assertEqual(len(browser.info_paths), 1)
                    self.assertIn('· filtered ·', browser.info.text)
            finally:
                browser.app.exit()
                await task

    async def test_selected_path_alias_counts_and_empty_filter_toggle(self):
        from prompt_toolkit.input import DummyInput
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            selected = root / 'selected.txt'
            selected.write_text('same')
            alias = root / 'symlink.txt'
            alias.symlink_to(selected)
            another = root / 'another.txt'
            another.write_text('same')
            fs = VirtualFS({'files': {}})
            for path in (selected, alias, another):
                fs.db.add_scanned_file(str(path), 'md5:' + '0' * 32, 4)
            with patch.object(tui, 'HISTORY_PATH', root / 'history.llog'):
                browser = tui.DriveBrowser(fs, path=directory, input=DummyInput(), output=DummyOutput())
            browser.image_previews = False
            browser.show_info(preview_node=fs.get_from_path(str(selected)))
            self.assertIn('Duplicates (1/2)', browser.info.text)
            self.assertEqual(list(browser.info_paths.values()), [str(another)])
            browser.toggle_duplicate_filter()
            self.assertIn('Duplicates (2/2)', browser.info.text)
            self.assertEqual(set(browser.info_paths.values()), {str(another), str(alias)})
            self.assertNotIn(str(selected), browser.info_paths.values())
            browser.db_trash.move(str(another), archive=False)
            browser.quickview_filter_duplicates = True
            browser.show_info(preview_node=fs.get_from_path(str(selected)))
            self.assertIn('Duplicates (0/1)', browser.info.text)
            self.assertFalse(browser.info_paths)
            browser.toggle_duplicate_filter()
            self.assertIn('Duplicates (1/1)', browser.info.text)
            self.assertEqual(list(browser.info_paths.values()), [str(alias)])
            browser.toggle_duplicate_filter()
            self.assertIn('Duplicates (0/1)', browser.info.text)
            self.assertFalse(browser.info_paths)

    async def test_arrow_selection_focus_and_duplicate_jump(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
            root = Path(directory)
            for name in ('first.txt', 'second.txt'):
                (root / name).write_text('content')
            with patch.object(tui, 'HISTORY_PATH', root / 'history.llog'):
                browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                           input=pipe, output=DummyOutput())
            browser.image_previews = False
            browser.info.text = 'Metadata\nMore metadata\nfirst\nSpacer\nsecond'
            browser.info_paths = {2: str(root / 'first.txt'), 4: str(root / 'second.txt')}
            browser.app.layout.focus(browser.info)
            task = asyncio.create_task(browser.app.run_async(set_exception_handler=False))
            async def key(value):
                pipe.send_text(value)
                await asyncio.sleep(.04)
            try:
                await asyncio.sleep(.04)
                browser.app.layout.focus(browser.control)
                with set_app(browser.app):
                    browser.info.control.create_content(80, 10)
                    browser.info.control.mouse_handler(MouseEvent(
                        position=Point(x=1, y=2), event_type=MouseEventType.MOUSE_DOWN,
                        button=MouseButton.LEFT, modifiers=frozenset()))
                    browser.info.control.mouse_handler(MouseEvent(
                        position=Point(x=1, y=2), event_type=MouseEventType.MOUSE_UP,
                        button=MouseButton.LEFT, modifiers=frozenset()))
                self.assertTrue(browser.app.layout.has_focus(browser.info))
                self.assertEqual(browser.selected_path(), str(root / 'first.txt'))
                browser.info.buffer.cursor_position = 0
                await key('\x1b[B')
                self.assertEqual(browser.selected_path(), str(root / 'first.txt'))
                await key('\x1b[B')
                self.assertEqual(browser.selected_path(), str(root / 'second.txt'))
                await key('\x1b[B')
                self.assertEqual(browser.info.buffer.document.cursor_position_row, 4)
                await key('\x1b[A')
                self.assertEqual(browser.info.buffer.document.cursor_position_row, 2)
                await key('\x1b[D')
                self.assertTrue(browser.app.layout.has_focus(browser.control))
                browser.app.layout.focus(browser.info)
                browser.move_info_duplicate('last')
                self.assertEqual(browser.info.buffer.document.cursor_position_row, 4)
                browser.move_info_duplicate('first')
                browser.move_info_duplicate(10)
                self.assertEqual(browser.info.buffer.document.cursor_position_row, 4)
                browser.move_info_duplicate(-10)
                self.assertEqual(browser.info.buffer.document.cursor_position_row, 2)
                await key('\x1b[C')
                self.assertEqual(browser.current_name(), 'first.txt')
                browser.info.text = 'Metadata\nfirst\nsecond'
                browser.info_paths = {1: str(root / 'first.txt'), 2: str(root / 'second.txt')}
                browser.app.layout.focus(browser.control)
                with set_app(browser.app):
                    browser.info.control.create_content(80, 10)
                    def click(row, moment):
                        with patch.object(tui.time, 'monotonic', return_value=moment):
                            for kind in (MouseEventType.MOUSE_DOWN, MouseEventType.MOUSE_UP):
                                browser.info.control.mouse_handler(MouseEvent(
                                    position=Point(x=1, y=row), event_type=kind,
                                    button=MouseButton.LEFT, modifiers=frozenset()))
                    click(1, 100.)
                    click(2, 100.1)
                    self.assertTrue(browser.app.layout.has_focus(browser.info))
                    self.assertEqual(browser.current_name(), 'first.txt')
                    click(2, 100.2)
                self.assertEqual(browser.current_name(), 'second.txt')
                self.assertTrue(browser.app.layout.has_focus(browser.control))
                browser.info_paths = {}
                browser.info.text = 'one\ntwo\nthree'
                browser.info.buffer.cursor_position = 0
                browser.app.layout.focus(browser.info)
                await key('\x1b[B')
                self.assertEqual(browser.info.buffer.document.cursor_position_row, 1)
            finally:
                browser.app.exit()
                await task
