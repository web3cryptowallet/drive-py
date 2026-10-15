"""Hash throughput is visible before a large file completes."""
import hashlib
from pathlib import Path
from queue import Queue
from threading import Event
import tempfile
import unittest
from unittest.mock import patch

from vfs import VirtualFS
from vfs.scanner import DriveScanner, ScanControls, ScanEntry, ScanStats


class HashRateTests(unittest.TestCase):
    def test_chunk_progress_reports_speed_before_completion_and_expires(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'large'
            file.write_bytes(b'x' * (3 * 1024 * 1024))
            fs = VirtualFS({'files': {}})
            controls = ScanControls((False, False, True))
            events = Queue()
            clock = [100.]
            digest = hashlib.md5()

            class TimedHasher:
                digest_size = digest.digest_size

                def update(self, chunk):
                    clock[0] += .25  # Deterministic hashing/read time per chunk.
                    digest.update(chunk)

                def hexdigest(self):
                    return digest.hexdigest()

            with patch('vfs.scanner.time.monotonic', side_effect=lambda: clock[0]), patch(
                    'vfs.scanner.hashlib.new', return_value=TimedHasher()):
                scanner = DriveScanner(fs.db, directory, events, Event(), controls=controls,
                    entries=[ScanEntry(str(file), str(file), False, file.stat().st_size)])
                scanner.scan_once(fs.db)
                samples = [value for kind, value in events.queue if kind == 'stats']
                in_progress = [value for value in samples if value.bytes_read and value.paths == 0]
                self.assertEqual([value.bytes_read for value in in_progress],
                                 [1024 * 1024, 2 * 1024 * 1024, 3 * 1024 * 1024])
                for sample in in_progress:
                    with patch('vfs.scanner.time.monotonic', return_value=sample.hash_samples[-1][0]):
                        self.assertAlmostEqual(sample.mb_per_second, 4 * 1024 * 1024 / 1_000_000)
                        self.assertEqual(sample.paths_per_second, 0)
                final = samples[-1]
                self.assertEqual(final.paths, 1)
                self.assertEqual(final.size_scanned, 3 * 1024 * 1024)
                self.assertAlmostEqual(final.mb_per_second, 4 * 1024 * 1024 / 1_000_000)
                clock[0] += 1.1
                self.assertEqual(final.mb_per_second, 0)
                self.assertEqual(final.bytes_read, 3 * 1024 * 1024)

    def test_metadata_completions_do_not_count_as_hashed_bytes(self):
        fs = VirtualFS({'files': {}})
        events = Queue()
        with patch('vfs.scanner.time.monotonic', return_value=100.):
            scanner = DriveScanner(fs.db, '/', events, Event())
            scanner.paths = 1
            scanner.report_stats(completed_size=10 ** 12, force=True)
            stats = events.get_nowait()[1]
            self.assertEqual(stats.mb_per_second, 0)
            self.assertEqual(stats.paths_per_second, .2)

    def test_legacy_statistics_still_accept_previous_fields(self):
        with patch('vfs.scanner.time.monotonic', return_value=100.):
            stats = ScanStats(rate_samples=((100., 5, 10_000_000),))
            self.assertEqual(stats.mb_per_second, 2.)
            self.assertEqual(stats.paths_per_second, 1.)
