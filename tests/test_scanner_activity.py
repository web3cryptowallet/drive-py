"""Scanner diagnostics remain useful while directory enumeration blocks."""
from pathlib import Path
from queue import Queue
from threading import Event
import tempfile
import unittest
from unittest.mock import patch

from vfs import VirtualFS
from vfs.scanner import DriveScanner


class ScannerActivityTests(unittest.TestCase):
    def test_current_operation_is_visible_before_directory_io(self):
        with tempfile.TemporaryDirectory() as directory:
            disk = Path(directory) / 'disk'
            disk.mkdir()
            (disk / 'file').write_text('data')
            fs = VirtualFS({'files': {}, 'hashes': {}}, 'memory')
            scanner = DriveScanner(fs.db, str(disk), Queue(), Event())
            import os
            scandir = os.scandir
            observed = []

            def enumerate_directory(path):
                observed.append(scanner.activity[1])
                return scandir(path)

            with patch('vfs.scanner.os.scandir', side_effect=enumerate_directory):
                scanner.scan_once(fs.db)
            self.assertEqual(observed, [f'Enumerating disk directory · {disk}'])
            self.assertEqual(scanner.paths, 2)
            messages = []
            while not scanner.events.empty():
                kind, payload = scanner.events.get_nowait()
                if kind == 'activity':
                    messages.append(payload)
            self.assertTrue(any('Loading saved checksums for directory' in m for m in messages))
            self.assertEqual(messages[-1], 'Scan pass complete')

    def test_log_is_throttled_but_current_step_is_not(self):
        scanner = DriveScanner(None, '/', Queue(), Event())
        with patch('vfs.scanner.time.monotonic', return_value=10.):
            for index in range(100):
                scanner.report_activity('Reading disk metadata', str(index))
        self.assertEqual(scanner.events.qsize(), 1)
        self.assertEqual(scanner.activity, (10., 'Reading disk metadata · 99'))
