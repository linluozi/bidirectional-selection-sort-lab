#!/usr/bin/env python
"""Deterministic operation counts for the three arms.

Nothing here touches the clock. That is deliberate: the claim under test
("double-ended selection halves the comparison count") is a *counting* claim,
so it should be settled by counting. A stopwatch can only ever show a
wall-clock difference and then invite a wrong causal story.

Output: ``benchmarks/ops.json``.
"""

from __future__ import annotations

import json
import platform
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bidsel import (  # noqa: E402
    count_operations,
    selection_sort,
    selection_sort_bidirectional,
    selection_sort_fast,
)
from bidsel.core import selection_sort_fast_noprecheck  # noqa: E402

ARMS = (
    ("baseline", selection_sort),
    ("bidirectional", selection_sort_bidirectional),
    ("fast_noprecheck", selection_sort_fast_noprecheck),
    ("fast", selection_sort_fast),
)

KINDS = ("random", "nearly", "sorted", "equal", "reversed")
SIZES = (100, 500, 1000, 2000)


def make_data(size: int, kind: str, seed: int = 20261017) -> list[int]:
    import random

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
    raise ValueError(kind)


def main(argv: list[str] | None = None) -> int:
    import argparse

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "recompute and compare against the committed ops.json instead of "
            "writing. Counts are deterministic across machines, so any "
            "difference is a real regression, not a timing artefact."
        ),
    )
    args = parser.parse_args(argv)

    cells: list[dict[str, Any]] = []
    print(f"{'kind':>9} {'n':>6} | {'arm':>16} | {'cmp':>10} {'read':>10} {'swap':>7}")
    print("-" * 68)

    for kind in KINDS:
        for size in SIZES:
            data = make_data(size, kind)
            row: dict[str, Any] = {"kind": kind, "size": size, "arms": {}}
            for name, fn in ARMS:
                counts = count_operations(fn, data)
                row["arms"][name] = counts.as_dict()
                print(f"{kind:>9} {size:>6} | {name:>16} | "
                      f"{counts.comparisons:>10,} {counts.subscripts:>10,} "
                      f"{counts.swaps:>7,}")
            cells.append(row)
            print()

    payload = {
        "meta": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "note": (
                "Exact counts, no timing. 'read' is the number of "
                "__getitem__ calls on the list (one per element inspected plus "
                "O(n) from swaps)."
            ),
        },
        "cells": cells,
    }
    target = ROOT / "benchmarks" / "ops.json"

    if args.check:
        if not target.exists():
            print(f"::error:: {target.name} is missing")
            return 1
        committed = json.loads(target.read_text(encoding="utf-8"))
        diffs = []
        for got, want in zip(cells, committed.get("cells", [])):
            for arm, counts in got["arms"].items():
                ref = want.get("arms", {}).get(arm)
                if ref != counts:
                    diffs.append(
                        f"{got['kind']} n={got['size']} {arm}: "
                        f"committed {ref} != recomputed {counts}"
                    )
        if diffs:
            for line in diffs[:10]:
                print(f"::error:: {line}")
            print(f"{len(diffs)} mismatched cells")
            return 1
        print(f"OK: {len(cells)} cells match {target.name} exactly")
        return 0

    # newline="\n" keeps the file LF on Windows, so CI's "did the smoke run
    # touch results.json" check compares like with like.
    target.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
