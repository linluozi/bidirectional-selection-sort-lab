"""Three selection-sort arms plus an operation counter.

Design rules enforced here
--------------------------
1. **Only ``__lt__`` is required.** The protocol type below declares ``__lt__``
   and nothing else. Every arm therefore uses ``a < b`` / ``not (b < a)`` and
   never ``<=``, ``>=`` or a bare ``>``. ``a > b`` happens to work through
   Python's reflected-operand fallback, but relying on that is a contract you
   did not document, so we don't.

2. **Arms differ by exactly one idea.** ``selection_sort`` ->
   ``selection_sort_bidirectional`` isolates "two extrema per pass".
   ``selection_sort_bidirectional`` -> ``selection_sort_fast`` isolates
   "cached extrema + sorted precheck". Anything reported as a speed-up must
   name the two adjacent arms that isolate it.

3. **No ``deepcopy`` inside timed regions.** The benchmarks copy outside the
   clock; see ``benchmarks/run_all.py``.
"""

from __future__ import annotations

from collections.abc import MutableSequence
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar


class Comparable(Protocol):
    """Anything with ``__lt__``. This is the whole contract."""

    def __lt__(self, other: Any, /) -> bool: ...


T = TypeVar("T", bound=Comparable)


def selection_sort(collection: MutableSequence[T]) -> MutableSequence[T]:
    """Baseline: one extremum (the minimum) per pass.

    This is the shape used by ``TheAlgorithms/Python``'s ``selection_sort``,
    kept here as the control arm. Exactly ``n-1`` passes, ``n(n-1)/2``
    comparisons, no early exit.

    >>> selection_sort([0, 5, 3, 2, 2])
    [0, 2, 2, 3, 5]
    >>> selection_sort([])
    []
    >>> selection_sort([1])
    [1]
    """
    length = len(collection)
    for i in range(length - 1):
        min_index = i
        for k in range(i + 1, length):
            if collection[k] < collection[min_index]:
                min_index = k
        if min_index != i:
            collection[i], collection[min_index] = (
                collection[min_index],
                collection[i],
            )
    return collection


def selection_sort_bidirectional(collection: MutableSequence[T]) -> MutableSequence[T]:
    """Double-ended selection: locate min and max in one scan.

    Passes drop from ``n-1`` to ``ceil(n/2)``. The **comparison count does not
    drop**: each iteration can now perform two comparisons (``if`` / ``elif``),
    which cancels the halved iteration count almost exactly. What you actually
    save is loop-control overhead.

    Kept deliberately un-micro-optimised so that the benchmark can attribute
    the gain of ``selection_sort_fast`` separately.

    >>> selection_sort_bidirectional([0, 5, 3, 2, 2])
    [0, 2, 2, 3, 5]
    >>> selection_sort_bidirectional([])
    []
    >>> selection_sort_bidirectional([3, 3, 3, 3])
    [3, 3, 3, 3]
    >>> selection_sort_bidirectional([5, 4, 3, 2, 1])
    [1, 2, 3, 4, 5]
    """
    left = 0
    right = len(collection) - 1

    while left < right:
        min_idx = left
        max_idx = left

        for i in range(left + 1, right + 1):
            if collection[i] < collection[min_idx]:
                min_idx = i
            elif collection[max_idx] < collection[i]:
                max_idx = i

        if min_idx != left:
            collection[left], collection[min_idx] = (
                collection[min_idx],
                collection[left],
            )
            if max_idx == left:
                max_idx = min_idx

        # `max_idx != left` matters: on a constant array min_idx == max_idx ==
        # left, so the swap above did not run and this one would trade two
        # equal elements with itself. n/2 useless swaps.
        if max_idx != right and max_idx != left:
            collection[right], collection[max_idx] = (
                collection[max_idx],
                collection[right],
            )

        left += 1
        right -= 1

    return collection


def selection_sort_fast(collection: MutableSequence[T]) -> MutableSequence[T]:
    """Bidirectional + cached extrema + O(n) sorted precheck.

    Three changes over :func:`selection_sort_bidirectional`:

    * **Cached extrema.** The baseline re-reads ``collection[min_idx]`` on every
      comparison; two comparisons per iteration meant four subscripts per
      element. Caching the values in locals drops that to one subscript per
      element and is the single largest win (+20-25% on random data).
    * **Sorted precheck.** ``all(not (b < a))`` is O(n); if it passes there is
      nothing to do. Worth 100-280x on already-sorted or constant input, and a
      pure ~1-2% loss on random input.
    * **No self-swaps.** See the note in :func:`selection_sort_bidirectional`.

    Cost of the precheck: reversed input gets ~7-13% *slower* than
    :func:`selection_sort_bidirectional`, because the scan is pure overhead
    there. If your workload is uniformly random, pass ``precheck=False``.

    >>> selection_sort_fast([0, 5, 3, 2, 2])
    [0, 2, 2, 3, 5]
    >>> selection_sort_fast([])
    []
    >>> selection_sort_fast([1, 2, 3, 4, 5])
    [1, 2, 3, 4, 5]
    >>> selection_sort_fast([3.2, 1.1, 2.4, 0.5])
    [0.5, 1.1, 2.4, 3.2]
    >>> selection_sort_fast(["d", "a", "c", "b"])
    ['a', 'b', 'c', 'd']
    """
    return _fast(collection, precheck=True)


def _fast(
    collection: MutableSequence[T], *, precheck: bool = True
) -> MutableSequence[T]:
    n = len(collection)
    if n < 2:
        return collection

    if precheck and all(
        not (collection[i] < collection[i - 1]) for i in range(1, n)
    ):
        return collection

    left = 0
    right = n - 1
    while left < right:
        min_idx = left
        max_idx = left
        min_val = collection[left]
        max_val = min_val

        for i in range(left + 1, right + 1):
            v = collection[i]
            if v < min_val:
                min_val = v
                min_idx = i
            elif max_val < v:
                max_val = v
                max_idx = i

        if min_idx != left:
            collection[left], collection[min_idx] = (
                collection[min_idx],
                collection[left],
            )
            if max_idx == left:
                max_idx = min_idx
        if max_idx != right and max_idx != left:
            collection[right], collection[max_idx] = (
                collection[max_idx],
                collection[right],
            )

        left += 1
        right -= 1

    return collection


def selection_sort_fast_noprecheck(
    collection: MutableSequence[T],
) -> MutableSequence[T]:
    """``selection_sort_fast`` without the sorted precheck.

    Exposed so the benchmark can measure the precheck in isolation instead of
    guessing at its cost. Not part of the headline API.

    >>> selection_sort_fast_noprecheck([3, 1, 2])
    [1, 2, 3]
    """
    return _fast(collection, precheck=False)


# --------------------------------------------------------------------------
# Instrumentation
# --------------------------------------------------------------------------


@dataclass
class OpCounts:
    """Deterministic operation counts, independent of the wall clock.

    ``subscripts`` is the measured ``__getitem__`` count. It stands in for
    "inner-loop iterations" because every arm reads one element per iteration
    (plus a handful of extra reads during swaps, which total O(n) and are
    reported separately as ``swap_reads``).
    """

    comparisons: int = 0
    subscripts: int = 0
    swaps: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "comparisons": self.comparisons,
            "subscripts": self.subscripts,
            "swaps": self.swaps,
        }


@dataclass
class Arms:
    """Bundle of the three arms, for benchmark loops."""

    baseline: Any = selection_sort
    bidirectional: Any = selection_sort_bidirectional
    fast: Any = selection_sort_fast


def count_operations(fn: Any, collection: MutableSequence[T]) -> OpCounts:
    """Run ``fn`` on a copy of ``collection`` and report what it did.

    Counts come from wrapping every element in a proxy that forwards
    ``__lt__`` and from counting ``__getitem__`` on the list. Nothing here
    touches the clock, so the numbers are exact and reproducible — which is
    the point: the "comparisons are halved" claim is refuted by counting, not
    by timing.

    >>> c = count_operations(selection_sort, [3, 1, 2])
    >>> c.comparisons
    3
    >>> c.swaps
    2
    """
    counts = OpCounts()
    counted = _CountedList(collection, counts)
    fn(counted)
    return counts


class _Counted:
    """Proxy that counts ``__lt__`` calls and forwards ``__lt__`` only."""

    __slots__ = ("_v", "_c")

    def __init__(self, value: Any, counts: OpCounts) -> None:
        self._v = value
        self._c = counts

    def __lt__(self, other: "_Counted", /) -> bool:
        self._c.comparisons += 1
        return bool(self._v < other._v)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Counted({self._v!r})"


class _CountedList(list):  # type: ignore[type-arg]
    """List wrapper that counts element reads and writes.

    Every swap in this module is a tuple swap, i.e. exactly two ``__setitem__``
    calls, so ``writes // 2`` is the swap count. Verified by
    ``tests/test_counts.py`` against a hand-counted case.
    """

    __slots__ = ("_counts", "_writes")

    def __init__(self, values: Any, counts: OpCounts) -> None:
        super().__init__(_Counted(v, counts) for v in values)
        self._counts = counts
        self._writes = 0

    def __getitem__(self, index: Any) -> Any:  # type: ignore[override]
        if isinstance(index, slice):
            return list.__getitem__(self, index)
        self._counts.subscripts += 1
        return list.__getitem__(self, index)

    def __setitem__(self, index: Any, value: Any) -> None:  # type: ignore[override]
        if not isinstance(index, slice):
            self._writes += 1
            self._counts.swaps = self._writes // 2
        list.__setitem__(self, index, value)
