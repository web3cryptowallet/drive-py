"""Expert candidate rebuilds must not stop queued scanning or publish stale work."""
# IMPORT TEST SCANNER REBUILD DEPENDENCIES [
from contextlib import contextmanager
from threading import Event, Thread
import unittest
from unittest.mock import patch

from vfs.scanner import ScanControls
# IMPORT TEST SCANNER REBUILD DEPENDENCIES ]
# VERIFY CANDIDATE REBUILD BEHAVIOR [
class CandidateRebuildTests(unittest.TestCase):
    # CONTROLS FOR CANDIDATE REBUILD TESTS [
    def controls(self, count=6):
        controls = ScanControls((False, False, True), heavy_order='expert')
        controls.buckets = tuple((str(index),) for index in range(count))
        controls.entry_priorities = dict.fromkeys((str(index) for index in range(count)), 0)
        return controls
    # CONTROLS FOR CANDIDATE REBUILD TESTS ]
    # START CALL FOR CANDIDATE REBUILD TESTS [
    @staticmethod
    def start_call(function):
        done, results, errors = Event(), [], []

        # RUN CANDIDATE REBUILD TESTS [
        def run():
            try:
                results.append(function())
            except BaseException as error:
                errors.append(error)
            finally:
                done.set()
        # RUN CANDIDATE REBUILD TESTS ]

        thread = Thread(target=run, daemon=True)
        thread.start()
        return thread, done, results, errors
    # START CALL FOR CANDIDATE REBUILD TESTS ]
    # FINISH CALL FOR CANDIDATE REBUILD TESTS [
    def finish_call(self, call):
        thread, done, results, errors = call
        self.assertTrue(done.wait(1), 'Operation blocked while candidate rebuilding was paused')
        thread.join(1)
        self.assertFalse(thread.is_alive())
        if errors:
            raise errors[0]
        return results[0]
    # FINISH CALL FOR CANDIDATE REBUILD TESTS ]
    # BLOCKED REBUILD FOR CANDIDATE REBUILD TESTS [
    @contextmanager
    def blocked_rebuild(self, controls):
        entered, release = Event(), Event()
        original = controls.expert_eligible_indices

        # HOLD SCANNER WORK UNTIL THE TEST RELEASES IT [
        def blocked(buckets, priorities=None):
            entered.set()
            if not release.wait(2):
                raise AssertionError('Candidate rebuild was not released')
            return original(buckets, priorities)
        # HOLD SCANNER WORK UNTIL THE TEST RELEASES IT ]

        with patch.object(controls, 'expert_eligible_indices', side_effect=blocked) as search, patch(
                'vfs.scanner.random.randint', return_value=20):
            call = self.start_call(controls.enqueue_expert_batch)
            try:
                self.assertTrue(entered.wait(1))
                yield search, call
            finally:
                release.set()
                call[0].join(2)
                self.assertFalse(call[0].is_alive())
    # BLOCKED REBUILD FOR CANDIDATE REBUILD TESTS ]
    # VERIFY EXISTING QUEUE CAN BE SCANNED DURING CANDIDATE REBUILD [
    def test_existing_queue_can_be_scanned_during_candidate_rebuild(self):
        controls = self.controls()
        controls.expert_queue.extend(controls.buckets[:2])

        # SCAN EXISTING FOR TEST EXISTING QUEUE CAN BE SCANNED DURING CANDIDATE REBUILD [
        def scan_existing():
            scanned = []
            for _ in range(2):
                scanned.append(controls.claim_expert())
                controls.finish_expert()
            return scanned
        # SCAN EXISTING FOR TEST EXISTING QUEUE CAN BE SCANNED DURING CANDIDATE REBUILD ]

        with self.blocked_rebuild(controls) as (_, rebuild):
            scanned = self.finish_call(self.start_call(scan_existing))
            self.assertEqual(scanned, [('0',), ('1',)])
        self.assertEqual(self.finish_call(rebuild), 4)
        self.assertEqual(set(controls.selected_buckets), set(controls.buckets[2:]))
    # VERIFY EXISTING QUEUE CAN BE SCANNED DURING CANDIDATE REBUILD ]
    # VERIFY SECOND PRODUCER DOES NOT COMPETE WITH ACTIVE BUILDER [
    def test_second_producer_does_not_compete_with_active_builder(self):
        controls = self.controls()
        with self.blocked_rebuild(controls) as (search, rebuild):
            second = self.finish_call(self.start_call(controls.enqueue_expert_batch))
            self.assertEqual(second, 0)
            self.assertEqual(search.call_count, 1)
        self.assertEqual(self.finish_call(rebuild), 6)
        self.assertEqual(len(controls.selected_buckets), 6)
        self.assertEqual(set(controls.selected_buckets), set(controls.buckets))
    # VERIFY SECOND PRODUCER DOES NOT COMPETE WITH ACTIVE BUILDER ]
    # VERIFY MANUAL START INVALIDATES IN PROGRESS REBUILD [
    def test_manual_start_invalidates_in_progress_rebuild(self):
        controls = self.controls()
        controls.expert_queue.append(controls.buckets[0])
        with self.blocked_rebuild(controls) as (_, rebuild):
            self.finish_call(self.start_call(lambda: controls.start_from(3, '3')))
            self.assertEqual(controls.selected_buckets, (('3',),))
        self.assertEqual(self.finish_call(rebuild), 0)
        self.assertEqual(controls.selected_buckets, (('3',),))
        with patch('vfs.scanner.random.randint', return_value=20):
            self.assertEqual(controls.enqueue_expert_batch(), 5)
        self.assertEqual(len(controls.selected_buckets), 6)
        self.assertEqual(set(controls.selected_buckets), set(controls.buckets))
    # VERIFY MANUAL START INVALIDATES IN PROGRESS REBUILD ]
    # VERIFY CATALOG REPLACEMENT DISCARDS IN PROGRESS REBUILD [
    def test_catalog_replacement_discards_in_progress_rebuild(self):
        controls = self.controls()
        replacement = (('replacement-a',), ('replacement-b',))

        # REPLACE CATALOG FOR TEST CATALOG REPLACEMENT DISCARDS IN PROGRESS REBUILD [
        def replace_catalog():
            with controls.lock:
                controls.buckets = replacement
                controls.entry_priorities = {'replacement-a': 0, 'replacement-b': 0}
        # REPLACE CATALOG FOR TEST CATALOG REPLACEMENT DISCARDS IN PROGRESS REBUILD ]

        with self.blocked_rebuild(controls) as (_, rebuild):
            self.finish_call(self.start_call(replace_catalog))
        self.assertEqual(self.finish_call(rebuild), 0)
        self.assertEqual(controls.selected_buckets, ())
        with patch('vfs.scanner.random.randint', return_value=20):
            self.assertEqual(controls.enqueue_expert_batch(), 2)
        self.assertEqual(set(controls.selected_buckets), set(replacement))
    # VERIFY CATALOG REPLACEMENT DISCARDS IN PROGRESS REBUILD ]
    # VERIFY FAILED REBUILD ALLOWS NEXT PRODUCER TO RETRY [
    def test_failed_rebuild_allows_next_producer_to_retry(self):
        controls = self.controls()
        with patch.object(controls, 'expert_eligible_indices', side_effect=RuntimeError('build failed')):
            with self.assertRaisesRegex(RuntimeError, 'build failed'):
                controls.enqueue_expert_batch()
        with patch('vfs.scanner.random.randint', return_value=20):
            self.assertEqual(controls.enqueue_expert_batch(), 6)
        self.assertEqual(set(controls.selected_buckets), set(controls.buckets))
    # VERIFY FAILED REBUILD ALLOWS NEXT PRODUCER TO RETRY ]
    # VERIFY PRIORITY CHANGES DO NOT RESTART SNAPSHOT REBUILD [
    def test_priority_changes_do_not_restart_snapshot_rebuild(self):
        controls = self.controls(2)
        controls.entry_priorities = {'0': 0, '1': 2}

        # VERIFY FIRST FOR TEST PRIORITY CHANGES DO NOT RESTART SNAPSHOT REBUILD [
        def verify_first():
            with controls.lock:
                controls.entry_priorities['0'] = 3
                controls.priority_revision += 1
        # VERIFY FIRST FOR TEST PRIORITY CHANGES DO NOT RESTART SNAPSHOT REBUILD ]

        with self.blocked_rebuild(controls) as (search, rebuild):
            self.finish_call(self.start_call(verify_first))
            self.assertEqual(search.call_count, 1)
        self.assertEqual(self.finish_call(rebuild), 1)
        self.assertEqual(controls.claim_expert(), ('0',))
        controls.finish_expert()
        self.assertEqual(controls.enqueue_expert_batch(), 1)
        self.assertEqual(controls.selected_buckets, (('1',),))
    # VERIFY PRIORITY CHANGES DO NOT RESTART SNAPSHOT REBUILD ]
# VERIFY CANDIDATE REBUILD BEHAVIOR ]
# RUN TEST SCANNER REBUILD ENTRY POINT [
if __name__ == '__main__':
    unittest.main()
# RUN TEST SCANNER REBUILD ENTRY POINT ]
