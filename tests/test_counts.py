"""Operation-count tests — the ones that refute the common claim.

The popular write-up for double-ended selection sort says the comparison count
is "roughly halved". These tests assert the opposite, using exact counts rather
than a stopwatch, so they are reproducible on any machine.

If you change an arm such that these fail, either you genuinely improved the
comparison count (then update docs/CLAIMS.md and the README) or you broke the
attribution the benchmark relies on.
"""

from __future__ import annotations

import unittest

from bidsel import selection_sort, selection_sort_bidirectional, selection_sort_fast
from bidsel.core import count_operations


def random_data(n: int, seed: int = 20261017) -> list[int]:
    import random

    rng = random.Random(seed)
    return [rng.randint(-10**6, 10**6) for _ in range(n)]


class TestComparisonCounts(unittest.TestCase):
    def test_baseline_comparison_formula(self) -> None:
        """n(n-1)/2, exactly, for any input order."""
        for n in (0, 1, 2, 3, 10, 50):
            for kind, data in (
                ("random", random_data(n)),
                ("sorted", list(range(n))),
                ("reversed", list(range(n, 0, -1))),
                ("equal", [5] * n),
            ):
                with self.subTest(n=n, kind=kind):
                    self.assertEqual(
                        count_operations(selection_sort, data).comparisons,
                        n * (n - 1) // 2,
                    )

    def test_bidirectional_does_not_halve_comparisons(self) -> None:
        """The headline refutation.

        On random data the bidirectional arm performs essentially the same
        number of comparisons as the baseline — measured 1.00-1.02x. The
        tolerance is asymmetric on purpose: the ``elif`` only fires when a new
        maximum appears, so the bidirectional arm usually comes in a hair
        *under* the baseline rather than exactly on it.
        """
        for n in (100, 500, 1000):
            data = random_data(n)
            base = count_operations(selection_sort, data).comparisons
            bidi = count_operations(selection_sort_bidirectional, data).comparisons
            ratio = base / bidi
            with self.subTest(n=n, ratio=round(ratio, 4)):
                self.assertGreater(ratio, 0.95)
                self.assertLess(ratio, 1.05)

    def test_bidirectional_halves_comparisons_only_on_reversed(self) -> None:
        """On strictly descending input the ``elif`` never fires.

        Comparisons then equal the iteration count, which is n^2/4 (rounded),
        so the ratio is ``2(n-1)/n`` — 1.98 at n=100, approaching 2.0 as n
        grows. Asserting a flat 2.0 would be wrong.
        """
        for n in (100, 500, 1000):
            data = list(range(n, 0, -1))
            base = count_operations(selection_sort, data).comparisons
            bidi = count_operations(selection_sort_bidirectional, data).comparisons
            expected = 2 * (n - 1) / n
            with self.subTest(n=n):
                self.assertAlmostEqual(base / bidi, expected, places=3)

    def test_uncached_bidirectional_does_not_reduce_reads(self) -> None:
        """Why the shipped variant left half its gain on the table.

        Without caching, the bidirectional arm reads four elements per
        iteration (two per comparison). Halving the iterations therefore does
        *nothing* for the read count — measured ratio 1.008.
        """
        n = 500
        data = random_data(n)
        base = count_operations(selection_sort, data).subscripts
        bidi = count_operations(selection_sort_bidirectional, data).subscripts
        ratio = base / bidi
        with self.subTest(ratio=round(ratio, 3)):
            self.assertGreater(ratio, 0.95)
            self.assertLess(ratio, 1.15)

    def test_cached_arm_cuts_reads_by_four(self) -> None:
        """Caching extrema is what actually turns the iteration saving into reads.

        Baseline: 2 reads per comparison. Fast arm: 1 read per iteration, and
        half the iterations => roughly 4x fewer reads.
        """
        n = 500
        data = random_data(n)
        base = count_operations(selection_sort, data).subscripts
        fast = count_operations(selection_sort_fast, data).subscripts
        ratio = base / fast
        with self.subTest(ratio=round(ratio, 3)):
            self.assertGreater(ratio, 3.5)
            self.assertLess(ratio, 4.5)


class TestSwapCounts(unittest.TestCase):
    def test_constant_array_causes_no_swaps(self) -> None:
        """Regression: the shipped variant performed n/2 useless self-swaps."""
        for n in (10, 100, 1000):
            data = [7] * n
            for name, fn in (
                ("bidirectional", selection_sort_bidirectional),
                ("fast", selection_sort_fast),
            ):
                with self.subTest(n=n, arm=name):
                    self.assertEqual(count_operations(fn, data).swaps, 0)

    def test_sorted_array_causes_no_swaps(self) -> None:
        for n in (10, 100, 1000):
            data = list(range(n))
            for name, fn in (
                ("baseline", selection_sort),
                ("bidirectional", selection_sort_bidirectional),
                ("fast", selection_sort_fast),
            ):
                with self.subTest(n=n, arm=name):
                    self.assertEqual(count_operations(fn, data).swaps, 0)

    def test_swap_count_upper_bound(self) -> None:
        """Selection sort never performs more than n-1 swaps."""
        for n in (2, 5, 50, 200):
            data = random_data(n)
            for name, fn in (
                ("baseline", selection_sort),
                ("bidirectional", selection_sort_bidirectional),
                ("fast", selection_sort_fast),
            ):
                with self.subTest(n=n, arm=name):
                    self.assertLessEqual(count_operations(fn, data).swaps, n)


class TestCounterItself(unittest.TestCase):
    """Reverse-check the instrument: a hand-countable case must match."""

    def test_hand_counted_three_elements(self) -> None:
        # selection_sort on [3, 1, 2]:
        #   i=0: k=1 (1<3 -> min=1), k=2 (2<1 false)  => 2 comparisons, 1 swap
        #   i=1: k=2 (2<3 true -> min=2)              => 1 comparison, 1 swap
        c = count_operations(selection_sort, [3, 1, 2])
        self.assertEqual(c.comparisons, 3)
        self.assertEqual(c.swaps, 2)

    def test_counter_is_not_vacuous(self) -> None:
        """A do-nothing function must report zeros.

        Guards against the classic fake-assertion trap where the instrument
        counts something that is always non-zero.
        """

        def noop(_collection: object) -> None:
            return None

        c = count_operations(noop, [3, 1, 2])
        self.assertEqual(c.comparisons, 0)
        self.assertEqual(c.subscripts, 0)
        self.assertEqual(c.swaps, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
