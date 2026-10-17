"""Bookmark keys and duplicate activation through real terminal input."""
import asyncio
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS

spec = importlib.util.spec_from_file_location('bookmarks_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)

class BookmarkTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        import tempfile
        self.storage = tempfile.TemporaryDirectory()
        self.addCleanup(self.storage.cleanup)
        self.bookmark_file = Path(self.storage.name) / 'bookmarks.json'
        patcher = patch.object(tui, 'BOOKMARKS_PATH', self.bookmark_file)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def test_keys_and_duplicate(self):
        fs = VirtualFS({'files': {'one/a.txt': {'same:3'}, 'two/b.txt': {'same:3'}}, 'hashes': {'same:3': {'one/a.txt', 'two/b.txt'}}})
        fs.enter('one')
        with create_pipe_input() as pipe, patch.object(fs, 'start_in_current_directory'):
            browser = tui.DriveBrowser(fs, input=pipe, output=DummyOutput())
            task = asyncio.create_task(browser.app.run_async())
            async def send(keys):
                pipe.send_text(keys)
                await asyncio.sleep(.08)
            try:
                await asyncio.sleep(.03)
                for view in [None, tui.HelpView(browser, 'Help', ['help']), tui.ActionsView(browser)]:
                    if view:
                        browser.push(view)
                    if not browser.bookmarks:
                        await send('b')
                    await send('b')
                    self.assertEqual(browser.bookmarks, [])
                    await send('b')
                    self.assertEqual(browser.bookmarks, ['/one'])
                    await send('j')
                    await send('1')
                    self.assertFalse(browser.screen_stack)
                    self.assertEqual(fs.pwd(), '/one')
                scanner = tui.ScannerView(browser, startup=False)
                with patch.object(scanner, 'start'):
                    browser.push(scanner)
                browser.app.layout.focus(scanner.limit)
                await send('b')
                self.assertEqual(browser.bookmarks, [])
                await send('b')
                await send('j')
                await send('1')
                for _ in range(100):
                    if not browser.screen_stack:
                        break
                    await asyncio.sleep(.01)
                self.assertFalse(browser.screen_stack)
                self.assertEqual(browser.bookmarks, ['/one'])
                await send('j')
                menu = browser.screen_stack[-1][0]
                await send('b')
                self.assertIn('No bookmarks', menu.list.text)
                menu.path.text = '/one'
                menu.save()
                self.assertIn('1. /one', menu.list.text)
                await send('1')
                browser.refresh('a.txt')
                browser.open()
                self.assertTrue(browser.info_paths)
                row, path = next(iter(browser.info_paths.items()))
                browser.app.layout.focus(browser.info)
                browser.info.buffer.cursor_position = browser.info.buffer.document.translate_row_col_to_index(row, 0)
                self.assertEqual(browser.selected_path(), path)
                await send('\r')
                self.assertEqual(fs.pwd(), '/two')
                self.assertEqual(browser.current_name(), 'b.txt')
            finally:
                browser.app.exit()
                await task

    async def test_file_bookmark_preview_edit_remove_and_jump(self):
        fs = VirtualFS({'files': {'one/a.txt': {'same:3'}, 'two/b.txt': {'same:3'}},
                        'hashes': {'same:3': {'one/a.txt', 'two/b.txt'}}})
        fs.enter('one')
        with create_pipe_input() as pipe, patch.object(fs, 'start_in_current_directory'):
            browser = tui.DriveBrowser(fs, input=pipe, output=DummyOutput())
            browser.refresh('a.txt')
            task = asyncio.create_task(browser.app.run_async())
            async def send(keys):
                pipe.send_text(keys)
                await asyncio.sleep(.08)
            try:
                await asyncio.sleep(.03)
                await send('b')
                self.assertEqual(browser.bookmarks, ['/one/a.txt'])
                await send('j')
                menu = browser.screen_stack[-1][0]
                self.assertIn('/one/a.txt', menu.details.text)
                self.assertIn('Size:', menu.details.text)
                await send('e')
                menu.path.text = '/two/b.txt'
                await send('\r')
                self.assertEqual(browser.bookmarks, ['/two/b.txt'])
                self.assertIn('/two/b.txt', menu.details.text)
                await send('\r')
                self.assertEqual(fs.pwd(), '/two')
                self.assertEqual(browser.current_name(), 'b.txt')
                self.assertIn('/two/b.txt', browser.info.text)
                await send('j')
                await send('\x1b[3~')
                self.assertEqual(browser.bookmarks, [])
            finally:
                browser.app.exit()
                await task

    async def test_local_text_and_image_previews(self):
        import tempfile
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
            root = Path(directory)
            text = root / 'note.txt'
            text.write_text('Bookmark preview content\n', encoding='utf-8')
            image = root / 'picture.png'
            Image.new('RGB', (8, 6), 'red').save(image)
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=pipe, output=DummyOutput())
            browser.refresh(text.name)
            browser.toggle_bookmark()
            self.assertEqual(browser.bookmarks, [str(text)])
            menu = tui.BookmarksView(browser)
            browser.push(menu)
            self.assertIn('Bookmark preview content', menu.details.text)
            menu.path.text = str(image)
            menu.save()
            self.assertIn('Image: 8 x 6', menu.details.text)
            menu.path.text = '/missing/bookmark'
            menu.save()
            self.assertEqual(browser.bookmarks, [str(image)])
            self.assertIn('existing absolute VFS path', menu.details.text)

    async def test_bookmark_marker_in_table_and_grid_updates_after_edits(self):
        fs = VirtualFS({'files': {'one/a.txt': {'same:3'}, 'one/picture.png': {'image:4'}}})
        fs.enter('one')
        with create_pipe_input() as pipe, patch.object(fs, 'start_in_current_directory'):
            browser = tui.DriveBrowser(fs, input=pipe, output=DummyOutput())
            browser.refresh('a.txt')
            def rendered():
                content = browser.control.create_content(60, 24)
                fragments = [part for i in range(content.line_count) for part in content.get_line(i)]
                markers = [(style, text) for style, text in fragments if text == 'B']
                if browser.bookmarks:
                    self.assertTrue(markers)
                    for style, _ in markers:
                        attrs = browser.style().get_attrs_for_style_str(style)
                        self.assertEqual(attrs.color, '00ffff')
                        self.assertTrue(attrs.bold)
                return '\n'.join(''.join(part[1] for part in content.get_line(i))
                                 for i in range(content.line_count))
            for mode in (1, 2, 3):
                browser.display_mode = mode
                browser.refresh('a.txt')
                browser.toggle_bookmark()
                self.assertIn('B 📄 a.txt', rendered())
                browser.toggle_bookmark()
                self.assertNotIn('B 📄 a.txt', rendered())
            browser.graphics_mode = True
            browser.toggle_bookmark()
            self.assertIn('B a.txt', rendered())
            menu = tui.BookmarksView(browser)
            browser.push(menu)
            menu.path.text = '/one/picture.png'
            menu.save()
            self.assertNotIn('B a.txt', rendered())
            self.assertIn('B picture.png', rendered())
            menu.remove()
            self.assertNotIn('B picture.png', rendered())

    async def test_persistence_after_new_browser(self):
        def make():
            fs = VirtualFS({'files': {'one/a.txt': {'same:3'}}})
            fs.enter('one')
            with patch.object(fs, 'start_in_current_directory'):
                return tui.DriveBrowser(fs, input=pipe, output=DummyOutput())
        with create_pipe_input() as pipe:
            browser = make()
            browser.refresh('a.txt')
            browser.toggle_bookmark()
            restored = make()
            self.assertEqual(restored.bookmarks, ['/one/a.txt'])
            menu = tui.BookmarksView(restored)
            restored.push(menu)
            menu.remove()
            self.assertEqual(make().bookmarks, [])

    async def test_bookmark_video_uses_quickview_player_and_controls(self):
        from queue import Queue
        from types import SimpleNamespace
        from unittest.mock import Mock
        fs = VirtualFS({'files': {'one/clip.mov': {'video:3'}, 'one/a.txt': {'text:3'}}})
        fs.enter('one')
        with create_pipe_input() as pipe, patch.object(fs, 'start_in_current_directory'):
            browser = tui.DriveBrowser(fs, input=pipe, output=DummyOutput())
            browser.bookmarks = ['/one/clip.mov', '/one/a.txt']
            fake = SimpleNamespace(events=Queue(), thread=Mock(), start=Mock(), close=Mock(), seek=Mock())
            poster = {'native': None, 'lines': [[('', 'POSTER')]], 'record': {'file_id': '/one/clip.mov'}}
            with patch.object(tui, 'VideoPreview', return_value=fake), patch.object(tui, 'prepare_grid_thumbnail', return_value=poster):
                menu = tui.BookmarksView(browser)
                browser.push(menu)
                task = asyncio.create_task(browser.app.run_async())
                try:
                    await asyncio.sleep(.08)
                    self.assertEqual(browser.video_path, '/one/clip.mov')
                    fake.start.assert_not_called()
                    browser.app.layout.focus(browser.play_button)
                    pipe.send_text('\r')
                    await asyncio.sleep(.08)
                    fake.start.assert_called_once()
                    fake.events.put(('frame', {'native': None, 'lines': [[('', 'FRAME')]], '_duration': 30}))
                    await asyncio.sleep(.08)
                    self.assertIn('FRAME', browser.video_area.text)
                    browser.seek_video(5)
                    fake.seek.assert_called_with(5)
                    browser.app.layout.focus(menu.table)
                    pipe.send_text('\x1b[B')
                    await asyncio.sleep(.08)
                    fake.close.assert_called()
                    self.assertIsNone(browser.video_player)
                    self.assertIn('/one/a.txt', menu.details.text)
                    menu.close()
                    self.assertFalse(browser.screen_stack)
                finally:
                    browser.app.exit()
                    await task

    async def test_parent_row_bookmarks_current_directory_and_marks_it(self):
        fs = VirtualFS({'files': {'one/child/a.txt': {'same:3'}}})
        fs.enter('one')
        fs.enter('child')
        with create_pipe_input() as pipe, patch.object(fs, 'start_in_current_directory'):
            browser = tui.DriveBrowser(fs, input=pipe, output=DummyOutput())
            browser.refresh('..')
            self.assertEqual(browser.current_name(), '..')
            task = asyncio.create_task(browser.app.run_async())
            try:
                await asyncio.sleep(.03)
                pipe.send_text('b')
                await asyncio.sleep(.08)
                self.assertEqual(browser.bookmarks, ['/one/child'])
                for graphics in (False, True):
                    browser.graphics_mode = graphics
                    content = browser.control.create_content(60, 24)
                    line = ''.join(part[1] for part in content.get_line(0))
                    self.assertIn('B', line)
                    self.assertIn('..', line)
                browser.graphics_mode = False
                browser.bookmarks = ['/one']  # Parent is a different bookmark.
                content = browser.control.create_content(60, 24)
                self.assertNotIn('B', ''.join(part[1] for part in content.get_line(0)))
                browser.bookmarks = ['/one/child']
                pipe.send_text('b')
                await asyncio.sleep(.08)
                self.assertEqual(browser.bookmarks, [])
            finally:
                browser.app.exit()
                await task

    async def test_cursor_restored_on_reopen_restart_and_deletion(self):
        import json
        fs = VirtualFS({'files': {'one/a.txt': {'a:3'}, 'one/b.txt': {'b:3'}}})
        fs.enter('one')
        with create_pipe_input() as pipe, patch.object(fs, 'start_in_current_directory'):
            # Legacy list files still load.
            self.bookmark_file.write_text(json.dumps(['/one/a.txt', '/one/b.txt']))
            def make():
                return tui.DriveBrowser(fs, input=pipe, output=DummyOutput())
            browser = make()
            menu = tui.BookmarksView(browser)
            browser.push(menu)
            menu.table.move(1)
            self.assertEqual(browser.bookmark_index, 1)
            menu.close()
            reopened = tui.BookmarksView(browser)
            browser.push(reopened)
            self.assertEqual(reopened.table.index, 1)
            self.assertIn('/one/b.txt', reopened.details.text)
            restarted = make()
            restored = tui.BookmarksView(restarted)
            restarted.push(restored)
            self.assertEqual(restored.table.index, 1)
            restored.remove()
            self.assertEqual(restored.table.index, 0)
            self.assertEqual(make().bookmark_index, 0)
            restarted.go_bookmark(0)
            self.assertEqual(make().bookmark_index, 0)

    async def test_config_alias_bookmark_loading_editing_and_navigation(self):
        import json
        root = Path(self.storage.name) / 'mounted disk'
        root.mkdir()
        file = root / 'clip.txt'
        file.write_text('alias preview')
        mappings = {'/report/old-disk': {'local': str(root), 'alias': 'disk'}}
        with patch.dict(tui.aliases, {'disk': str(root)}, clear=True), \
                patch.dict(tui.prefixes, mappings, clear=True), create_pipe_input() as pipe:
            self.bookmark_file.write_text(json.dumps({'bookmarks': ['/report/old-disk/clip.txt', str(file)],
                                                     'selected_index': 0}))
            fs = VirtualFS({'files': {}})
            browser = tui.DriveBrowser(fs, path=str(root), input=pipe, output=DummyOutput())
            self.assertEqual(browser.bookmarks, ['/disk/clip.txt'])
            task = asyncio.create_task(browser.app.run_async())
            try:
                await asyncio.sleep(.03)
                pipe.send_text('j')
                await asyncio.sleep(.08)
                menu = browser.screen_stack[-1][0]
                self.assertIn('alias preview', menu.details.text)
                menu.path.text = str(file)
                menu.save()
                self.assertEqual(browser.bookmarks, ['/disk/clip.txt'])
                pipe.send_text('\r')
                await asyncio.sleep(.08)
                self.assertFalse(browser.screen_stack)
                self.assertEqual(fs.pwd(), '/disk')
                self.assertEqual(browser.current_name(), 'clip.txt')
            finally:
                browser.app.exit()
                await task

    async def test_unavailable_bookmark_stays_open_and_alias_boundaries(self):
        with patch.dict(tui.aliases, {'disk': '/mount/data', 'nested': '/mount/data/sub'}, clear=True), \
                patch.dict(tui.prefixes, {}, clear=True), create_pipe_input() as pipe:
            self.assertEqual(tui.normalize_bookmark_path('/mount/data/sub/file'), '/nested/file')
            self.assertEqual(tui.normalize_bookmark_path('/mount/database/file'), '/mount/database/file')
            self.assertEqual(tui.normalize_bookmark_path('/disk/sub/file'), '/disk/sub/file')
            fs = VirtualFS({'files': {}})
            with patch.object(fs, 'start_in_current_directory'):
                browser = tui.DriveBrowser(fs, input=pipe, output=DummyOutput())
            browser.bookmarks = ['/disk/definitely-missing-file']
            menu = tui.BookmarksView(browser)
            browser.push(menu)
            menu.choose()
            self.assertIs(browser.screen_stack[-1][0], menu)
            self.assertIn('config.sh', menu.details.text)
            self.assertEqual(fs.pwd(), '/')
