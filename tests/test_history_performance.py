"""History indexes avoid disk IO and full row formatting during redraws."""
import asyncio
import importlib.util
from pathlib import Path
from threading import Event, current_thread, main_thread
import tempfile
import time
import unittest
from unittest.mock import patch
from prompt_toolkit.input import DummyInput, create_pipe_input
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS
from vfs.action_history import ActionHistory

spec = importlib.util.spec_from_file_location('history_performance_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


def records(count):
    return [dict(action='view file', path=f'/history-item-{i % 3}.txt',
                 started='2026-11-02T12:00:00+00:00', last_known='2026-11-02T12:00:00+00:00')
            for i in range(count)]


class HistoryIndexPerformanceTests(unittest.TestCase):
    def test_50000_entries_format_visible_rows_only(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(tui, 'HISTORY_PATH', Path(directory) / 'history.llog'):
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=DummyInput(), output=DummyOutput())
            browser.action_history.entries = records(50000)
            view = tui.HistoryView(browser)
            view.async_presence = True
            started = time.perf_counter()
            with patch.object(tui.os.path, 'exists', side_effect=AssertionError('disk IO on redraw')):
                rows = view.rows()
                for _ in range(20):
                    content = view.table.create_content(100, 20)
                    for line in range(20):
                        content.get_line(line)
                    view.table.maximum_pan()
                self.assertEqual(len(rows.cache), 20)
                self.assertEqual(len(view.pending), 3)
                self.assertEqual(len(rows), 50000)
                self.assertTrue(rows[0][0][1].lstrip().startswith('1 ?'))
                view.indexed.availability({'/history-item-0.txt': True, '/history-item-1.txt': False})
                view.online = True
                view.indexed.set_filter(True)
                self.assertTrue(view.rows())
                index = view.indexed.visible[0]
                self.assertTrue(view.rows()[0][0][1].lstrip().startswith(f'{index + 1} ●'))
            print(f'50k history snapshot + 20 redraws: {time.perf_counter() - started:.3f}s')

    def test_background_saves_coalesce_and_flush_without_resurrecting_deleted_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            history = ActionHistory(Path(directory) / 'history.llog')
            writes = []
            original = history._write_snapshot
            def write(entries):
                writes.append(current_thread().name)
                original(entries)
            with patch.object(history, '_write_snapshot', side_effect=write):
                history.start_writer()
                play = history.add('play', '/music.mp3', position=0)
                for position in range(100):
                    history.update(play, position=position)
                history.remove(play)
                history.update(play, position=1000)
                history.add('view file', '/keep.txt')
                history.close_writer()
            loaded = ActionHistory(history.path)
            self.assertEqual([entry['path'] for entry in loaded.entries], ['/keep.txt'])
            self.assertLess(len(writes), 10)
            self.assertTrue(all(name == 'drive-history-writer' for name in writes))


class HistoryPresenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_presence_checks_off_ui_thread_and_reused_by_path(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe, \
                patch.object(tui, 'HISTORY_PATH', Path(directory) / 'history.llog'):
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=pipe, output=DummyOutput())
            browser.action_history.entries = records(3000)
            observed = []
            original = tui.os.path.exists
            def exists(path):
                if str(path).startswith('/history-item-'):
                    observed.append(current_thread() is main_thread())
                    return 'item-0' in path
                return original(path)
            task = asyncio.create_task(browser.app.run_async(set_exception_handler=False))
            try:
                await asyncio.sleep(.04)
                with patch.object(tui.os.path, 'exists', side_effect=exists):
                    view = tui.HistoryView(browser)
                    browser.push(view)
                    for _ in range(100):
                        if len(view.presence) == 3:
                            break
                        await asyncio.sleep(.02)
                    self.assertEqual(len(view.presence), 3)
                    self.assertEqual(observed, [False, False, False])
                    for _ in range(10):
                        browser.app.invalidate()
                        await asyncio.sleep(.01)
                    self.assertEqual(len(observed), 3)
                    view.toggle()
                    self.assertEqual(len(view.rows()), 1000)
                    view.refresh_presence()
                    for _ in range(100):
                        if len(view.presence) == 3:
                            break
                        await asyncio.sleep(.02)
                    self.assertEqual(len(observed), 6)
                    view.close()
            finally:
                browser.app.exit()
                await task


class HistoryInteractionTests(unittest.IsolatedAsyncioTestCase):
    async def test_preview_toggle_drag_and_bounded_contents(self):
        from prompt_toolkit.mouse_events import MouseEvent, MouseEventType, MouseButton
        from prompt_toolkit.data_structures import Point
        from prompt_toolkit.application.current import set_app
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe, \
                patch.object(tui, 'HISTORY_PATH', Path(directory) / 'history.llog'):
            first = Path(directory) / 'first.txt'
            second = Path(directory) / 'second.txt'
            first.write_text('first preview')
            second.write_text('second preview' + 'x' * 20000)
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=pipe, output=DummyOutput())
            browser.action_history.clear()
            browser.action_history.add('view file', str(second))
            browser.action_history.add('view file', str(first))
            task = asyncio.create_task(browser.app.run_async(set_exception_handler=False))
            try:
                await asyncio.sleep(.05)
                view = tui.HistoryView(browser)
                browser.push(view)
                pipe.send_text('v')
                for _ in range(100):
                    if 'first preview' in view.preview.text:
                        break
                    await asyncio.sleep(.02)
                self.assertTrue(view.preview_visible)
                self.assertIn('first preview', view.preview.text)
                count = len(browser.action_history.entries)
                with set_app(browser.app):
                    for kind, y in [(MouseEventType.MOUSE_DOWN, 0),
                                    (MouseEventType.MOUSE_MOVE, 1),
                                    (MouseEventType.MOUSE_UP, 1)]:
                        view.table.mouse_handler(MouseEvent(Point(2, y), kind, MouseButton.LEFT, frozenset()))
                self.assertEqual(view.table.index, 1)
                self.assertFalse(view.table.dragging)
                for _ in range(100):
                    if 'second preview' in view.preview.text:
                        break
                    await asyncio.sleep(.02)
                self.assertIn('second preview', view.preview.text)
                self.assertIn('first 16 KiB', view.preview.text)
                self.assertLess(len(view.preview.text), 17000)
                self.assertEqual(len(browser.action_history.entries), count)
                # Capture keeps dragging outside the table and clamps at the ends.
                view.table.dragging = True
                view.install_drag(browser.app)
                handler = browser.app.renderer.mouse_handlers.mouse_handlers[0][0]
                handler(MouseEvent(Point(0, 1000), MouseEventType.MOUSE_UP, MouseButton.LEFT, frozenset()))
                self.assertEqual(view.table.index, 1)
                self.assertFalse(view.table.dragging)
                pipe.send_text('v')
                await asyncio.sleep(.05)
                self.assertFalse(view.preview_visible)
                view.close()
            finally:
                browser.app.exit()
                await task

    def test_image_missing_and_special_file_previews(self):
        tui.configure_image_terminal()
        from PIL import Image
        import os
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'image.png'
            Image.new('RGB', (40, 20), 'red').save(path)
            entry = records(1)[0]
            entry['path'] = str(path)
            with patch.object(tui, 'get_real_path', side_effect=lambda path: path):
                text, images = tui.HistoryView.read_preview(entry)
                self.assertTrue(images)
                self.assertIn('Size:', text)
                entry['path'] = str(path.parent / 'absent')
                text, _ = tui.HistoryView.read_preview(entry)
                self.assertIn('Preview unavailable:', text)
                entry['path'] = str(path.parent / 'fifo')
                os.mkfifo(entry['path'])
                text, _ = tui.HistoryView.read_preview(entry)
                self.assertIn('Special file', text)
