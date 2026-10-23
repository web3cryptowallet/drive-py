"""Path display toggles preserve VFS identities and active previews."""
# IMPORT TEST PATH PREFIXES DEPENDENCIES [
import asyncio
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS
from vfs.scanner import ScanEntry, ScanStats
# IMPORT TEST PATH PREFIXES DEPENDENCIES ]
# PREPARE TEST PATH PREFIXES SHARED STATE [
spec = importlib.util.spec_from_file_location('path_prefix_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)
# PREPARE TEST PATH PREFIXES SHARED STATE ]
# VERIFY PATH PREFIX BEHAVIOR [
class PathPrefixTests(unittest.IsolatedAsyncioTestCase):
    # VERIFY X ACROSS MAIN BOOKMARKS SCANNER ACTIONS [
    async def test_x_across_main_bookmarks_scanner_actions(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe, patch.dict(tui.aliases, {'m1': '/media/drive'}, clear=True), patch.object(tui, 'BOOKMARKS_PATH', Path(directory) / 'bookmarks.json'):
            fs = VirtualFS({'files': {'m1/f.txt': {'MD5:abc:3'}}})
            fs.enter('m1')
            with patch.object(fs, 'start_in_current_directory'):
                browser = tui.DriveBrowser(fs, input=pipe, output=DummyOutput())
            browser.startup_path = '/home/start'
            self.assertFalse(browser.show_path_prefixes)
            browser.toggle_path_prefixes()
            self.assertEqual(browser.display_path('/home/start/a'), '~:a')
            self.assertEqual(browser.display_path('/home/starting/a'), ':/home/starting/a')
            self.assertEqual(browser.display_path('/m1/f.txt'), 'm1:/f.txt')
            self.assertEqual(browser.parse_display_path('m1:/f.txt'), '/m1/f.txt')
            browser.refresh('f.txt')
            browser.open()
            task = asyncio.create_task(browser.app.run_async())
            # SEND THE PATH DISPLAY TOGGLE KEY [
            async def send_x():
                await asyncio.sleep(.04)
                pipe.send_text('x')
                await asyncio.sleep(.06)
            # SEND THE PATH DISPLAY TOGGLE KEY ]
            try:
                await asyncio.sleep(.03)
                self.assertIn('m1:/f.txt', browser.info.text)
                with patch.object(browser, 'stop_video') as stop:
                    await send_x()
                    stop.assert_not_called()
                self.assertIn('/media/drive/f.txt', browser.info.text)
                self.assertNotIn('m1:/', browser.info.text)
                self.assertEqual(fs.pwd(), '/m1')
                browser.bookmarks = ['/m1/f.txt']
                menu = tui.BookmarksView(browser)
                browser.push(menu)
                await send_x()
                self.assertTrue(browser.show_path_prefixes)
                self.assertIn('m1:/f.txt', menu.list.text, repr(browser.displayed_paths))
                self.assertEqual(menu.path.text, 'm1:/f.txt')
                browser.app.layout.focus(menu.path)
                pipe.send_text('x')
                await asyncio.sleep(.06)
                self.assertTrue(browser.show_path_prefixes)  # Editing can type x.
                menu.close()
                scanner = tui.ScannerView(browser, startup=False)
                scanner.model.entries = {'f': ScanEntry('f', '/m1/f.txt', False)}
                scanner.model.rebuild()
                scanner.selected = 0
                scanner.follow_end = False
                scanner.detail_ids = ['f']
                scanner.stats = ScanStats(path='/m1/f.txt')
                browser.startup_path = '/media/drive'
                scanner.scope_path = '/m1'
                self.assertIn('~:f.txt', ''.join(text for _, text in scanner.detail_rows()[0]))
                browser.startup_path = '/home/start'
                scanner.scope_path = None
                with patch.object(scanner, 'start'):
                    browser.push(scanner)
                await send_x()
                self.assertIn('/media/drive/f.txt', ''.join(text for _, text in scanner.detail_rows()[0]))
                self.assertIn('/media/drive/f.txt', ''.join(text for _, text in scanner.path_fragments(scanner.stats_text())))
                scanner.close()
                browser.actions = [('remove', '/m1/f.txt')]
                actions = tui.ActionsView(browser)
                browser.push(actions)
                await send_x()
                self.assertEqual(browser.actions, [('remove', '/m1/f.txt')])
                self.assertIn('m1:/f.txt', ''.join(text for _, text in actions.rows()[0]))
            finally:
                browser.app.exit()
                await task
    # VERIFY X ACROSS MAIN BOOKMARKS SCANNER ACTIONS ]
    # VERIFY FULL FILE PATHS IN TABLE COMPACT ROWS AND MEDIA TILES [
    async def test_full_paths_in_all_file_list_layouts(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(tui.aliases, {'m1': '/media/my drive'}, clear=True), patch.object(tui, 'BOOKMARKS_PATH', Path(directory) / 'bookmarks.json'):
            fs = VirtualFS({'files': {'m1/sub/file.txt': {'MD5:abc:3'},
                                      'm1/sub/song.mp3': {'MD5:def:4'},
                                      'm1/sub/child/nested.txt': {'MD5:ghi:5'}}})
            fs.enter('m1')
            fs.enter('sub')
            with patch.object(fs, 'start_in_current_directory'):
                browser = tui.DriveBrowser(fs, output=DummyOutput())
            browser.startup_path = '/other/start'
            browser.expanded_dirs.add('/m1/sub/child')
            browser.refresh('file.txt')
            identities = [row['node'].id for row in browser.rows]
            for prefixed in (True, False, True):
                if browser.show_path_prefixes != prefixed:
                    browser.toggle_path_prefixes()
                for mode in (1, 2, 3):
                    browser.display_mode = mode
                    browser.refresh('file.txt', update_info=False)
                    table = browser.control.create_content(180, 30)
                    for index, row in enumerate(browser.rows):
                        expected = '..' if row['name'] == '..' else (
                            'm1:' + row['node'].id[len('/m1'):] if prefixed else
                            row['name'])
                        rendered = ''.join(text for _, text in table.get_line(index))
                        self.assertIn(expected, rendered)
                        if not prefixed:
                            self.assertNotIn('m1:', rendered)
                            self.assertNotIn('/media/my drive', rendered)
                    with patch.object(browser, 'icon_dimensions', return_value=(120, 3)):
                        grid = browser.grid_content(200, 40)
                        for index, row in enumerate(browser.rows):
                            expected = browser.file_list_path(row)
                            _, first, _, media = browser.grid_positions[index]
                            self.assertIn(expected, ''.join(text for _, text in grid.get_line(first + (3 if media else 0))))
                self.assertEqual([row['node'].id for row in browser.rows], identities)
                self.assertEqual(browser.current_name(), 'file.txt')
    # VERIFY FULL FILE PATHS IN TABLE COMPACT ROWS AND MEDIA TILES ]

# VERIFY PATH PREFIX BEHAVIOR ]
