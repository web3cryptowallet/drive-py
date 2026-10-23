"""Action log persistence and history navigation controls."""
# VERIFY ACTION LOG STORAGE AND HISTORY CONTROLS [
import asyncio
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS
from vfs.action_history import ActionHistory

spec = importlib.util.spec_from_file_location('history_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class ActionHistoryTests(unittest.TestCase):
    def test_roundtrip_grouping_progress_and_deleted_playback(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'history.llog'
            log = ActionHistory(path)
            play = log.add('play', '/audio.mp3', position=0., duration=30.)
            log.add('view image', '/image\n#.png')
            log.update(play, position=12.)
            loaded = ActionHistory(path)
            self.assertEqual(loaded.entries, log.entries)
            self.assertIn('# view image[', path.read_text())
            self.assertEqual(loaded.entries[0]['position'], 12.)
            log.remove(play)
            log.update(play, position=14.)
            self.assertEqual(len(ActionHistory(path).entries), 1)

    def test_history_filter_delete_clear_and_navigation(self):
        with tempfile.TemporaryDirectory() as folder, create_pipe_input() as pipe:
            fs = VirtualFS({'files': {'one/a.txt': {'same:3'}}, 'hashes': {'same:3': {'one/a.txt'}}})
            with patch.object(tui, 'HISTORY_PATH', Path(folder) / 'history.llog'), patch.object(fs, 'start_in_current_directory'):
                browser = tui.DriveBrowser(fs, input=pipe, output=DummyOutput())
            browser.action_history.entries.clear()
            browser.action_history.add('play', '/one/a.txt', position=3., duration=5.)
            browser.action_history.add('view image', '/missing.png')
            view = tui.HistoryView(browser)
            browser.push(view)
            with patch.object(tui, 'get_real_path', side_effect=lambda p: folder if p == '/one/a.txt' else folder + '/absent'):
                self.assertIn('○', view.rows()[0][0][1])
                self.assertIn('●', view.rows()[1][0][1])
                view.toggle()
                self.assertEqual(len(view.entries()), 1)
                view.choose()
                self.assertEqual(fs.pwd(), '/one')
                self.assertEqual(browser.current_name(), 'a.txt')
            view = tui.HistoryView(browser)
            browser.push(view)
            count = len(browser.action_history.entries)
            view.remove()
            self.assertEqual(len(browser.action_history.entries), count - 1)
            view.clear()
            self.assertEqual(ActionHistory(Path(folder) / 'history.llog').entries, [])
class HistoryKeyboardTests(unittest.IsolatedAsyncioTestCase):
    async def test_hotkey_delete_shift_delete_and_filter(self):
        with tempfile.TemporaryDirectory() as folder, create_pipe_input() as pipe:
            fs = VirtualFS({'files': {}, 'hashes': {}})
            with patch.object(tui, 'HISTORY_PATH', Path(folder) / 'history.llog'), patch.object(fs, 'start_in_current_directory'):
                browser = tui.DriveBrowser(fs, input=pipe, output=DummyOutput())
            task = asyncio.create_task(browser.app.run_async())
            try:
                await asyncio.sleep(.05)
                browser.action_history.add('view image', '/missing.png')
                pipe.send_text('l')
                await asyncio.sleep(.08)
                view = browser.screen_stack[-1][0]
                self.assertIsInstance(view, tui.HistoryView)
                count = len(browser.action_history.entries)
                pipe.send_text('\x1b[3~')
                await asyncio.sleep(.08)
                self.assertEqual(len(browser.action_history.entries), count-1)
                browser.action_history.add('view image', '/missing.png')
                pipe.send_text('t')
                await asyncio.sleep(.08)
                self.assertTrue(view.online)
                pipe.send_text('\x1b[3;2~')
                await asyncio.sleep(.08)
                self.assertEqual(browser.action_history.entries, [])
            finally:
                browser.app.exit()
                await task
# VERIFY ACTION LOG STORAGE AND HISTORY CONTROLS ]
