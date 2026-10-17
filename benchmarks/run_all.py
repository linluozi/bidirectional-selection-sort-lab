#!/usr/bin/env python
"""Wall-clock benchmark for the three arms.

Measurement rules (each one earned the hard way):

1. **Same-round interleaving.** All arms run once per round, in the same
   round, then the *ratio* per round is taken. Slow drift hits every arm
   equally; absolute milliseconds do not survive a process boundary. In an
   earlier measurement of this exact code, "run baseline fully, then the
   optimised arm" reported 1.45x where interleaving reported 1.22x — an 18.6%
   inflation from ordering alone.

2. **Copy outside the clock.** ``deepcopy`` inside the timed region inflated
   n=100 by 21% in the package this repo replaces. We copy with ``list()``
   before ``perf_counter``.

3. **Median of per-round ratios, plus a range.** A single run of the original
   script moved between 0.93x and 1.45x on n=100 across three invocations.
   Any one number is noise.

4. **Best-of-N absolutes are reported for magnitude only.** They are never
   used to compute a speed-up.

Usage
-----
    python benchmarks/run_all.py            # full run, writes results.json
    python benchmarks/run_all.py --quick    # smaller grid
    python benchmarks/run_all.py --ci       # smoke only, writes results-ci.json
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bidsel import (  # noqa: E402
    selection_sort,
    selection_sort_bidirectional,
    selection_sort_fast,
)
from bidsel.core import selection_sort_fast_noprecheck  # noqa: E402

ARMS: tuple[tuple[str, Callable[..., Any]], ...] = (
    ("baseline", selection_sort),
    ("bidirectional", selection_sort_bidirectional),
    ("fast_noprecheck", selection_sort_fast_noprecheck),
    ("fast", selection_sort_fast),
)

KINDS = ("random", "nearly", "sorted", "equal", "reversed")


def make_data(size: int, kind: str, seed: int = 20261017) -> list[int]:
    rng = random.Random(seed)
    if kind == "random":
        return [rng.randint(-10**6, 10**6) for _ in range(size)]
    if kind == "nearly":
        data = list(range(size))
        for _ in range(max(1, size // 50)):
            i, j = rng.randrange(size), rng.randrange(size)
            data[i], data[j] = data[j], data[i]
        return data
    if kind == "sorted":
        return list(range(size))
    if kind == "equal":
        return [42] * size
    if kind == "reversed":
        return list(range(size, 0, -1))
    raise ValueError(f"unknown kind: {kind}")


def timed(fn: Callable[..., Any], data: list[int]) -> float:
    """Run one arm on a fresh copy; the copy is *outside* the clock."""
    payload = list(data)
    start = time.perf_counter()
    fn(payload)
    return time.perf_counter() - start


def bench_cell(
    size: int, kind: str, rounds: int
) -> dict[str, Any]:
    data = make_data(size, kind)

    # Warm up every arm once so first-call effects do not land on round 1.
    for _, fn in ARMS:
        timed(fn, data)

    per_round: list[dict[str, float]] = []
    for _ in range(rounds):
        row: dict[str, float] = {}
        for name, fn in ARMS:  # interleaved inside the round
            row[name] = timed(fn, data)
        per_round.append(row)

    out: dict[str, Any] = {
        "size": size,
        "kind": kind,
        "rounds": rounds,
        "median_ms": {
            name: statistics.median(r[name] for r in per_round) * 1000
            for name, _ in ARMS
        },
        "best_ms": {
            name: min(r[name] for r in per_round) * 1000 for name, _ in ARMS
        },
    }

    # Per-round speed-up ratios against the baseline.
    ratios: dict[str, list[float]] = {name: [] for name, _ in ARMS[1:]}
    for row in per_round:
        base = row["baseline"]
        for name, _ in ARMS[1:]:
            ratios[name].append(base / row[name])
    out["ratio"] = {
        name: {
            "median": statistics.median(vals),
            "min": min(vals),
            "max": max(vals),
        }
        for name, vals in ratios.items()
    }
    return out


def grid(profile: str) -> tuple[list[int], list[str], int]:
    if profile == "ci":
        return [400], ["random", "sorted"], 3
    if profile == "quick":
        return [500, 2000], list(KINDS), 5
    return [500, 1000, 2000, 5000], list(KINDS), 7


def main(argv: Iterable[str] | None = None) -> int:
    # Windows defaults to cp1252 and this script prints arrows and the like.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--quick", action="store_true", help="smaller grid")
    group.add_argument("--ci", action="store_true", help="smoke run only")
    args = parser.parse_args(list(argv) if argv is not None else None)

    profile = "ci" if args.ci else "quick" if args.quick else "full"
    sizes, kinds, rounds = grid(profile)
    out_name = "results-ci.json" if profile == "ci" else "results.json"

    print(f"profile={profile}  python={platform.python_version()}  "
          f"machine={platform.machine()}  rounds={rounds}")

    header = f"{'kind':>9} {'n':>6} | " + " | ".join(
        f"{name:>16}" for name, _ in ARMS[1:]
    )
    print(header)
    print("-" * len(header))

    cells: list[dict[str, Any]] = []
    for kind in kinds:
        for size in sizes:
            cell = bench_cell(size, kind, rounds)
            cells.append(cell)
            parts = []
            for name, _ in ARMS[1:]:
                r = cell["ratio"][name]
                parts.append(
                    f"{r['median']:>6.2f}x [{r['min']:.2f}..{r['max']:.2f}]"
                )
            print(f"{kind:>9} {size:>6} | " + " | ".join(f"{p:>16}" for p in parts),
                  flush=True)

    payload = {
        "meta": {
            "profile": profile,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "rounds": rounds,
            "sizes": sizes,
            "kinds": kinds,
            "arms": [name for name, _ in ARMS],
            "note": (
                "Ratios are medians of per-round baseline/arm ratios with "
                "same-round interleaving. Absolute ms are best-of-N and are "
                "for magnitude only."
            ),
        },
        "cells": cells,
    }

    target = ROOT / "benchmarks" / out_name
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
