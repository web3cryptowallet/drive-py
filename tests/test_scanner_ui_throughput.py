"""Live scanner event ingestion and rendered VT100 navigation regressions."""
import asyncio
from io import StringIO
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from prompt_toolkit.data_structures import Size
from prompt_toolkit.input import DummyInput, create_pipe_input
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.output.vt100 import Vt100_Output
from vfs import VirtualFS
from vfs.scanner import ScanEntry

spec = importlib.util.spec_from_file_location('throughput_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class ScannerIngestionTests(unittest.TestCase):
    def test_event_batch_refreshes_each_dirty_bucket_once(self):
        with tempfile.TemporaryDirectory() as directory:
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=DummyInput(), output=DummyOutput())
            scanner = tui.ScannerView(browser, startup=False)
            scanner.model.limit = 100
            scanner.scope_path, scanner.scope_color = '/scan', '#123456'
            scanner.fixed_colors = {'/scan/0': '#abcdef'}
            for index in range(500):
                path = f'/scan/{index}'
                scanner.events.put(('entry', ScanEntry(path, path, False, 3)))
            with patch.object(scanner, 'refresh_colors', wraps=scanner.refresh_colors) as refresh:
                scanner.drain_all()
            self.assertEqual(len(scanner.model.entries), 500)
            self.assertEqual(scanner.directory_sizes['/scan'], 1500)
            refresh.assert_called_once()
            self.assertEqual(refresh.call_args.args[0], set(range(5)))
            self.assertEqual(scanner.backgrounds, dict.fromkeys(range(5), '#123456'))
            scanner.scope_path = None
            scanner.refresh_colors()
            self.assertEqual(scanner.backgrounds, {0: '#abcdef'})

    def test_projection_reuses_filtered_prefix_and_invalidates_exclusions(self):
        with tempfile.TemporaryDirectory() as directory:
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=DummyInput(), output=DummyOutput())
            scanner = tui.ScannerView(browser, startup=False)
            scanner.model.limit = 10
            for index in range(100):
                path = f'/scan/{index}'
                scanner.model.update(ScanEntry(path, path, False))
            scanner.update_catalog()
            prefix = scanner.controls.buckets[0]
            scanner.model.update(ScanEntry('/scan/new', '/scan/new', False))
            with patch.object(browser, 'excluded_directory', wraps=browser.excluded_directory) as lookup:
                scanner.update_catalog()
            self.assertLessEqual(lookup.call_count, 11)
            self.assertIs(scanner.controls.buckets[0], prefix)
            browser.blacklist_enabled = True
            browser.blacklist.add('/scan/0')
            scanner.update_catalog()
            paths = {path for bucket in scanner.controls.buckets for path in bucket}
            self.assertNotIn('/scan/0', paths)
            self.assertIn('/scan/1', paths)
            browser.trashed_roots = ('/scan/1',)
            scanner.update_catalog()
            self.assertNotIn('/scan/1', {path for bucket in scanner.controls.buckets for path in bucket})


class RenderedScannerTests(unittest.IsolatedAsyncioTestCase):
    async def test_backlog_slices_do_not_wait_for_a_display_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=DummyInput(), output=DummyOutput())
            scanner = tui.ScannerView(browser, startup=False)
            for index in range(8):
                scanner.events.put(('phase', str(index)))
            delays = []

            def drain(**kwargs):
                scanner.events.get_nowait()
                if scanner.events.empty():
                    scanner.stop.set()

            async def sleep(delay):
                delays.append(delay)

            with patch.object(scanner, 'drain_all', side_effect=drain), \
                    patch.object(scanner, 'invalidate') as redraw, \
                    patch.object(browser.scan_statistics, 'save', side_effect=AssertionError('UI count write')), \
                    patch.object(tui.asyncio, 'sleep', new=sleep):
                await scanner.tick()
            self.assertEqual(len(delays), 8)
            self.assertTrue(all(delay <= .005 for delay in delays[:-1]))
            redraw.assert_called_once()

    async def test_worker_drains_and_arrow_updates_real_terminal_frame(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
            root = Path(directory)
            disk = root / 'disk'
            disk.mkdir()
            for index in range(1000):
                (disk / f'file-{index:04}').touch()
            fs = VirtualFS(None, 'sqlite', db_path=str(root / 'cache.sqlite'))
            terminal = StringIO()
            output = Vt100_Output(terminal, lambda: Size(rows=40, columns=120),
                                 term='xterm-256color', enable_cpr=False)
            browser = tui.DriveBrowser(fs, path=str(disk), input=pipe, output=output)
            scanner = tui.ScannerView(browser, startup=False)
            browser.push(scanner)
            app = asyncio.create_task(browser.app.run_async())
            try:
                async def complete():
                    while (scanner.engine.paths < 1001 or not scanner.events.empty()
                           or browser.app.renderer.last_rendered_screen is None):
                        await asyncio.sleep(.01)
                await asyncio.wait_for(complete(), 10)
                self.assertEqual(len(scanner.model.entries), 1001)
                previous = list(scanner.detail_ids)
                before = len(terminal.getvalue())
                pipe.send_text('\x1b[C')
                async def moved():
                    while scanner.selected != 1 or len(terminal.getvalue()) <= before:
                        await asyncio.sleep(.01)
                await asyncio.wait_for(moved(), 3)
                self.assertNotEqual(scanner.detail_ids, previous)
                self.assertTrue(scanner.detail_ids)
                self.assertTrue(browser.app.layout.has_focus(scanner.grid))
                self.assertIn('Drive map', terminal.getvalue())
                self.assertIn('\x1b[', terminal.getvalue())
            finally:
                await scanner.stop_scanning()
                browser.app.exit()
                await app
                await asyncio.gather(*tuple(browser.app._background_tasks), return_exceptions=True)
                fs.db.conn.close()
