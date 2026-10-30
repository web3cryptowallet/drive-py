"""Persistent u exclusions skip entire subtrees and retain colored markers."""
import importlib.util
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS

spec = importlib.util.spec_from_file_location('blacklist_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)

class BlacklistTests(unittest.IsolatedAsyncioTestCase):
    async def test_saved_exclusions_skip_subtrees_and_can_be_bypassed(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(tui, 'BLACKLIST_PATH', Path(directory) / 'blacklist.json'):
            fs = VirtualFS({'files': {'/disk/skip/deep/no.txt': {'a:1'}, '/disk/keep/yes.txt': {'b:1'}}})
            fs.enter('disk')
            def browser():
                with patch.object(fs, 'start_in_current_directory'):
                    return tui.DriveBrowser(fs, input=DummyInput(), output=DummyOutput())
            b = browser()
            b.selected = next(i for i, row in enumerate(b.rows) if row['name'] == 'skip')
            b.toggle_exclusion()
            self.assertEqual(b.blacklist, {'/disk/skip'})
            self.assertEqual(browser().blacklist, b.blacklist)
            b.bookmarks = ['/disk/skip']
            line = b.control.create_content(100, 30).get_line(b.selected)
            text = ''.join(value for _, value in line)
            self.assertIn('B !', text)
            self.assertTrue(any(value == '!' and 'fg:#ff5555' in style for style, value in line))
            b.graphics_mode = True
            b.refresh(update_info=False)
            index = next(i for i, row in enumerate(b.rows) if row['name'] == 'skip')
            b.control.create_content(100, 30)
            line = b.control.create_content(100, 30).get_line(b.grid_positions[index][1])
            self.assertIn('B !', ''.join(value for _, value in line))
            self.assertTrue(any(value == '!' and 'fg:#ff5555' in style for style, value in line))
            b.graphics_mode = False
            b.refresh(update_info=False)
            b.expand_all_levels = True
            b.selected = 0
            original = b.expansion_nodes
            reads = []
            async def read(node):
                reads.append(node.id)
                return await original(node)
            with patch.object(b, 'expansion_nodes', read):
                await b.expand_subdirs_async()
            self.assertFalse(any(path.startswith('/disk/skip') for path in reads))
            self.assertNotIn('skip/deep/no.txt', [row['name'] for row in b.rows])
            self.assertIn('keep/yes.txt', [row['name'] for row in b.rows])
            b.toggle_blacklist()
            b.selected = next(i for i, row in enumerate(b.rows) if row['name'] == 'skip')
            line = b.control.create_content(100, 30).get_line(b.selected)
            self.assertTrue(any(value == '!' and 'fg:#00bb55' in style for style, value in line))
            b.expand_subdirs_sync()
            self.assertIn('skip/deep/no.txt', [row['name'] for row in b.rows])
            b.toggle_blacklist()
            self.assertNotIn('skip/deep/no.txt', [row['name'] for row in b.rows])
            b.selected = next(i for i, row in enumerate(b.rows) if row['name'] == 'skip')
            b.toggle_exclusion()
            self.assertEqual(browser().blacklist, set())

    async def test_keyboard_shortcuts_and_blacklist_view(self):
        import asyncio
        from prompt_toolkit.input import create_pipe_input
        with tempfile.TemporaryDirectory() as directory, patch.object(tui, 'BLACKLIST_PATH', Path(directory) / 'blacklist.json'), create_pipe_input() as pipe:
            fs = VirtualFS({'files': {'/disk/skip/no.txt': {'a:1'}}})
            fs.enter('disk')
            with patch.object(fs, 'start_in_current_directory'):
                b = tui.DriveBrowser(fs, input=pipe, output=DummyOutput())
            b.selected = next(i for i, row in enumerate(b.rows) if row['name'] == 'skip')
            task = asyncio.create_task(b.app.run_async())
            try:
                await asyncio.sleep(.04)
                pipe.send_text('!')
                await asyncio.sleep(.08)
                self.assertEqual(b.blacklist, {'/disk/skip'})
                pipe.send_text('X')
                await asyncio.sleep(.08)
                self.assertFalse(b.blacklist_enabled)
                pipe.send_text('L')
                await asyncio.sleep(.08)
                self.assertTrue(b.screen_stack)
                self.assertIsInstance(b.screen_stack[-1][0], tui.BlacklistView)
                pipe.send_text('\r')
                await asyncio.sleep(.08)
                self.assertEqual(fs.pwd(), '/disk/skip')
                self.assertFalse(b.screen_stack)
                pipe.send_text('L')
                await asyncio.sleep(.08)
                pipe.send_text('\x1b[3~')
                await asyncio.sleep(.08)
                self.assertEqual(b.blacklist, set())
                self.assertEqual(tui.BLACKLIST_PATH.read_text().strip(), '[]')
                self.assertEqual(b.screen_stack[-1][0].table.index, 0)
                pipe.send_text('\r\x1b[3~')
                await asyncio.sleep(.08)
                self.assertEqual(fs.pwd(), '/disk/skip')
            finally:
                b.app.exit()
                await task
