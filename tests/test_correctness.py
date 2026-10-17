"""Correctness tests for the three arms.

The exhaustive sweep runs over every multiset of length 0..6 drawn from
{0, 1, 2}. That is 1093 cases with heavy duplication, which is where
selection-sort variants actually break — duplicate handling is what makes the
min/max index-fixup after the first swap non-trivial.

``BIDSEL_FAST=1`` shrinks the sweep to length 0..5 (364 cases) for CI speed.
"""

from __future__ import annotations

import itertools
import os
import random
import unittest

from bidsel import (
    selection_sort,
    selection_sort_bidirectional,
    selection_sort_fast,
)
from bidsel.core import selection_sort_fast_noprecheck

ARMS = (
    ("baseline", selection_sort),
    ("bidirectional", selection_sort_bidirectional),
    ("fast", selection_sort_fast),
    ("fast_noprecheck", selection_sort_fast_noprecheck),
)

FAST = os.environ.get("BIDSEL_FAST") == "1"
MAX_LEN = 5 if FAST else 6


class TestExhaustive(unittest.TestCase):
    def test_all_multisets_small_alphabet(self) -> None:
        cases = 0
        for n in range(MAX_LEN + 1):
            for combo in itertools.product(range(3), repeat=n):
                cases += 1
                want = sorted(combo)
                for name, fn in ARMS:
                    with self.subTest(arm=name, input=combo):
                        self.assertEqual(fn(list(combo)), want)
        self.assertGreater(cases, 300)

    def test_single_extremum_patterns(self) -> None:
        """The case where min and max land on the same index."""
        for n in (2, 3, 4, 5, 17, 64):
            data = [7] * n
            for name, fn in ARMS:
                with self.subTest(arm=name, n=n):
                    self.assertEqual(fn(list(data)), data)

    def test_min_at_right_max_at_left(self) -> None:
        """Exercises the max_idx == left fixup after the min swap."""
        for n in (2, 3, 4, 5, 8, 9):
            data = list(range(n, 0, -1))
            for name, fn in ARMS:
                with self.subTest(arm=name, n=n):
                    self.assertEqual(fn(list(data)), sorted(data))

    def test_sorted_and_reversed(self) -> None:
        for n in (0, 1, 2, 3, 100):
            for name, fn in ARMS:
                with self.subTest(arm=name, n=n, kind="sorted"):
                    self.assertEqual(fn(list(range(n))), list(range(n)))
                with self.subTest(arm=name, n=n, kind="reversed"):
                    self.assertEqual(
                        fn(list(range(n, 0, -1))), list(range(1, n + 1))
                    )


class TestRandomised(unittest.TestCase):
    def test_random_integers(self) -> None:
        rng = random.Random(20261017)
        for _ in range(150):
            n = rng.randint(0, 120)
            data = [rng.randint(-50, 50) for _ in range(n)]
            for name, fn in ARMS:
                with self.subTest(arm=name, n=n):
                    self.assertEqual(fn(list(data)), sorted(data))

    def test_random_floats(self) -> None:
        rng = random.Random(7)
        for _ in range(60):
            n = rng.randint(0, 60)
            data = [round(rng.uniform(-10, 10), 3) for _ in range(n)]
            for name, fn in ARMS:
                with self.subTest(arm=name):
                    self.assertEqual(fn(list(data)), sorted(data))

    def test_strings(self) -> None:
        rng = random.Random(11)
        alphabet = "abcdefgh"
        for _ in range(40):
            n = rng.randint(0, 40)
            data = [rng.choice(alphabet) for _ in range(n)]
            for name, fn in ARMS:
                with self.subTest(arm=name):
                    self.assertEqual(fn(list(data)), sorted(data))


class TestContract(unittest.TestCase):
    """The documented contract is ``__lt__`` and nothing else."""

    def test_lt_only_objects(self) -> None:
        class LtOnly:
            __slots__ = ("v",)

            def __init__(self, v: int) -> None:
                self.v = v

            def __lt__(self, other: "LtOnly", /) -> bool:
                return self.v < other.v

            def __repr__(self) -> str:
                return f"LtOnly({self.v})"

        data = [LtOnly(x) for x in (5, 1, 4, 1, 3)]
        for name, fn in ARMS:
            with self.subTest(arm=name):
                got = [o.v for o in fn(list(data))]
                self.assertEqual(got, [1, 1, 3, 4, 5])

    def test_in_place_and_identity(self) -> None:
        for name, fn in ARMS:
            with self.subTest(arm=name):
                data = [3, 1, 2]
                out = fn(data)
                self.assertIs(out, data)
                self.assertEqual(data, [1, 2, 3])

    def test_tuple_input_rejected(self) -> None:
        """Immutable sequences fail the same way for every arm."""
        for name, fn in ARMS:
            with self.subTest(arm=name):
                with self.assertRaises(TypeError):
                    fn((3, 1, 2))  # type: ignore[arg-type]

    def test_nan_is_not_claimed_to_match_baseline(self) -> None:
        """Documented non-goal: NaN is not a total order.

        ``nan < x`` and ``nan > x`` are both False, so any selection sort that
        looks at both ends will order NaN differently from one that only looks
        at the minimum. This test pins the *documented* behaviour (all arms
        return a permutation of the input) rather than pretending the outputs
        are identical.
        """
        nan = float("nan")
        data = [nan, 1.0, 2.0]
        for name, fn in ARMS:
            with self.subTest(arm=name):
                out = fn(list(data))
                self.assertEqual(len(out), 3)
                self.assertEqual(sum(1 for x in out if x != x), 1)
                self.assertEqual(sorted(x for x in out if x == x), [1.0, 2.0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
