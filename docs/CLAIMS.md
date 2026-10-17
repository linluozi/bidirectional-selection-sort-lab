# Every number in the README, and how it was obtained

This file exists because the write-up this repo replaces reported a
"30-45% fewer comparisons" figure that does not survive measurement. Anything
claimed in `README.md` must be traceable to a line here.

Two kinds of evidence are used, and they are never mixed:

* **Counts** (`benchmarks/ops.py`) — exact, reproducible, no clock involved.
  Used for every claim about *how much work* an arm does.
* **Ratios** (`benchmarks/run_all.py`) — median of per-round `baseline / arm`
  with all arms interleaved in the same round, 7 rounds. Used for every claim
  about *speed*. Absolute milliseconds are printed but never used to compute a
  speed-up.

---

## C1. Double-ended selection does not reduce the comparison count

**Claim.** The bidirectional arm performs essentially the same number of
comparisons as the one-extremum baseline on random data.

**Evidence.** `benchmarks/ops.py`, random n=2000:

| arm | comparisons | element reads | swaps |
|---|---:|---:|---:|
| baseline | 1,999,000 | 4,000,000 | 1,000 |
| bidirectional | 1,999,920 | 4,000,000 | 1,000 |
| fast (precheck off) | 1,999,920 | 1,000,999 | 1,000 |

Ratio of comparisons: **1.00x**. Ratio of reads: **4.00x**.

Why: passes halve (`n-1` → `ceil(n/2)`), but each iteration may now perform two
comparisons (`if` / `elif`). The two effects cancel. Enforced by
`tests/test_counts.py::test_bidirectional_does_not_halve_comparisons`.

**Where the claim holds.** Strictly descending input: the `elif` never fires, so
comparisons equal the iteration count and the ratio is `2(n-1)/n` — 1.98 at
n=100, approaching 2.0. See
`test_bidirectional_halves_comparisons_only_on_reversed`.

## C2. The gain comes from loop-control overhead, not from comparisons

**Claim.** Halving the iteration count at constant comparison count is worth
~25-30%.

**Evidence.** `benchmarks/mechanism.py`, synthetic, 9 interleaved rounds:

| loop | median |
|---|---:|
| 2M iterations × 1 comparison | 42.3 ms |
| 1M iterations × 2 comparisons | 33.0 ms |

**1.28x [1.18..1.38]**. Same total comparisons; only the iteration count
differs. This is the size of the effect seen in the real benchmark, which is
what makes it the explanation rather than a coincidence.

This is a microbenchmark and is labelled as one. It establishes a mechanism,
not a speed-up for any workload.

## C3. Caching the extrema is worth more than the double-ended idea itself

**Claim.** `fast` (cached extrema + precheck) is 1.4-1.7x on random data, while
the un-micro-optimised bidirectional arm is only 1.2-1.3x.

**Evidence.** `benchmarks/run_all.py`, random input, median of 7 rounds:

| n | bidirectional | fast, precheck off | fast |
|---:|---:|---:|---:|
| 500 | 1.35x | 1.73x | 1.74x |
| 1000 | 1.17x | 1.41x | 1.37x |
| 2000 | 1.18x | 1.58x | 1.55x |
| 5000 | 1.19x | 1.50x | 1.59x |

Attribution: the `bidirectional` → `fast_noprecheck` step changes exactly one
thing (caching), and it moves ~1.2x → ~1.5x. The mechanism is visible in the
counts: without caching the bidirectional arm reads **four** elements per
iteration (two per comparison), so halving iterations does nothing for the read
count. With caching it reads one per iteration, so the halving finally shows up.

Enforced by `test_uncached_bidirectional_does_not_reduce_reads` (ratio ≈ 1.0)
and `test_cached_arm_cuts_reads_by_four` (ratio ≈ 4.0).

The n=500 bidirectional figure (1.35x) is the noisiest cell in the table — its
per-round range is [1.09..1.66]. Read the column as "1.2-1.3x, with one
outlier", not as "1.35x".

## C4. The sorted precheck is free when it fails, and worth 60-900x when it succeeds

**Claim.** The `all(not (b < a) ...)` scan costs nothing measurable on unsorted
input, and replaces O(n²) work when the input is already in order.

**Evidence.** `benchmarks/run_all.py`, ratio of `fast` / `fast_noprecheck`:

| input shape | n=500 | n=1000 | n=2000 | n=5000 |
|---|---:|---:|---:|---:|
| random | 1.01 | 0.97 | 0.98 | 1.06 |
| nearly sorted | 1.03 | 0.81 | 0.97 | 1.09 |
| reversed | 1.00 | 1.04 | 0.89 | 0.95 |
| already sorted | 80x | 159x | 301x | 745x |
| all equal | 61x | 142x | 331x | 940x |

**The cost side is within noise.** The three unsorted shapes land between 0.81
and 1.09 with no monotone trend. An earlier draft of this repo claimed the
precheck made reversed input "7-13% slower". That was a misreading of a single
run — with 7 interleaved rounds the effect does not separate from noise, and the
claim was withdrawn. (Two full runs of this benchmark gave cost-side means of
1.01 and 0.98; both are indistinguishable from 1.0.)

**The win side is real and grows with n**, because the precheck is O(n) and the
work it skips is O(n²).

## C5. Nothing here is a claimed drop-in for the upstream function

`selection_sort` reproduces the shape of `TheAlgorithms/Python`'s
`selection_sort` and is byte-comparable in behaviour for ordered data, but this
repo does **not** claim the `fast` arm is a drop-in replacement. Specifically:

* **NaN.** `nan < x` and `nan > x` are both False, so an arm that inspects both
  ends places NaN differently from one that only inspects the minimum. In a
  separate measurement on the upstream pair, the two outputs disagreed on 56%
  of random lists containing NaN. `tests/test_correctness.py` therefore pins
  only the documented behaviour (output is a permutation, non-NaN elements are
  ordered) rather than pretending the outputs match.
* **Contract.** Only `__lt__` is required and only `__lt__` is used. Note that
  `a > b` *does* work without `__gt__` via Python's reflected-operand fallback,
  so "the code uses `>`" is not by itself a contract violation — an earlier
  review flagged it as one and was wrong. This repo avoids `>` anyway so the
  contract does not depend on reflection.
* **Stability.** All arms are unstable. `selection_sort` and the bidirectional
  arms even disagree with each other on equal keys.

## C6. What is *not* measured

* Memory. Every arm is O(1) extra space by construction; no allocation
  benchmark is run, and no memory claim is made.
* Python versions other than 3.12 and 3.13. The `def f[T](...)` syntax is PEP
  695 and needs 3.12+.
* Large n. The grid stops at 5000 because O(n²) at n=10000 is ~100x slower and
  adds nothing to any of the claims above.

---

## Reproducing

```bash
python benchmarks/ops.py          # exact counts -> benchmarks/ops.json
python benchmarks/mechanism.py    # mechanism microbenchmark -> benchmarks/mechanism.json
python benchmarks/run_all.py      # 7 interleaved rounds -> benchmarks/results.json
python assets/make_figures.py     # figures (needs matplotlib)
```

Machine for the numbers above: Windows, CPython 3.13.14, AMD64. Ratios from a
different machine will differ in the second decimal; the ordering of the arms
and the ~1.00x comparison ratio will not.
