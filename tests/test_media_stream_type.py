"""Stream type persistence controls icons without promoting untracked files."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS
from vfs.video_preview import probe_media_type

spec = importlib.util.spec_from_file_location('media_type_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class MediaTypeTests(unittest.TestCase):
    def test_probe_distinguishes_audio_video_and_unknown(self):
        for kinds, expected in ((['audio', 'data'], 'audio'),
                                (['audio', 'video'], 'video'), (['video'], 'video'),
                                (['data'], None), ([], None)):
            result = SimpleNamespace(stdout=json.dumps({'streams': [{'codec_type': kind} for kind in kinds]}))
            with patch('vfs.video_preview.subprocess.run', return_value=result):
                self.assertEqual(probe_media_type('/fixture.mp4'), expected)
        with patch('vfs.video_preview.subprocess.run', side_effect=FileNotFoundError):
            self.assertIsNone(probe_media_type('/fixture.mp4'))

    def test_legacy_type_restores_across_symlink_routes_after_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'media'
            target.mkdir()
            path = target / 'song.mp4'
            path.write_bytes(b'audio')
            link = root / 'src'
            link.symlink_to(target, target_is_directory=True)
            database = str(root / 'catalog.sqlite')
            with patch.object(tui, 'HISTORY_PATH', root / 'history.llog'):
                fs = VirtualFS(None, 'sqlite', db_path=database)
                browser = tui.DriveBrowser(fs, path=directory, input=DummyInput(), output=DummyOutput())
                stat = path.stat()
                record = {'type': 'audio', 'size': stat.st_size, 'modified': stat.st_mtime}
                browser.navigation_store.put('media_type', str(link / 'song.mp4'), record)
                self.assertTrue(browser.go_path(str(link)))
                row = next(row for row in browser.rows if row['name'] == 'song.mp4')
                self.assertTrue(browser.file_list_path(row).startswith('♫ '))
                self.assertEqual(browser.navigation_store.get('media_type', str(path)), record)
                fs.db.conn.close()
                fs = VirtualFS(None, 'sqlite', db_path=database)
                try:
                    browser = tui.DriveBrowser(fs, path=str(target), input=DummyInput(), output=DummyOutput())
                    row = next(row for row in browser.rows if row['name'] == 'song.mp4')
                    self.assertEqual(row['node'].info['media_type'], 'audio')
                    self.assertTrue(browser.file_list_path(row).startswith('♫ '))
                    browser.show_info(preview_node=row['node'])
                    self.assertTrue(browser.audio_selected())
                finally:
                    fs.db.conn.close()
                script = r'''
import asyncio, importlib.util, json, sys
from pathlib import Path
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS
source, database, directory = sys.argv[1:]
spec = importlib.util.spec_from_file_location('restart_type_check', source)
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)
tui.HISTORY_PATH = Path(directory).parent / 'child-history.llog'
fs = VirtualFS(None, 'sqlite', db_path=database)
with create_pipe_input() as pipe:
    browser = tui.DriveBrowser(fs, path=directory, input=pipe, output=DummyOutput())
    row = next(row for row in browser.rows if row['name'] == 'song.mp4')
    result = {'type': row['node'].info.get('media_type'), 'label': browser.file_list_path(row)}
    async def quit_app():
        task = asyncio.create_task(browser.app.run_async(set_exception_handler=False))
        await asyncio.sleep(.04)
        pipe.send_text('q')
        await asyncio.wait_for(task, 3)
    asyncio.run(quit_app())
fs.db.conn.close()
print('RESTORED:' + json.dumps(result))
'''
                source = str(Path(__file__).resolve().parents[1] / 'drive-tui.py')
                for _ in range(2):
                    result = subprocess.run([sys.executable, '-c', script, source, database, str(target)],
                                            capture_output=True, text=True, timeout=15, check=True)
                    restored = json.loads(next(line.removeprefix('RESTORED:') for line in result.stdout.splitlines()
                                               if line.startswith('RESTORED:')))
                    self.assertEqual(restored, {'type': 'audio', 'label': '♫ song.mp4'})

    def test_sqlite_type_icon_and_audio_layout_survive_reopen_and_invalidate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            song = root / 'song.mp4'
            movie = root / 'movie.mp4'
            song.write_bytes(b'audio')
            movie.write_bytes(b'video')
            (root / 'notes.txt').write_text('text')
            database = str(root / 'catalog.sqlite')
            with patch.object(tui, 'HISTORY_PATH', root / 'history.llog'):
                fs = VirtualFS(None, 'sqlite', db_path=database)
                fs.db.add_scanned_file(str(movie), 'md5:abc', 5)
                browser = tui.DriveBrowser(fs, path=directory, input=DummyInput(), output=DummyOutput())
                browser.record_media_type(str(song), 'audio')
                browser.record_media_type(str(movie), 'video')
                rows = {row['name']: row for row in browser.rows}
                self.assertTrue(browser.file_list_path(rows['song.mp4']).startswith('♫ '))
                self.assertTrue(browser.file_list_path(rows['movie.mp4']).startswith('▶ '))
                self.assertEqual(rows['song.mp4']['indicator'], 'orange')
                self.assertEqual(rows['movie.mp4']['indicator'], 'green')
                self.assertIsNone(rows['song.mp4']['node'].info.get('hashinfo'))
                content = browser.control.create_content(100, 20)
                for name, icon in (('song.mp4', '♫'), ('movie.mp4', '▶'), ('notes.txt', '📄')):
                    index = next(i for i, row in enumerate(browser.rows) if row['name'] == name)
                    rendered = ''.join(part[1] for part in content.get_line(index))
                    self.assertEqual(rendered.count(icon), 1, rendered)
                    self.assertEqual(sum(rendered.count(mark) for mark in ('♫', '▶', '📄')), 1, rendered)
                    self.assertLess(rendered.index(icon), rendered.index(name))

                fs.db.conn.close()
                fs = VirtualFS(None, 'sqlite', db_path=database)
                try:
                    browser = tui.DriveBrowser(fs, path=directory, input=DummyInput(), output=DummyOutput())
                    browser.image_previews = False
                    rows = {row['name']: row for row in browser.rows}
                    self.assertEqual(rows['song.mp4']['node'].info['media_type'], 'audio')
                    self.assertEqual(rows['movie.mp4']['node'].info['media_type'], 'video')
                    browser.show_info(preview_node=rows['song.mp4']['node'])
                    self.assertTrue(browser.audio_selected())
                    browser.graphics_mode = True
                    content = browser.grid_content(60, 30)
                    fragments = [part for line in range(content.line_count) for part in content.get_line(line)]
                    text = ''.join(part[1] for part in fragments)
                    self.assertEqual(text.count('♫'), 1)
                    self.assertEqual(text.count('▶'), 1)
                    browser.graphics_mode = False
                    browser.media_filter = 'videos'
                    browser.refresh(update_info=False)
                    self.assertNotIn('song.mp4', [row['name'] for row in browser.rows])
                    self.assertIn('movie.mp4', [row['name'] for row in browser.rows])
                    song.write_bytes(b'changed content')
                    browser.media_filter = 'all'
                    browser.refresh(update_info=False)
                    rows = {row['name']: row for row in browser.rows}
                    self.assertNotIn('media_type', rows['song.mp4']['node'].info)
                finally:
                    fs.db.conn.close()
