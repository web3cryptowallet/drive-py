# IMPORT TEST SCANNER POOL DEPENDENCIES [
import random
import unittest

from vfs.scanner_pool import CandidatePool
# IMPORT TEST SCANNER POOL DEPENDENCIES ]
# VERIFY CANDIDATE POOL BEHAVIOR [
class CandidatePoolTests(unittest.TestCase):
    # VERIFY RANGES KEEP MAP ORDER ACROSS HOLES AND WRAP [
    def test_ranges_keep_map_order_across_holes_and_wrap(self):
        pool = CandidatePool([0, 2, 4, 6, 8, 10])
        self.assertEqual(pool.consume(4, 2), [4, 6])
        self.assertEqual(pool.consume(10, 3), [10, 0, 2])
        self.assertEqual(list(pool), [8])
        self.assertEqual(pool.consume(8, 20), [8])
        self.assertFalse(pool)
        self.assertEqual(pool.consume(8, 1), [])
    # VERIFY RANGES KEEP MAP ORDER ACROSS HOLES AND WRAP ]
    # VERIFY DENSE CHOICES HAVE EXACTLY ONE SLOT PER REMAINING CANDIDATE [
    def test_dense_choices_have_exactly_one_slot_per_remaining_candidate(self):
        pool = CandidatePool(range(50))
        remaining = set(range(50))
        rng = random.Random(67)
        while pool:
            # Every available bucket occupies exactly one possible choice slot.
            self.assertEqual(len(pool), len(remaining))
            self.assertEqual(set(pool), remaining)
            self.assertEqual(len(set(pool)), len(pool))
            self.assertEqual(pool[-1], list(pool)[-1])
            self.assertEqual(pool[:3], list(pool)[:3])
            first = rng.choice(pool)
            chosen = pool.consume(first, rng.randint(1, 20))
            for index in chosen:
                remaining.remove(index)
                self.assertNotIn(index, pool)
            for index in remaining:
                self.assertIn(index, pool)
        self.assertFalse(remaining)
    # VERIFY DENSE CHOICES HAVE EXACTLY ONE SLOT PER REMAINING CANDIDATE ]
    # VERIFY RANDOM CONSUMPTION MATCHES SORTED LIST REFERENCE [
    def test_random_consumption_matches_sorted_list_reference(self):
        for seed in range(12):
            rng = random.Random(seed)
            reference = sorted(rng.sample(range(5000), 1000))
            pool = CandidatePool(reference)
            while reference:
                first = rng.choice(pool)
                count = min(rng.randint(1, 20), len(reference))
                start = reference.index(first)
                expected = (reference[start:] + reference[:start])[:count]
                self.assertEqual(pool.consume(first, count), expected)
                removed = set(expected)
                reference = [index for index in reference if index not in removed]
                self.assertEqual(sorted(pool), reference)
            self.assertFalse(pool)
    # VERIFY RANDOM CONSUMPTION MATCHES SORTED LIST REFERENCE ]
    # VERIFY EMPTY ZERO LENGTH AND REMOVED START [
    def test_empty_zero_length_and_removed_start(self):
        pool = CandidatePool()
        self.assertFalse(pool)
        self.assertNotIn(0, pool)
        self.assertEqual(pool.consume(0, 4), [])
        with self.assertRaises(IndexError):
            random.choice(pool)
        pool = CandidatePool([2, 5])
        self.assertEqual(pool.consume(2, 0), [])
        self.assertEqual(pool.consume(2, 1), [2])
        with self.assertRaises(KeyError):
            pool.consume(2, 1)
        with self.assertRaises(KeyError):
            pool.consume(3, 1)
        self.assertEqual(pool.consume(5, 1), [5])
    # VERIFY EMPTY ZERO LENGTH AND REMOVED START ]
# VERIFY CANDIDATE POOL BEHAVIOR ]
# RUN TEST SCANNER POOL ENTRY POINT [
if __name__ == '__main__':
    unittest.main()
# RUN TEST SCANNER POOL ENTRY POINT ]
