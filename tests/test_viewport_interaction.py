"""Actual resize and SGR scrollbar input against the rendered main layout."""
# IMPORT TEST VIEWPORT INTERACTION DEPENDENCIES [
import asyncio
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.data_structures import Size
from vfs import VirtualFS
# IMPORT TEST VIEWPORT INTERACTION DEPENDENCIES ]
# PREPARE TEST VIEWPORT INTERACTION SHARED STATE [
spec = importlib.util.spec_from_file_location('viewport_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)
# PREPARE TEST VIEWPORT INTERACTION SHARED STATE ]
# MANAGE RESIZABLE OUTPUT [
class ResizableOutput(DummyOutput):
    size = Size(rows=40, columns=120)

    # RESOLVE SIZE FOR RESIZABLE OUTPUT [
    def get_size(self):
        return self.size
    # RESOLVE SIZE FOR RESIZABLE OUTPUT ]
# MANAGE RESIZABLE OUTPUT ]
# WAIT UNTIL THE EXPECTED UI STATE IS READY [
async def until(predicate):
    for _ in range(100):
        if predicate():
            return
        await asyncio.sleep(.01)
    raise AssertionError('UI did not reach expected state')
# WAIT UNTIL THE EXPECTED UI STATE IS READY ]
# VERIFY VIEWPORT INTERACTION BEHAVIOR [
class ViewportInteractionTests(unittest.IsolatedAsyncioTestCase):
    # VERIFY IMAGE REFITS SHRINK AND GROW NATIVE AND BLOCK [
    async def test_image_refits_shrink_and_grow_native_and_block(self):
        tui.configure_image_terminal()
        from term_image.image import KittyImage, BlockImage
        for renderer in (KittyImage, BlockImage):
            with self.subTest(renderer=renderer.__name__), tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
                path = Path(directory) / 'portrait.png'
                Image.new('RGB', (800, 1600), 'red').save(path)
                fs = VirtualFS({'files': {}})
                output = ResizableOutput()
                with patch.object(fs, 'start_in_current_directory'):
                    browser = tui.DriveBrowser(fs, input=pipe, output=output)
                node = SimpleNamespace(id=str(path), name=path.name, size=10, is_dir=False, info={})
                browser.rows = [dict(node=node, name=path.name, indicator='green', color='white', label=path.name, size='10', dups='')]
                with patch.object(fs, 'get_full_info', return_value={'exists': True, 'size': 10, 'dups': ['/first-duplicate.png'], 'dups_states': [{'exists': True}]}), \
                        patch('term_image.image.auto_image_class', return_value=renderer), \
                        patch.object(KittyImage, 'is_supported', return_value=True):
                    browser.show_info()
                    task = asyncio.create_task(browser.app.run_async())
                    try:
                        await until(lambda: browser.info.window.render_info is not None)
                        heights = []
                        for rows, columns in [(40, 120), (22, 80), (50, 140)]:
                            output.size = Size(rows=rows, columns=columns)
                            browser.app._on_resize()
                            await until(lambda: browser.image_preview_geometry[:2] == (columns, rows))
                            await asyncio.sleep(.04)
                            render = browser.info.window.render_info
                            if renderer is KittyImage:
                                _, (width, height), first = browser.native_preview
                                self.assertTrue(browser.native_visible)
                                self.assertLessEqual(width, render.window_width - 1)
                                visible = [render.input_line_to_visible_line.get(first + i) for i in range(height)]
                                self.assertTrue(all(y is not None and y < render.window_height for y in visible))
                            else:
                                art = [(i, line) for i, line in browser.info_lexer.image_lines.items()
                                       if any('#ff0000' in style for style, _ in line)]
                                height = len(art)
                                self.assertGreater(height, 0)
                                self.assertTrue(all(i in render.input_line_to_visible_line for i, _ in art))
                            first_duplicate = next(iter(browser.info_paths))
                            self.assertIn(first_duplicate, render.input_line_to_visible_line)
                            heights.append(height)
                        self.assertLess(heights[1], heights[0])
                        self.assertGreater(heights[2], heights[1])
                    finally:
                        browser.app.exit()
                        await task
    # VERIFY IMAGE REFITS SHRINK AND GROW NATIVE AND BLOCK ]
    # VERIFY SCROLLBAR CLICK AND DRAG TABLE AND GRID [
    async def test_scrollbar_click_and_drag_table_and_grid(self):
        fs = VirtualFS({'files': {f'/folder/file{i:03}.{"png" if i % 3 else "txt"}': {'MD5:test:1'} for i in range(80)}})
        fs.enter('folder')
        output = ResizableOutput()
        with create_pipe_input() as pipe:
            with patch.object(fs, 'start_in_current_directory'):
                browser = tui.DriveBrowser(fs, input=pipe, output=output)
            task = asyncio.create_task(browser.app.run_async())
            try:
                await until(lambda: browser.files.render_info is not None)
                for graphics in (False, True):
                    browser.graphics_mode = graphics
                    browser.app.invalidate()
                    await asyncio.sleep(.04)
                    position = browser.app.renderer._last_screen.visible_windows_to_write_positions[browser.files]
                    for offset, expected in [(position.height - 1, len(browser.rows) - 1),
                                             (0, 0), ((position.height - 1) // 2, None)]:
                        x, y = position.xpos + position.width, position.ypos + offset + 1
                        pipe.send_text(f'\x1b[<0;{x};{y}M\x1b[<0;{x};{y}m')
                        if expected is None:
                            await until(lambda: 0 < browser.selected < len(browser.rows) - 1)
                        else:
                            await until(lambda: browser.selected == expected)
                    # Hold the left button, move off the narrow track, then
                    # release outside the pane. Motion must work before release.
                    x = position.xpos + position.width
                    top = position.ypos + 1
                    middle = position.ypos + position.height // 2 + 1
                    bottom = position.ypos + position.height
                    pipe.send_text(f'\x1b[<0;{x};{top}M')
                    await until(lambda: browser.files_scrollbar_dragging and browser.selected == 0)
                    pipe.send_text(f'\x1b[<32;{x + 5};{middle}M')
                    await until(lambda: 0 < browser.selected < len(browser.rows) - 1)
                    self.assertTrue(browser.files_scrollbar_dragging)
                    pipe.send_text(f'\x1b[<32;{x + 5};{bottom + 1}M')
                    await until(lambda: browser.selected == len(browser.rows) - 1)
                    pipe.send_text(f'\x1b[<0;{x + 5};{bottom + 1}m')
                    await until(lambda: not browser.files_scrollbar_dragging)
                    await asyncio.sleep(.04)
                    pipe.send_text(f'\x1b[<35;{x};{top}M')  # Hover after release.
                    await asyncio.sleep(.04)
                    self.assertEqual(browser.selected, len(browser.rows) - 1)
            finally:
                browser.app.exit()
                await task
    # VERIFY SCROLLBAR CLICK AND DRAG TABLE AND GRID ]
# VERIFY VIEWPORT INTERACTION BEHAVIOR ]
