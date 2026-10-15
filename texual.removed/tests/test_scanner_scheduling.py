"""Startup, discovery, expert selector/FIFO scans and directory colors."""
import hashlib
import time
from pathlib import Path
from queue import Queue
from threading import Event, Thread
import tempfile
import unittest
from unittest.mock import patch, PropertyMock

from rich.color import Color
from textual.app import App
from textual.widgets import DataTable
from vfs import VirtualFS
from vfs.scanner import DriveScanner, ScanControls, ScanEntry, ScanStore, ScanStats
from views.ScannerScreen import ScannerScreen, BucketMap


def data_for(paths):
    digest = 'MD5:' + hashlib.md5(b'abc').hexdigest() + ':3'
    return {'files': {str(path): {digest} for path in paths}}


class SchedulingTests(unittest.TestCase):
    def test_startup_runs_all_three_passes_once_then_stops(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'file'
            file.write_bytes(b'abc')
            fs = VirtualFS(data_for([file]))
            controls = ScanControls(startup=True, heavy_order='expert')
            scanner = DriveScanner(fs.db, directory, Queue(), Event(), controls=controls)
            scanner.scan_once(fs.db)
            phases = [payload for kind, payload in scanner.events.queue if kind == 'phase']
            self.assertTrue(phases[0].startswith('Lite'))
            self.assertTrue(phases[1].startswith('Medium'))
            self.assertTrue(phases[2].startswith('Heavy'))
            self.assertEqual(controls.modes, (False, False, False))
            self.assertIsNone(controls.startup_mode)
            self.assertEqual(scanner.entries[str(file)].state, 'verified')
            self.assertEqual(scanner.bytes_read, 3)
            before = scanner.paths
            scanner.scan_once(fs.db)
            self.assertEqual(scanner.paths, before)

    def test_startup_resumes_saved_pending_work(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'file'
            file.write_bytes(b'abc')
            fs = VirtualFS(data_for([file]))
            ScanStore(fs.db).put('position', directory, {
                '1': {'stack': [str(file)], 'seen': [directory], 'partial': False},
                '2': None, '3': None})
            controls = ScanControls(startup=True)
            scanner = DriveScanner(fs.db, directory, Queue(), Event(), controls=controls,
                                   entries=[ScanEntry(directory, directory, True)])
            with patch.object(scanner, 'publish', wraps=scanner.publish) as published:
                scanner.scan_once(fs.db)
            self.assertEqual(published.call_args_list[0].args[1].path, str(file))
            self.assertEqual(controls.modes, (False, False, False))

    def test_mode_changes_cancel_startup_and_prevent_automatic_heavy(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'file'
            file.write_bytes(b'abc')
            fs = VirtualFS(data_for([file]))
            controls = ScanControls(startup=True)
            scanner = DriveScanner(fs.db, directory, Queue(), Event(), controls=controls)
            original = scanner.publish
            changed = False
            def publish(db, entry):
                nonlocal changed
                original(db, entry)
                if not changed:
                    changed = True
                    controls.toggle(2)
            with patch.object(scanner, 'publish', side_effect=publish):
                scanner.scan_once(fs.db)
            self.assertIsNone(controls.startup_mode)
            self.assertFalse(controls.modes[2])
            self.assertEqual(scanner.bytes_read, 0)
            self.assertFalse(any(kind == 'phase' and payload.startswith('Heavy')
                                 for kind, payload in scanner.events.queue))
            for mode in (1, 2, 3):
                control = ScanControls(startup=True)
                control.start_from(mode, str(file))
                self.assertIsNone(control.startup_mode)

    def test_medium_discovers_new_files_and_directories_without_hashing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            known = root / 'known'
            known.write_bytes(b'abc')
            fs = VirtualFS(data_for([known]))
            controls = ScanControls()
            scanner = DriveScanner(fs.db, directory, Queue(), Event(), controls=controls)
            scanner.scan_once(fs.db)
            new_dir = root / 'new-dir'
            new_dir.mkdir()
            fresh = new_dir / 'fresh'
            fresh.write_bytes(b'hello')
            controls.modes = (False, True, False)
            with patch('vfs.scanner.os.open', side_effect=AssertionError('medium must not hash')):
                scanner.scan_once(fs.db)
            self.assertEqual(scanner.entries[str(new_dir)].state, 'directory')
            self.assertEqual(scanner.entries[str(fresh)].state, 'unknown')
            self.assertEqual(scanner.entries[str(fresh)].size, 5)
            self.assertEqual(scanner.entries[str(known)].state, 'verified')
            self.assertIn(str(fresh), fs.db.scan_paths)

    def test_normal_heavy_visits_buckets_sequentially(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            known, fresh = root / 'a-known', root / 'z-new'
            for path in (known, fresh):
                path.write_bytes(b'abc')
            fs = VirtualFS(data_for([known]))
            controls = ScanControls((False, False, True), new_first=True)
            controls.buckets = ((str(known),), (str(fresh),))
            scanner = DriveScanner(fs.db, directory, Queue(), Event(), controls=controls,
                                   entries=[ScanEntry(str(p), str(p), False, 3) for p in (known, fresh)])
            with patch.object(scanner, 'verify', wraps=scanner.verify) as verify:
                scanner.scan_once(fs.db)
            self.assertEqual([call.args[0].path for call in verify.call_args_list],
                             [str(known), str(fresh)])

    def test_expert_selector_sequential_fifo_pause_and_no_duplicates(self):
        controls = ScanControls((False, False, True), heavy_order='expert')
        controls.buckets = tuple((name,) for name in ('new-a', 'new-b', 'unknown', 'modified', 'verified', 'dir'))
        controls.entry_priorities = {'new-a': 0, 'new-b': 0, 'unknown': 1,
                                     'modified': 2, 'verified': 3}
        for _ in range(3):
            self.assertTrue(controls.enqueue_expert())
        self.assertFalse(controls.enqueue_expert())
        self.assertEqual(controls.selected_buckets,
                         (('new-a',), ('new-b',), ('unknown',)))
        self.assertEqual(controls.claim_expert(), ('new-a',))
        self.assertEqual(controls.selected_buckets[0], ('new-a',))
        self.assertFalse(controls.enqueue_expert())
        controls.toggle(3)
        self.assertFalse(controls.enqueue_expert())
        self.assertIsNone(controls.claim_expert())
        controls.finish_expert(interrupted=True)
        controls.toggle(3)
        self.assertEqual(controls.claim_expert(), ('new-a',))
        controls.finish_expert()
        self.assertEqual(controls.selected_buckets[0], ('new-b',))
        controls.toggle_order()
        self.assertEqual(controls.selected_buckets, ())

    def test_mixed_unverified_green_and_missing_bucket_selection(self):
        controls = ScanControls((False, False, True), heavy_order='expert')
        controls.buckets = (('green',), ('mixed-green', 'unknown'), ('missing',), ('modified',))
        controls.entry_priorities = {'green': 3, 'mixed-green': 3, 'unknown': 1,
                                     'missing': 4, 'modified': 2}
        with patch('vfs.scanner.random.choice', side_effect=lambda values: min(values)), patch(
                'vfs.scanner.random.randint', side_effect=lambda low, high: high):
            self.assertEqual(controls.enqueue_expert_batch(), 1)
            self.assertEqual(controls.selected_buckets, (controls.buckets[1],))
            controls.claim_expert()
            controls.entry_priorities['unknown'] = 3
            controls.finish_expert()
            self.assertEqual(controls.enqueue_expert_batch(), 2)
            self.assertEqual(controls.selected_buckets, controls.buckets[2:])

    def test_selector_continuously_adds_one_to_twenty_consecutive_buckets(self):
        controls = ScanControls((False, False, True), heavy_order='expert')
        controls.buckets = tuple((str(i),) for i in range(50))
        controls.entry_priorities = dict.fromkeys((str(i) for i in range(50)), 0)
        with patch('vfs.scanner.random.randint', side_effect=[1, 10, 9]), patch(
                'vfs.scanner.random.choice', side_effect=[49, 39, 30]):
            self.assertEqual(controls.enqueue_expert_batch(), 1)
            self.assertEqual(controls.claim_expert(), ('49',))
            self.assertEqual(controls.enqueue_expert_batch(), 10)
            self.assertEqual(controls.enqueue_expert_batch(), 9)
        self.assertEqual(len(controls.selected_buckets), 20)
        self.assertEqual(len(set(controls.selected_buckets)), 20)
        self.assertEqual(controls.expert_current, ('49',))
        self.assertEqual(controls.expert_queue[0], ('39',))
        with patch('vfs.scanner.random.randint', return_value=6) as draw, patch(
                'vfs.scanner.random.choice', return_value=0):
            self.assertEqual(controls.enqueue_expert_batch(), 6)
            draw.assert_called_once_with(1, 20)
        self.assertEqual(len(controls.selected_buckets), 26)
        self.assertEqual(controls.expert_current, ('49',))  # First range is still scanning.
        self.assertEqual(tuple(controls.expert_queue)[-6:], tuple((str(i),) for i in range(6)))
        controls.finish_expert()
        while controls.claim_expert() is not None:
            controls.finish_expert()
        scanner = DriveScanner(VirtualFS({'files': {}}).db, '/', Queue(), Event(), controls=controls)
        waits = []
        def wait(seconds):
            waits.append(seconds)
            if len(waits) == 2:
                scanner.selector_stop.set()
        with patch('vfs.scanner.random.randint', side_effect=[3, 4]), patch(
                'vfs.scanner.random.uniform', side_effect=[.2, 1.0]) as delay, patch.object(
                scanner.selector_stop, 'wait', side_effect=wait):
            scanner.select_buckets()
        self.assertEqual(waits, [.2, 1.0])
        self.assertEqual(delay.call_count, 2)
        delay.assert_called_with(.2, 1.0)
        self.assertEqual(len(controls.selected_buckets), 7)

    def test_exhausted_selector_skips_unchanged_catalog_polling(self):
        controls = ScanControls((False, False, True), heavy_order='expert')
        scanner = DriveScanner(VirtualFS({'files': {}}).db, '/', Queue(), Event(), controls=controls)
        waits = []
        def wait(seconds):
            waits.append(seconds)
            if len(waits) == 2:
                controls.priority_revision += 1  # A worker result makes eligibility change.
            if len(waits) == 4:
                scanner.selector_stop.set()
        with patch.object(controls, 'enqueue_expert_batch', side_effect=[0, 2, 0]) as enqueue, patch(
                'vfs.scanner.random.uniform', return_value=.2), patch.object(
                scanner.selector_stop, 'wait', side_effect=wait):
            scanner.select_buckets()
        self.assertEqual(enqueue.call_count, 3)
        self.assertEqual(waits, [.05, .05, .2, .05])

    def test_selector_consumes_pool_without_researching_until_empty(self):
        controls = ScanControls((False, False, True), heavy_order='expert')
        controls.buckets = tuple((str(i),) for i in range(6))
        controls.entry_priorities = dict.fromkeys((str(i) for i in range(6)), 0)
        with patch.object(controls, 'expert_eligible_indices', wraps=controls.expert_eligible_indices) as search, patch(
                'vfs.scanner.random.randint', return_value=2), patch(
                'vfs.scanner.random.choice', side_effect=[2, 4, 0, 2]):
            self.assertEqual(controls.enqueue_expert_batch(), 2)
            self.assertEqual(controls.enqueue_expert_batch(), 2)
            self.assertEqual(controls.enqueue_expert_batch(), 2)
            self.assertEqual(search.call_count, 1)
            self.assertFalse(controls.selector_pool)
            self.assertEqual(controls.selected_buckets,
                             (('2',), ('3',), ('4',), ('5',), ('0',), ('1',)))
            controls.claim_expert()
            controls.finish_expert()
            self.assertEqual(controls.enqueue_expert_batch(), 1)
            self.assertEqual(search.call_count, 2)
            self.assertEqual(len(set(controls.selected_buckets)), 6)

    def test_repeated_ranges_append_without_finishing_the_active_bucket(self):
        controls = ScanControls((False, False, True), heavy_order='expert')
        controls.buckets = tuple((str(i),) for i in range(200))
        controls.entry_priorities = dict.fromkeys((str(i) for i in range(200)), 0)
        lengths = [20, 20, 7, 3, 19, 2]
        with patch('vfs.scanner.random.randint', side_effect=lengths) as draw, patch(
                'vfs.scanner.random.choice', side_effect=lambda values: min(values)):
            self.assertEqual(controls.enqueue_expert_batch(), 20)
            self.assertEqual(controls.claim_expert(), ('0',))
            total = 20
            for requested in lengths[1:]:
                self.assertEqual(controls.enqueue_expert_batch(), requested)
                total += requested
                self.assertEqual(controls.selected_buckets, controls.buckets[:total])
                self.assertEqual(controls.expert_current, ('0',))
                self.assertEqual(controls.selector_batch, requested)
            self.assertEqual(draw.call_count, len(lengths))

    def test_selector_adds_remaining_candidates_without_waiting_for_occupied_work(self):
        controls = ScanControls((False, False, True), heavy_order='expert')
        controls.buckets = tuple((str(i),) for i in range(5))
        controls.entry_priorities = dict.fromkeys((str(i) for i in range(5)), 0)
        controls.expert_queue.extend(controls.buckets[:2])
        self.assertEqual(controls.claim_expert(), ('0',))
        with patch('vfs.scanner.random.randint', return_value=20) as draw, patch(
                'vfs.scanner.random.choice', side_effect=lambda values: min(values)):
            self.assertEqual(controls.enqueue_expert_batch(), 3)
            self.assertEqual(controls.selected_buckets, controls.buckets)
            self.assertEqual(controls.enqueue_expert_batch(), 0)
            draw.assert_called_once_with(1, 20)
        self.assertEqual(controls.expert_current, ('0',))

    def test_unknown_tier_becomes_all_green_without_reselecting_occupied_work(self):
        controls = ScanControls((False, False, True), heavy_order='expert')
        controls.buckets = tuple((str(i),) for i in range(3))
        controls.entry_priorities = dict.fromkeys(('0', '1', '2'), 0)
        controls.expert_queue.extend(controls.buckets)
        with patch('vfs.scanner.random.randint', return_value=20) as draw, patch(
                'vfs.scanner.random.choice', side_effect=lambda values: min(values)):
            self.assertEqual(controls.enqueue_expert_batch(), 0)
            for _ in range(2):
                ids = controls.claim_expert()
                controls.entry_priorities[ids[0]] = 3
                controls.finish_expert()
                self.assertEqual(controls.enqueue_expert_batch(), 0)
            ids = controls.claim_expert()
            controls.entry_priorities[ids[0]] = 3
            controls.finish_expert()
            self.assertEqual(controls.enqueue_expert_batch(), 3)
            self.assertEqual(controls.selected_buckets, controls.buckets)
            draw.assert_called_once()

    def test_selection_pauses_and_resumes_with_earlier_work_queued(self):
        controls = ScanControls((False, False, True), heavy_order='expert')
        controls.buckets = tuple((str(i),) for i in range(5))
        controls.entry_priorities = dict.fromkeys((str(i) for i in range(5)), 0)
        controls.expert_queue.extend(controls.buckets[:2])
        controls.toggle(3)
        with patch('vfs.scanner.random.randint', return_value=3) as draw, patch(
                'vfs.scanner.random.choice', return_value=2):
            self.assertEqual(controls.enqueue_expert_batch(), 0)
            draw.assert_not_called()
            controls.toggle(3)
            self.assertEqual(controls.enqueue_expert_batch(), 3)
            self.assertEqual(controls.selected_buckets, controls.buckets)
            draw.assert_called_once()
        controls.start_from(3, '1')
        self.assertEqual(controls.selected_buckets, (('1',),))
        controls.toggle_order()
        self.assertEqual(controls.selected_buckets, ())

    def test_each_tick_uses_one_random_start_then_marks_consecutive_buckets(self):
        controls = ScanControls((False, False, True), heavy_order='expert')
        controls.buckets = tuple((str(i),) for i in range(30))
        controls.entry_priorities = {str(i): 0 for i in range(30) if i != 4}
        with patch('vfs.scanner.random.randint', return_value=20) as length, patch(
                'vfs.scanner.random.choice', return_value=8) as first:
            self.assertEqual(controls.enqueue_expert_batch(), 20)
            length.assert_called_once_with(1, 20)
            self.assertEqual(controls.selected_buckets, tuple((str(i),) for i in range(8, 28)))
            first.assert_called_once()
            self.assertNotIn(4, first.call_args.args[0])
        for _ in range(3):
            controls.claim_expert()
            controls.finish_expert()
        self.assertEqual(controls.claim_expert(), ('11',))
        with patch('vfs.scanner.random.randint', return_value=3), patch(
                'vfs.scanner.random.choice', return_value=29):
            self.assertEqual(controls.enqueue_expert_batch(), 3)
            self.assertEqual(tuple(controls.expert_queue)[-3:], (('29',), ('0',), ('1',)))
        self.assertEqual(controls.expert_current, ('11',))
        controls.finish_expert()
        while controls.claim_expert() is not None:
            controls.finish_expert()
        controls.start_from(3, '7')
        with patch('vfs.scanner.random.randint', return_value=2), patch(
                'vfs.scanner.random.choice', return_value=3):
            self.assertEqual(controls.enqueue_expert_batch(), 2)
            self.assertEqual(controls.selected_buckets, (('7',), ('3',), ('5',)))

    def test_expert_refills_empty_work_queue_without_waiting_for_selector_timer(self):
        with tempfile.TemporaryDirectory() as directory:
            files = [Path(directory) / str(i) for i in range(40)]
            for file in files:
                file.write_bytes(b'abc')
            fs = VirtualFS({'files': {}})
            controls = ScanControls((False, False, True), heavy_order='expert')
            controls.buckets = tuple((str(file),) for file in files)
            controls.entry_priorities = dict.fromkeys((str(file) for file in files), 0)
            scanner = DriveScanner(fs.db, directory, Queue(), Event(), controls=controls,
                                   entries=[ScanEntry(str(file), str(file), False, 3) for file in files])
            # No selector thread or timer runs: the worker must replenish its work.
            with patch('vfs.scanner.random.randint', return_value=20), patch(
                    'vfs.scanner.random.choice', side_effect=lambda values: min(values)):
                for _ in files:
                    scanner.scan_once(fs.db)
            self.assertEqual(scanner.paths, 40)
            self.assertEqual(scanner.bytes_read, 120)
            self.assertTrue(all(entry.state == 'verified' for entry in scanner.entries.values()))
            self.assertEqual(controls.selected_buckets, ())

    def test_expert_scans_only_fifo_head_and_completes_large_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            files = [Path(directory) / name for name in ('large', 'later')]
            files[0].write_bytes(b'x' * (2 * 1024 * 1024))
            files[1].write_bytes(b'abc')
            fs = VirtualFS({'files': {}})
            controls = ScanControls((False, False, True), heavy_order='expert')
            controls.buckets = tuple((str(file),) for file in files)
            controls.entry_priorities = dict.fromkeys((str(file) for file in files), 0)
            controls.expert_queue.extend(controls.buckets)
            scanner = DriveScanner(fs.db, directory, Queue(), Event(), controls=controls,
                                   entries=[ScanEntry(str(file), str(file), False, file.stat().st_size)
                                            for file in files])
            original_items = ScanStore.items
            loads = []
            def items(store, kind):
                loads.append(kind)
                return original_items(store, kind)
            with patch.object(ScanStore, 'items', items):
                scanner.scan_once(fs.db)
                self.assertEqual(scanner.entries[str(files[0])].state, 'verified')
                self.assertEqual(scanner.entries[str(files[1])].state, 'unknown')
                self.assertIsNotNone(ScanStore(fs.db).get('checksum', str(files[0])))
                self.assertEqual(controls.selected_buckets, ((str(files[1]),),))
                scanner.scan_once(fs.db)
            self.assertEqual(loads, ['checksum'])  # Catalog load once, not once per bucket.
            self.assertEqual(scanner.entries[str(files[1])].state, 'verified')
            self.assertEqual(controls.selected_buckets, ())

    def test_unverified_first_green_skip_removed_work_and_all_green_rechecks(self):
        with tempfile.TemporaryDirectory() as directory:
            files = [Path(directory) / name for name in ('known', 'fresh', 'modified', 'verified')]
            for file in files:
                file.write_bytes(b'abc')
            fs = VirtualFS(data_for([files[0], files[2], files[3]]))
            controls = ScanControls((False, False, True), new_first=False, heavy_order='expert')
            controls.buckets = tuple((str(file),) for file in files)
            states = ('unknown', 'unknown', 'modified', 'verified')
            scanner = DriveScanner(fs.db, directory, Queue(), Event(), controls=controls,
                                   entries=[ScanEntry(str(file), str(file), False, 3, state)
                                            for file, state in zip(files, states)])
            with patch.object(controls, 'enqueue_expert_batch', return_value=0):
                scanner.scan_once(fs.db)  # Initialize priorities before exercising manual queueing.
            self.assertEqual([controls.entry_priorities[str(file)] for file in files], [1, 0, 2, 3])
            for _ in range(2):
                self.assertTrue(controls.enqueue_expert())
            self.assertFalse(controls.enqueue_expert())
            self.assertEqual(controls.selected_buckets, controls.buckets[:2])
            scanner.scan_once(fs.db)
            self.assertEqual(scanner.entries[str(files[0])].state, 'verified')
            # A discovery removal can invalidate a waiting bucket before it is claimed.
            scanner.entries.pop(str(files[1]))
            controls.entry_priorities.pop(str(files[1]))
            scanner.scan_once(fs.db)
            self.assertEqual(controls.selected_buckets, ())
            self.assertIsNone(scanner.checkpoints['3'])
            self.assertTrue(controls.enqueue_expert())
            self.assertEqual(controls.selected_buckets, (controls.buckets[2],))
            self.assertFalse(controls.enqueue_expert())  # Green remains blocked by queued modified work.
            scanner.scan_once(fs.db)
            with patch('vfs.scanner.random.randint', side_effect=lambda low, high: high):
                self.assertEqual(controls.enqueue_expert_batch(), 3)  # All surviving files are now green.
            self.assertEqual(set(controls.selected_buckets),
                             {controls.buckets[i] for i in (0, 2, 3)})

    def test_expert_interrupted_head_resumes_before_next_bucket(self):
        with tempfile.TemporaryDirectory() as directory:
            files = [Path(directory) / name for name in ('large', 'later')]
            files[0].write_bytes(b'x' * (2 * 1024 * 1024))
            files[1].write_bytes(b'abc')
            fs = VirtualFS({'files': {}})
            controls = ScanControls((False, False, True), heavy_order='expert')
            controls.buckets = tuple((str(file),) for file in files)
            controls.expert_queue.extend(controls.buckets)
            scanner = DriveScanner(fs.db, directory, Queue(), Event(), controls=controls,
                                   entries=[ScanEntry(str(file), str(file), False, file.stat().st_size)
                                            for file in files])
            report = scanner.report_stats
            def interrupt(**kwargs):
                if kwargs.get('read') and controls.modes[2]:
                    controls.toggle(3)
                report(**kwargs)
            with patch.object(scanner, 'report_stats', side_effect=interrupt):
                scanner.scan_once(fs.db)
            self.assertIsNone(ScanStore(fs.db).get('checksum', str(files[0])))
            self.assertIsNone(fs.db.get_child(fs.get_from_path(directory), 'large'))
            self.assertEqual(controls.selected_buckets, controls.buckets)
            self.assertEqual(scanner.checkpoints['3']['first'], str(files[0]))
            controls.toggle(3)
            scanner.scan_once(fs.db)
            self.assertEqual(scanner.entries[str(files[0])].state, 'verified')
            self.assertEqual(controls.selected_buckets, ((str(files[1]),),))
            self.assertEqual(scanner.entries[str(files[1])].state, 'unknown')

    def test_selector_runs_while_scan_worker_is_blocked_and_joins_on_close(self):
        with tempfile.TemporaryDirectory() as directory:
            files = [Path(directory) / str(index) for index in range(60)]
            for file in files:
                file.write_bytes(b'abc')
            fs = VirtualFS({'files': {}})
            controls = ScanControls((False, False, True), heavy_order='expert')
            controls.buckets = tuple((str(file),) for file in files)
            entered, release = Event(), Event()
            entered_count = []
            scanner = DriveScanner(fs.db, directory, Queue(), Event(), controls=controls,
                                   entries=[ScanEntry(str(file), str(file), False, 3) for file in files])
            verify = scanner.verify
            def blocked(*args):
                entered_count.append(len(controls.selected_buckets))
                entered.set()
                release.wait(3)
                return verify(*args)
            with patch.object(scanner, 'verify', side_effect=blocked), patch(
                    'vfs.scanner.random.randint', return_value=20), patch(
                    'vfs.scanner.random.uniform', return_value=.5):
                worker = Thread(target=scanner.run)
                worker.start()
                try:
                    self.assertTrue(entered.wait(2))
                    self.assertEqual(entered_count[0], 20)
                    # Wait for the selector to fill the queue while the worker cannot proceed.
                    for _ in range(60):
                        if len(controls.selected_buckets) == 60:
                            break
                        Event().wait(.02)
                    self.assertEqual(len(controls.selected_buckets), 60)
                    scanner.stop.set()
                finally:
                    release.set()
                    scanner.stop.set()
                    worker.join(3)
                self.assertFalse(worker.is_alive())
                self.assertFalse(scanner.selector_thread.is_alive())
                self.assertIsNone(ScanStore(fs.db).get('checksum', controls.buckets[0][0]))

    def test_rates_use_only_last_five_seconds_and_totals_stay_cumulative(self):
        scanner = DriveScanner(VirtualFS({'files': {}}).db, '/', Queue(), Event())
        scanner.paths = 100000
        scanner.size_scanned = 10 ** 18
        with patch('vfs.scanner.time.monotonic', return_value=10):
            scanner.report_stats(completed_size=10 ** 12, force=True)
        with patch('vfs.scanner.time.monotonic', return_value=12):
            scanner.report_stats(completed_size=5 * 10 ** 12, force=True)
            stats = scanner.events.queue[-1][1]
            self.assertEqual(stats.paths, 100000)
            self.assertEqual(stats.size_scanned, 10 ** 18)
            self.assertEqual(stats.paths_per_second, .4)
            self.assertEqual(stats.mb_per_second, 1_200_000)  # 1.2 TB/s
        with patch('vfs.scanner.time.monotonic', return_value=15):
            self.assertEqual(stats.paths_per_second, .2)
            self.assertEqual(stats.mb_per_second, 1_000_000)
        with patch('vfs.scanner.time.monotonic', return_value=17):
            self.assertEqual(stats.paths_per_second, 0)
            self.assertEqual(stats.mb_per_second, 0)
            scanner.report_stats(force=True, active=False)
            self.assertFalse(scanner.rate_samples)

    def test_expert_with_directory_only_buckets_does_not_spin(self):
        with tempfile.TemporaryDirectory() as directory:
            fs = VirtualFS({'files': {}})
            controls = ScanControls((False, False, True), heavy_order='expert')
            controls.buckets = ((directory,),)
            scanner = DriveScanner(fs.db, directory, Queue(), Event(), controls=controls,
                                   entries=[ScanEntry(directory, directory, True)])
            scanner.scan_once(fs.db)
            self.assertFalse(scanner.expert_scanned)
            self.assertEqual(scanner.paths, 0)


class ScopeTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_popup_startup_stops_and_j_toggles_expert(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'file'
            file.write_bytes(b'abc')
            fs = VirtualFS(data_for([file]))
            app = App()
            async with app.run_test(size=(80, 24)) as pilot:
                screen = ScannerScreen(fs, directory)
                self.assertEqual(screen.controls.startup_mode, 1)
                app.push_screen(screen)
                await pilot.pause(.4)
                self.assertEqual(screen.controls.modes, (False, False, False))
                self.assertEqual(screen.model.entries[str(file)].state, 'verified')
                await pilot.press('j')
                self.assertEqual(screen.controls.heavy_order, 'expert')
                await pilot.press('3')
                await pilot.pause(.2)
                self.assertTrue(screen.controls.modes[2])
                self.assertIn('expert', screen.phase)
                await pilot.press('3')
                self.assertFalse(screen.controls.modes[2])
                await pilot.press('escape')
                await pilot.pause()
                screen.worker_thread.join(2)
                self.assertFalse(screen.worker_thread.is_alive())

    async def test_expert_queue_blue_highlights_list_and_recent_rate_decay(self):
        with tempfile.TemporaryDirectory() as directory:
            fs = VirtualFS({'files': {}})
            app = App()
            async with app.run_test(size=(80, 24)) as pilot:
                screen = ScannerScreen(fs, directory, startup=False)
                app.push_screen(screen)
                await pilot.pause(.2)
                screen.stop.set()
                screen.worker_thread.join(2)
                self.assertFalse(screen.worker_thread.is_alive())
                while not screen.events.empty():
                    screen.events.get_nowait()
                entries = [ScanEntry('/a', '/a', False), ScanEntry('/b', '/b', False, state='modified')]
                screen.model.limit = 1
                screen.model.entries = {entry.id: entry for entry in entries}
                screen.model.rebuild()
                screen.controls.modes = (False, False, True)
                screen.controls.heavy_order = 'expert'
                screen.controls.expert_queue.extend((('/b',), ('/a',)))
                screen.controls.selector_batch = 2
                screen.redraw()
                grid = screen.query_one(BucketMap)
                self.assertEqual(grid.expert_selected, {0, 1})
                with patch.object(ScanControls, 'selected_buckets', new_callable=PropertyMock) as snapshot:
                    screen.update_expert_selection()
                    snapshot.assert_not_called()  # Unchanged refresh only uses cached colors.
                acquired, release = Event(), Event()
                def hold_selector_lock():
                    with screen.controls.lock:
                        acquired.set()
                        release.wait(2)
                holder = Thread(target=hold_selector_lock)
                holder.start()
                try:
                    self.assertTrue(acquired.wait(1))
                    started = time.perf_counter()
                    screen.update_expert_selection()
                    self.assertLess(time.perf_counter() - started, .1)
                    self.assertEqual(grid.expert_selected, {0, 1})
                finally:
                    release.set()
                    holder.join(2)
                grid.selected = 1
                screen.selection_changed()
                details = screen.query_one('#scan-details', DataTable)
                details.focus()
                await pilot.pause()
                pagination = screen.pagination
                with patch.object(grid, 'reveal_selection') as reveal:
                    screen.events.put(('expert', {'id': '/a'}))
                    screen.drain_events()
                    reveal.assert_not_called()
                self.assertEqual(grid.selected, 1)
                self.assertIs(screen.pagination, pagination)
                self.assertIs(app.focused, details)
                self.assertEqual(details.ordered_rows[0].key.value, '/b')
                grid.follow_end = True
                grid.sync()
                screen.events.put(('expert', {'id': '/a'}))
                screen.drain_events()
                self.assertTrue(grid.follow_end)
                self.assertEqual(grid.selected, 2)
                self.assertIs(screen.pagination, pagination)
                grid.follow_end = False
                grid.selected = 1
                screen.redraw()
                with patch('views.ScannerScreen.time.monotonic', return_value=10):
                    strip = list(grid.render_line(0))
                    self.assertEqual(strip[0].style.bgcolor, Color.parse('#0000ff'))
                    self.assertEqual(strip[1].style.bgcolor, Color.parse('#0000ff'))
                    self.assertEqual(strip[0].style.color, Color.parse('#ffffff'))
                    self.assertEqual(strip[1].style.color, Color.parse('#ff8800'))
                screen.model.buckets[1].updated = 9.5
                self.assertEqual(screen.controls.claim_expert(), ('/b',))
                screen.update_stats()
                self.assertEqual(grid.expert_selected, {0, 1})
                screen.controls.finish_expert()
                screen.update_stats()
                self.assertEqual(grid.expert_selected, {0})
                with patch('views.ScannerScreen.time.monotonic', return_value=10):
                    self.assertEqual(list(grid.render_line(0))[1].style.bgcolor, Color.parse('#000000'))
                    screen.scan_stats = ScanStats(paths=100000, size_scanned=10 ** 18,
                                                  rate_samples=((10, 10, 6 * 10 ** 12),))
                    screen.update_stats()
                    self.assertIn('2.0 paths/s · 1.20 TB/s', str(screen.query_one('#scan-stats').render()))
                with patch('views.ScannerScreen.time.monotonic', return_value=16):
                    screen.drain_events()  # No new worker event needed to expire rates.
                    self.assertIn('0.0 paths/s · 0.00 MB/s', str(screen.query_one('#scan-stats').render()))
                # Regrouping can split an original selected work bucket. Keep one
                # visual anchor per work bucket to avoid duplicate blue highlights.
                screen.controls.expert_queue.clear()
                screen.controls.expert_queue.append(('/a', '/b'))
                screen.update_stats()
                self.assertEqual(grid.expert_selected, {0})
                screen.controls.toggle(3)
                screen.redraw()
                self.assertEqual(grid.expert_selected, set())
                self.assertEqual(screen.controls.selected_buckets, (('/a', '/b'),))
                await pilot.press('escape')
                await pilot.pause()

    async def test_directory_brackets_pin_clear_preserve_foregrounds_and_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            fs = VirtualFS({'files': {}})
            app = App()
            async with app.run_test(size=(80, 24)) as pilot:
                screen = ScannerScreen(fs, directory, startup=False)
                app.push_screen(screen)
                await pilot.pause(.2)
                screen.stop.set()
                screen.worker_thread.join(2)
                while not screen.events.empty():
                    screen.events.get_nowait()
                screen.controls.modes = (False, False, False)
                screen.model.limit = 1
                entries = [ScanEntry('/a', '/a', True),
                           ScanEntry('/a/b/c', '/a/b/c', False),
                           ScanEntry('/a/x', '/a/x', False, state='verified'),
                           ScanEntry('/a2/z', '/a2/z', False, state='modified'),
                           ScanEntry('/a/b/x', '/a/b/x', False)]
                screen.model.entries = {entry.id: entry for entry in entries}
                screen.model.rebuild()
                screen.redraw()
                grid = screen.query_one(BucketMap)
                grid.selected = 1
                screen.selection_changed()
                grid.focus()
                with patch('views.ScannerScreen.random.randint',
                           side_effect=[32,40,48,50,60,70,70,80,90,40,50,60]):
                    await pilot.press('right_square_bracket')
                    self.assertEqual(screen.scope_path, '/a')
                    self.assertIs(app.focused, grid)
                    self.assertEqual(grid.selected, 1)
                    self.assertEqual(screen.scoped_buckets(), [0, 1, 2, 4])
                    outer = screen.scope_color
                    self.assertEqual(grid.backgrounds, [outer, outer, outer, '#000000', outer])
                    screen.query_one('#scan-details', DataTable).focus()
                    await pilot.press('right_square_bracket')
                    self.assertEqual(screen.scope_path, '/a/b')
                    self.assertNotEqual(screen.scope_color, outer)
                    self.assertEqual(grid.backgrounds[0], '#000000')
                    grid.focus()
                    await pilot.press('left_square_bracket')
                    self.assertEqual(screen.scope_path, '/a')
                    self.assertIs(app.focused, grid)
                    outer = screen.scope_color
                    await pilot.press('f')
                    await pilot.press('right_square_bracket')
                    self.assertEqual(grid.backgrounds, [outer, outer, outer, '#000000', outer])
                grid.follow_end = True
                screen.redraw()
                await pilot.press('left_square_bracket', 'right_square_bracket')
                self.assertEqual(screen.scope_path, '/a/b')
                grid.follow_end = False
                screen.redraw()
                with patch('views.ScannerScreen.time.monotonic', return_value=10):
                    strip = list(grid.render_line(0))
                self.assertEqual([segment.text for segment in strip[:5]], ['D','?','●','M','?'])
                for segment, color in zip(strip, ['#ffffff','#ffffff','green','#ff8800','#ffffff']):
                    self.assertEqual(segment.style.color, Color.parse(color))
                await pilot.press('escape')
                await pilot.pause()
                restored = ScannerScreen(fs, directory, startup=False)
                app.push_screen(restored)
                await pilot.pause(.2)
                grid = restored.query_one(BucketMap)
                self.assertEqual(grid.backgrounds, [outer, outer, outer, '#000000', outer])
                await pilot.press('d')
                self.assertEqual(grid.backgrounds, ['#000000'] * 5)
                self.assertEqual(restored.fixed_colors, {})
                self.assertIsNone(restored.scope_path)
                await pilot.press('escape')
                await pilot.pause()
                restored.worker_thread.join(2)
