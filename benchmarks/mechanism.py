#!/usr/bin/env python
"""Mechanism attribution: why does halving the iteration count help at all?

The bidirectional arm performs the *same* number of comparisons as the baseline
(see ``benchmarks/ops.py``), yet it is faster. The usual explanation — "fewer
comparisons" — is therefore unavailable. This script isolates the real cause by
holding the comparison count fixed and varying only the number of loop
iterations.

Two loops, identical work:

* ``A`` — 2M iterations, one comparison each
* ``B`` — 1M iterations, two comparisons each

Same total comparisons. If loop control were free, they would take the same
time. They do not: B is ~25-30% faster, which is the size of the effect seen in
the real benchmark. That is the whole explanation.

This is a synthetic microbenchmark and is labelled as such: it establishes a
*causal mechanism*, not a speed-up for any particular workload.

Output: ``benchmarks/mechanism.json``.
"""

from __future__ import annotations

import json
import platform
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
ROUNDS = 9
N_ITERS = 2_000_000


def loop_one_comparison(seq: list[int], n: int) -> int:
    """n iterations, one comparison each."""
    hits = 0
    for i in range(n):
        if seq[i] < 0:
            hits += 1
    return hits


def loop_two_comparisons(seq: list[int], n: int) -> int:
    """n iterations, up to two comparisons each (mirrors if/elif)."""
    hits = 0
    for i in range(n):
        if seq[i] < 0:
            hits += 1
        elif seq[i] > 10**9:
            hits += 1
    return hits


CASES: tuple[tuple[str, Callable[[list[int], int], int], int], ...] = (
    ("2M iterations x 1 comparison", loop_one_comparison, N_ITERS),
    ("1M iterations x 2 comparisons", loop_two_comparisons, N_ITERS // 2),
)


def main(argv: list[str] | None = None) -> int:
    import argparse

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-write",
        action="store_true",
        help=(
            "run and print, but do not overwrite mechanism.json. CI uses this: "
            "the committed timings are machine-specific, so a runner with a "
            "different CPU would otherwise dirty the tree on every build."
        ),
    )
    args = parser.parse_args(argv)

    data = list(range(N_ITERS))
    results: dict[str, Any] = {}

    # Warm up both so the first case does not pay one-time costs alone.
    for _, fn, n in CASES:
        fn(data, n)

    samples: dict[str, list[float]] = {name: [] for name, _, _ in CASES}
    for _ in range(ROUNDS):
        for name, fn, n in CASES:  # interleaved inside the round
            start = time.perf_counter()
            fn(data, n)
            samples[name].append(time.perf_counter() - start)

    print(f"{'case':>32} | {'median ms':>10} | {'best ms':>9}")
    print("-" * 58)
    for name, _, _ in CASES:
        med = statistics.median(samples[name]) * 1000
        best = min(samples[name]) * 1000
        results[name] = {"median_ms": med, "best_ms": best}
        print(f"{name:>32} | {med:>10.1f} | {best:>9.1f}")

    ratios = [
        samples[CASES[0][0]][i] / samples[CASES[1][0]][i] for i in range(ROUNDS)
    ]
    ratio = statistics.median(ratios)
    results["ratio_one_cmp_over_two_cmp"] = {
        "median": ratio,
        "min": min(ratios),
        "max": max(ratios),
    }
    print("-" * 58)
    print(f"{'same comparisons, half the iterations':>32} | "
          f"{ratio:>9.2f}x [{min(ratios):.2f}..{max(ratios):.2f}]")

    payload = {
        "meta": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "rounds": ROUNDS,
            "iterations": N_ITERS,
            "note": (
                "Synthetic microbenchmark. Both loops perform N comparisons "
                "in total; only the iteration count differs. The ratio is the "
                "median of per-round ratios."
            ),
        },
        "cases": results,
    }
    target = ROOT / "benchmarks" / "mechanism.json"

    if args.no_write:
        print("\n--no-write: mechanism.json left untouched")
        return 0

    # newline="\n" keeps the file LF on Windows, so CI's "did the smoke run
    # touch results.json" check compares like with like.
    target.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"\nwrote {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
