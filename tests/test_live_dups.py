"""Dups updates after expansion and background checksum promotion."""
import asyncio
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS

spec = importlib.util.spec_from_file_location('dups_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class LiveDupsTests(unittest.IsolatedAsyncioTestCase):
    async def test_expanded_known_files_resolve_counts_without_sync_queries(self):
        with tempfile.TemporaryDirectory() as directory:
            fs = VirtualFS({'files': {}})
            paths = [Path(directory) / name for name in ('a', 'b')]
            for path in paths:
                path.write_bytes(b'data')
                fs.db.add_scanned_file(str(path), 'md5:abc', 4)
            browser = tui.DriveBrowser(fs, path=directory, input=DummyInput(), output=DummyOutput())
            entries = [(node.name, node) for node in fs.list_nodes() if not node.is_dir]
            browser.rows = []  # newly revealed expansion rows have no previous counts
            with patch.object(fs, 'get_hash_dups', side_effect=AssertionError('sync duplicate query')):
                browser.refresh(update_info=False, _entries=entries,
                                _infos={node.id: {'exists': True} for _, node in entries})
            self.assertEqual([row['dups'] for row in browser.rows], ['(?)', '(?)'])
            await browser.dups_task
            self.assertEqual([row['dups'] for row in browser.rows], ['(2)', '(2)'])

    async def test_background_scan_updates_unknown_files_and_directory_counts(self):
        for backend in ('memory', 'sqlite'):
            with tempfile.TemporaryDirectory() as storage, tempfile.TemporaryDirectory() as directory:
                child = Path(directory) / 'child'
                child.mkdir()
                for name in ('a', 'b'):
                    (Path(directory) / name).write_bytes(b'same')
                (child / 'c').write_bytes(b'other')
                browser = tui.DriveBrowser(VirtualFS({'files': {}}, backend, **({'db_path': str(Path(storage) / 'cache.sqlite')} if backend == 'sqlite' else {})), path=directory,
                                           input=DummyInput(), output=DummyOutput())
                files = [row for row in browser.rows if not row['node'].is_dir]
                self.assertEqual([row['dups'] for row in files], ['(?)', '(?)'])
                browser.toggle_scanner()
                scanner = browser.scanners[0]
                scanner.close()
                try:
                    for _ in range(150):
                        if all(row['dups'] == '(2)' for row in files):
                            break
                        await asyncio.sleep(.02)
                    self.assertEqual([row['dups'] for row in files], ['(2)', '(2)'])
                    folder = next(row for row in browser.rows if row['name'] == 'child')
                    self.assertEqual(folder['dups'], '(1)')
                finally:
                    await scanner.stop_scanning()
                    await asyncio.gather(*tuple(browser.app._background_tasks), return_exceptions=True)
