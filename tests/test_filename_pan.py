"""Shift filename navigation through real terminal escape sequences."""
import asyncio
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS

spec = importlib.util.spec_from_file_location('filename_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)

class FilenamePanTests(unittest.IsolatedAsyncioTestCase):
    async def test_shift_navigation_main_grid_popups_and_info(self):
        fs = VirtualFS({'files': {'/folder/' + 'long-name-' * 20 + '.txt': {'MD5:test:1'}}})
        fs.enter('folder')
        with create_pipe_input() as pipe:
            with patch.object(fs, 'start_in_current_directory'):
                b = tui.DriveBrowser(fs, input=pipe, output=DummyOutput())
            task = asyncio.create_task(b.app.run_async())
            async def send(sequence):
                pipe.send_text(sequence)
                await asyncio.sleep(.08)
            try:
                await asyncio.sleep(.1)
                b.selected = len(b.rows) - 1
                b.app.invalidate()
                await asyncio.sleep(.08)
                await send('\x1b[1;2C')
                self.assertEqual(b.filename_pan, 1)
                await send('\x1b[1;2F')
                self.assertGreater(b.filename_pan, 1)
                end = b.filename_pan
                await send('\x1b[5;2~')
                self.assertEqual(b.filename_pan, 0)
                await send('\x1b[6;2~')
                self.assertEqual(b.filename_pan, end)
                await send('\x1b[1;2D')
                self.assertEqual(b.filename_pan, end - 1)
                await send('\x1b[1;2H')
                self.assertEqual(b.filename_pan, 0)
                b.graphics_mode = True
                b.app.invalidate()
                await send('\x1b[1;2F')
                self.assertGreater(b.filename_pan, 0)
                screen = tui.HistoryView(b)
                screen.table.get_rows = lambda: [[('', 'x' * 200)]]
                b.push(screen)
                await asyncio.sleep(.1)
                await send('\x1b[1;2F')
                self.assertGreater(screen.table.pan, 0)
                end = screen.table.pan
                await send('\x1b[1;2D')
                self.assertEqual(screen.table.pan, end - 1)
                await send('\x1b[1;2H')
                self.assertEqual(screen.table.pan, 0)
                screen.close()
                b.info.text = 'a' * 200
                b.app.layout.focus(b.info)
                await send('\x1b[1;2F')
                self.assertEqual(b.info.buffer.cursor_position, 200)
                await send('\x1b[1;2H')
                self.assertEqual(b.info.buffer.cursor_position, 0)
            finally:
                b.app.exit()
                await task

    async def test_longest_name_limits_and_mouse_drag(self):
        from prompt_toolkit.data_structures import Size

        class Output(DummyOutput):
            def get_size(self):
                return Size(rows=30, columns=100)

        fs = VirtualFS({'files': {'/folder/short.txt': {'MD5:test:1'},
                                 '/folder/' + 'long-' * 35 + '.txt': {'MD5:test:1'}}})
        fs.enter('folder')
        with create_pipe_input() as pipe:
            with patch.object(fs, 'start_in_current_directory'):
                b = tui.DriveBrowser(fs, input=pipe, output=Output())
            task = asyncio.create_task(b.app.run_async())
            async def send(sequence):
                pipe.send_text(sequence)
                await asyncio.sleep(.08)
            async def drag(bar, expected):
                positions = b.app.renderer._last_screen.visible_windows_to_write_positions
                window = next(w for w in positions if w.content is bar)
                pos = positions[window]
                x, y = pos.xpos + 1, pos.ypos + 1
                pipe.send_text(f'\x1b[<0;{x};{y}M')
                await asyncio.sleep(.05)
                x = pos.xpos + pos.width
                await send(f'\x1b[<32;{x};{y}M')
                self.assertEqual(bar.table.pan, expected)
                await send(f'\x1b[<0;{x};{y}m')
                self.assertFalse(bar.dragging)
            try:
                await asyncio.sleep(.1)
                b.select(next(i for i, row in enumerate(b.rows) if row['name'] == 'short.txt'))
                await asyncio.sleep(.08)
                maximum = b.filename_maximum()
                self.assertGreater(maximum, 100)
                await send('\x1b[1;2F')
                self.assertEqual(b.filename_pan, maximum)
                await send('\x1b[1;2C' * 3)
                self.assertEqual(b.filename_pan, maximum)
                await drag(b.filename_slider, maximum)
                await send('\x1b[1;2H')
                self.assertEqual(b.filename_pan, 0)
                self.assertEqual(b.fit_name('short.txt', 8), 'short.tx')
                b.filename_pan = maximum
                self.assertEqual(b.fit_name('short.txt', 8), ' ' * 8)
                menu = tui.BookmarksView(b)
                menu.table.get_rows = lambda: [[('', 'short')], [('', 'z' * 220)]]
                b.push(menu)
                await asyncio.sleep(.1)
                await send('\x1b[1;2F')
                self.assertEqual(menu.table.pan, menu.table.maximum_pan())
                await drag(menu.horizontal, menu.table.maximum_pan())
            finally:
                b.app.exit()
                await task
