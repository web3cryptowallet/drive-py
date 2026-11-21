"""Directory Files counts survive SQLite reopening without live UI writes."""
import asyncio
import importlib.util
from pathlib import Path
from queue import Queue
from threading import Event, current_thread, main_thread
import tempfile
import unittest
from unittest.mock import patch

from prompt_toolkit.input import DummyInput, create_pipe_input
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS
from vfs.directory_counts import DirectoryCounts, catalog_directory_counts
from vfs.scanner import DriveScanner, ScanStore

spec = importlib.util.spec_from_file_location('directory_counts_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class DirectoryCountStorageTests(unittest.TestCase):
    def test_exit_cache_restores_without_writes_or_rescan(self):
        with tempfile.TemporaryDirectory() as directory:
            disk = Path(directory) / 'disk'
            disk.mkdir()
            folder = disk / 'folder'
            folder.mkdir()
            database = str(Path(directory) / 'cache.sqlite')
            fs = VirtualFS(None, 'sqlite', db_path=database)
            browser = tui.DriveBrowser(fs, path=str(disk), input=DummyInput(), output=DummyOutput())
            browser.directory_counts.remember({str(folder): 42})
            self.assertIsNone(ScanStore(fs.db).get('directory_count', str(folder)))
            with patch.object(browser.app, 'run'), patch.object(tui.sys, 'stderr'):
                browser.run()
            fs.db.conn.close()
            fs = VirtualFS(None, 'sqlite', db_path=database)
            try:
                browser = tui.DriveBrowser(fs, path=str(disk), input=DummyInput(), output=DummyOutput())
                row = next(row for row in browser.rows if row['name'] == 'folder')
                self.assertEqual(row['dups'], '(42)')
                self.assertNotIn(str(folder), browser.directory_count_pending)
                self.assertEqual(browser.directory_counts.get(str(folder)), 42)
            finally:
                fs.db.conn.close()

    def test_legacy_lite_entries_recover_and_catalog_files_are_not_double_counted(self):
        with tempfile.TemporaryDirectory() as directory:
            disk = Path(directory) / 'disk'
            disk.mkdir()
            (disk / 'sub').mkdir()
            for name in ('one', 'sub/two'):
                (disk / name).write_text('abc')
            database = str(Path(directory) / 'cache.sqlite')
            fs = VirtualFS(None, 'sqlite', db_path=database)
            try:
                scanner = DriveScanner(fs.db, str(disk), Queue(), Event())
                scanner.scan_once(fs.db)
                fs.db.add_scanned_file(str(disk / 'one'), 'md5:test', 3)
                before = fs.db.conn.total_changes
                counts = catalog_directory_counts(database, (), {str(disk): str(disk), str(disk / 'sub'): str(disk / 'sub')})
                self.assertEqual(counts, {str(disk): 2, str(disk / 'sub'): 1})
                self.assertEqual(fs.db.conn.total_changes, before)
                cache = DirectoryCounts(fs.db)
                cache.remember(counts)
                cache.save()
                self.assertEqual(DirectoryCounts(fs.db).get(str(disk)), 2)
            finally:
                fs.db.conn.close()

    def test_fragment_counts_merge_descendants_without_duplicate_directories(self):
        from vfs.adapter.fragmented import FragmentedSQLiteDBAdapter
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / 'cache.sqlite')
            fragment = str(Path(directory) / 'fragment.sqlite')
            db = FragmentedSQLiteDBAdapter(database, {'/disk/sub': fragment}, refragment=True)
            try:
                db.add_scanned_file('/disk/one', 'md5:one', 1)
                db.add_scanned_file('/disk/sub/two', 'md5:two', 2)
                self.assertEqual(catalog_directory_counts(database, (fragment,), {'/disk': '/disk'}), {'/disk': 2})
            finally:
                db.conn.close()


class DirectoryCountUITests(unittest.IsolatedAsyncioTestCase):
    async def test_lite_count_survives_scanner_stop_exit_and_browser_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            disk = root / 'disk'
            disk.mkdir()
            folder = disk / 'folder'
            folder.mkdir()
            for index in range(3):
                (folder / str(index)).write_text('abc')
            database = str(root / 'cache.sqlite')
            fs = VirtualFS(None, 'sqlite', db_path=database)
            browser = tui.DriveBrowser(fs, path=str(disk), input=DummyInput(), output=DummyOutput())
            scanner = tui.ScannerView(browser, startup=False)
            browser.push(scanner)
            try:
                for _ in range(200):
                    if scanner.directory_counts.get(str(folder)) == 3:
                        break
                    await asyncio.sleep(.01)
                self.assertEqual(scanner.directory_counts.get(str(folder)), 3)
            finally:
                await scanner.stop_scanning()
            self.assertFalse(browser.scanners)
            self.assertEqual(browser.directory_counts.get(str(folder)), 3)
            self.assertIsNone(ScanStore(fs.db).get('directory_count', str(folder)))
            with patch.object(browser.app, 'run'), patch.object(tui.sys, 'stderr'):
                browser.run()
            fs.db.conn.close()
            fs = VirtualFS(None, 'sqlite', db_path=database)
            try:
                reopened = tui.DriveBrowser(fs, path=str(disk), input=DummyInput(), output=DummyOutput())
                row = next(row for row in reopened.rows if row['name'] == 'folder')
                self.assertEqual(row['dups'], '(3)')
            finally:
                if reopened.directory_count_task:
                    await reopened.directory_count_task
                fs.db.conn.close()

    async def test_background_restore_does_not_block_keyboard_or_write_live_counts(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
            root = Path(directory)
            disk = root / 'disk'
            disk.mkdir()
            folder = disk / 'folder'
            folder.mkdir()
            (disk / 'second').mkdir()
            database = str(root / 'cache.sqlite')
            fs = VirtualFS(None, 'sqlite', db_path=database)
            fs.db.add_scanned_file(str(folder / 'one'), 'md5:one', 1)
            fs.db.add_scanned_file(str(folder / 'sub/two'), 'md5:two', 1)
            entered, release = Event(), Event()
            original = tui.catalog_directory_counts

            def read(*args):
                self.assertIsNot(current_thread(), main_thread())
                entered.set()
                release.wait(3)
                return original(*args)

            async def until(predicate):
                for _ in range(300):
                    if predicate():
                        return
                    await asyncio.sleep(.01)
                self.fail('Directory count UI did not settle')

            with patch.object(tui, 'catalog_directory_counts', side_effect=read):
                browser = tui.DriveBrowser(fs, path=str(disk), input=pipe, output=DummyOutput())
                app = asyncio.create_task(browser.app.run_async(set_exception_handler=False))
                try:
                    await until(entered.is_set)
                    previous = browser.selected
                    pipe.send_text('\x1b[B')
                    await until(lambda: browser.selected != previous)
                    release.set()
                    await until(lambda: browser.directory_counts.get(str(folder)) == 2)
                    row = next(row for row in browser.rows if row['name'] == 'folder')
                    self.assertEqual(row['dups'], '(2)')
                    self.assertIsNone(ScanStore(fs.db).get('directory_count', str(folder)))
                finally:
                    release.set()
                    if browser.directory_count_task:
                        await browser.directory_count_task
                    browser.app.exit()
                    await app
                    fs.db.conn.close()
