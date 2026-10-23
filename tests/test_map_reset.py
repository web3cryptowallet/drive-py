"""Main Shift+R clears only the current folder's map/resume records."""
# IMPORT TEST MAP RESET DEPENDENCIES [
import asyncio
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS
from vfs.scanner import ScanStore
# IMPORT TEST MAP RESET DEPENDENCIES ]
# PREPARE TEST MAP RESET SHARED STATE [
spec = importlib.util.spec_from_file_location('pt_map_reset', Path(__file__).resolve().parents[1] / 'drive-tui.py')
pt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pt)
# PREPARE TEST MAP RESET SHARED STATE ]
# VERIFY MAP RESET BEHAVIOR [
class MapResetTests(unittest.IsolatedAsyncioTestCase):
    # VERIFY MAIN BINDING SCOPES AND SQLITE REOPENING [
    async def test_main_binding_scopes_and_sqlite_reopening(self):
        for backend in ('memory', 'sqlite'):
            with self.subTest(backend=backend), tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
                db_path = str(Path(directory) / 'cache.sqlite')
                data = {'files': {'/active/file': {'MD5:test:3'}}}
                if backend == 'sqlite':
                    fs = VirtualFS(None, 'sqlite', db_path=db_path)
                    fs.update(data)
                else:
                    fs = VirtualFS(data)
                fs.enter('active')
                with patch.object(fs, 'start_in_current_directory'):
                    browser = pt.DriveBrowser(fs, input=pipe, output=DummyOutput())
                path = fs.pwd()
                store = ScanStore(fs.db)
                for kind in ('map', 'position', 'entry', 'checksum'):
                    store.put(kind, path, {'fixture': kind})
                store.put('map', '/other', {'keep': True})
                store.put('map', '/active/child', {'keep': True})
                task = asyncio.create_task(browser.app.run_async())
                try:
                    await asyncio.sleep(.03)
                    pipe.send_text('h')
                    await asyncio.sleep(.03)
                    pipe.send_text('R')
                    await asyncio.sleep(.03)
                    self.assertIsNotNone(store.get('map', path))
                    pipe.send_text('hR')
                    await asyncio.sleep(.05)
                    self.assertIsNone(store.get('map', path))
                    self.assertIsNone(store.get('position', path))
                    self.assertEqual(store.get('entry', path), {'fixture': 'entry'})
                    self.assertEqual(store.get('checksum', path), {'fixture': 'checksum'})
                    self.assertEqual(store.get('map', '/other'), {'keep': True})
                    self.assertEqual(store.get('map', '/active/child'), {'keep': True})
                    self.assertEqual(fs.pwd(), path)
                    self.assertIn('cleared', browser.info.text)
                    scanner = pt.ScannerView(browser, startup=False)
                    self.assertFalse(scanner.model.entries)
                    self.assertFalse(store.delete('map', path))
                finally:
                    browser.app.exit()
                    await task
                if backend == 'sqlite':
                    fs.db.conn.close()
                    reopened = VirtualFS(None, 'sqlite', db_path=db_path)
                    try:
                        store = ScanStore(reopened.db)
                        self.assertIsNone(store.get('map', path))
                        self.assertIsNone(store.get('position', path))
                        self.assertEqual(store.get('map', '/other'), {'keep': True})
                    finally:
                        reopened.db.conn.close()
    # VERIFY MAIN BINDING SCOPES AND SQLITE REOPENING ]
# VERIFY MAP RESET BEHAVIOR ]
