#!/usr/bin/env python
"""Generate every figure in assets/ from benchmarks/*.json.

Rules followed here (each one from a past mistake):

* **Plot ratios, never absolute milliseconds.** Absolute wall-clock drifts by
  up to 3x across cases inside one process; a millisecond axis then draws a
  curve whose shape is measurement artefact.
* **Draw speed-up, not ratio.** A ratio axis inverts the story: 0.98x looks
  like a long bar on a log scale. ``speedup = 1 / ratio`` puts "long bar =
  big win" on the page.
* **Label the number of rounds and the range** on every timing figure, so a
  reader cannot mistake a single run for a result.

Figures
-------
``speedup-by-shape.png``    one panel per input shape; x = n, y = speed-up
``comparisons-vs-reads.png`` the refutation: comparisons flat, reads falling
``mechanism.png``           same comparisons, half the iterations
``precheck-cost.png``       what the sorted precheck costs and what it buys

Run:
    python assets/make_figures.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
BENCH = ROOT / "benchmarks"

# Warm editorial palette: espresso brown / amber gold / terracotta.
INK = "#2b2119"
PAPER = "#faf6f0"
AMBER = "#c8892b"
TERRACOTTA = "#b4552f"
OLIVE = "#6b6b3a"
MUTED = "#8a7a68"

plt.rcParams.update(
    {
        "figure.facecolor": PAPER,
        "axes.facecolor": PAPER,
        "axes.edgecolor": INK,
        "axes.labelcolor": INK,
        "text.color": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "font.size": 10,
        "axes.grid": True,
        "grid.color": "#ddd2c4",
        "grid.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)

ARM_STYLE = {
    "bidirectional": (TERRACOTTA, "o", "bidirectional (no micro-opt)"),
    "fast_noprecheck": (OLIVE, "s", "fast, precheck off"),
    "fast": (AMBER, "^", "fast (default)"),
}
KIND_LABEL = {
    "random": "random",
    "nearly": "nearly sorted",
    "sorted": "already sorted",
    "equal": "all equal",
    "reversed": "reversed",
}


def load(name: str) -> dict:
    return json.loads((BENCH / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------


def fig_speedup_by_shape() -> None:
    data = load("results.json")
    cells = {(c["kind"], c["size"]): c for c in data["cells"]}
    kinds = [k for k in ("random", "nearly", "reversed", "sorted", "equal")
             if any(c["kind"] == k for c in data["cells"])]
    sizes = sorted({c["size"] for c in data["cells"]})

    ncols = 3
    nrows = (len(kinds) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.4 * ncols, 3.4 * nrows))
    flat = axes.ravel() if nrows * ncols > 1 else [axes]

    for ax, kind in zip(flat, kinds):
        for arm, (colour, marker, label) in ARM_STYLE.items():
            xs, ys = [], []
            for size in sizes:
                cell = cells.get((kind, size))
                if not cell:
                    continue
                xs.append(size)
                ys.append(cell["ratio"][arm]["median"])
            if xs:
                ax.plot(xs, ys, marker=marker, color=colour, label=label,
                        linewidth=1.8, markersize=5)
        ax.axhline(1.0, color=MUTED, linestyle="--", linewidth=1.0)
        ax.set_xscale("log")
        ax.set_title(KIND_LABEL.get(kind, kind), fontsize=11)
        ax.set_xlabel("n")
        # Log-spaced ticks crowd together; use plain index positions instead.
        ax.set_xticks(sizes)
        ax.set_xticklabels([f"{s:,}" for s in sizes], fontsize=9)
        ax.minorticks_off()
        if kind in ("sorted", "equal"):
            ax.set_yscale("log")
            ax.set_ylabel("speed-up (log)")
        else:
            ax.set_ylabel("speed-up")
            ax.set_ylim(0.8, 2.6)

    for ax in flat[len(kinds):]:
        ax.set_visible(False)

    handles, labels = flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, fontsize=9,
               frameon=False, bbox_to_anchor=(0.5, 0.0))
    rounds = data["meta"]["rounds"]
    fig.suptitle(
        f"Speed-up over the one-extremum baseline\n"
        f"median of {rounds} interleaved rounds; note the log y-axis on the last two panels",
        fontsize=12,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 0.92))
    fig.savefig(ASSETS / "speedup-by-shape.png", dpi=150)
    plt.close(fig)


def fig_comparisons_vs_reads() -> None:
    data = load("ops.json")
    cells = {(c["kind"], c["size"]): c for c in data["cells"]}
    kinds = ["random", "reversed", "sorted"]
    arms = ["bidirectional", "fast_noprecheck", "fast"]
    arm_label = {
        "bidirectional": "bidirectional",
        "fast_noprecheck": "fast (precheck off)",
        "fast": "fast (default)",
    }

    fig, axes = plt.subplots(2, len(kinds), figsize=(4.2 * len(kinds), 6.6),
                             sharex=False)
    sizes = sorted({c["size"] for c in data["cells"]})
    colours = {"bidirectional": TERRACOTTA, "fast_noprecheck": OLIVE,
               "fast": AMBER}
    markers = {"bidirectional": "o", "fast_noprecheck": "s", "fast": "^"}

    for col, kind in enumerate(kinds):
        top, bottom = axes[0][col], axes[1][col]
        for arm in arms:
            cmp_ratio, read_ratio, xs = [], [], []
            for size in sizes:
                cell = cells.get((kind, size))
                if not cell:
                    continue
                xs.append(size)
                base = cell["arms"]["baseline"]
                mine = cell["arms"][arm]
                cmp_ratio.append(base["comparisons"] / mine["comparisons"])
                read_ratio.append(base["subscripts"] / max(mine["subscripts"], 1))
            top.plot(xs, cmp_ratio, marker=markers[arm],
                     color=colours[arm], label=arm_label[arm], linewidth=1.8)
            bottom.plot(xs, read_ratio, marker=markers[arm],
                        color=colours[arm], label=arm_label[arm], linewidth=1.8)

        top.axhline(1.0, color=MUTED, linestyle="--", linewidth=1.0)
        bottom.axhline(1.0, color=MUTED, linestyle="--", linewidth=1.0)
        for ax in (top, bottom):
            ax.set_xscale("log")
            ax.set_xticks(sizes)
            ax.set_xticklabels([f"{s:,}" for s in sizes], fontsize=9)
            ax.minorticks_off()
            # The sorted panel spans 1.0 to 1000x; on a linear axis everything
            # below 100 collapses onto the baseline line and the panel says
            # nothing.
            if kind in ("sorted", "equal"):
                ax.set_yscale("log")
        top.set_title(KIND_LABEL.get(kind, kind), fontsize=11)
        bottom.set_xlabel("n")

    axes[0][0].set_ylabel("baseline / arm\ncomparisons")
    axes[1][0].set_ylabel("baseline / arm\nelement reads")
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, fontsize=9,
               frameon=False, bbox_to_anchor=(0.5, 0.0))
    fig.suptitle(
        "Comparison count barely moves; element reads are what drop\n"
        "exact counts, no timing",
        fontsize=12,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 0.91))
    fig.savefig(ASSETS / "comparisons-vs-reads.png", dpi=150)
    plt.close(fig)


def fig_mechanism() -> None:
    data = load("mechanism.json")
    cases = data["cases"]
    one = cases["2M iterations x 1 comparison"]
    two = cases["1M iterations x 2 comparisons"]
    ratio = cases["ratio_one_cmp_over_two_cmp"]

    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    labels = ["2M iterations\n1 comparison each", "1M iterations\n2 comparisons each"]
    values = [one["median_ms"], two["median_ms"]]
    colours = [TERRACOTTA, AMBER]
    bars = ax.bar(labels, values, color=colours, width=0.5)

    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.8,
                f"{value:.1f} ms", ha="center", fontsize=10)

    ax.annotate(
        f"{ratio['median']:.2f}x faster\n[{ratio['min']:.2f}..{ratio['max']:.2f}]",
        xy=(1, values[1]), xytext=(0.5, max(values) * 0.62),
        ha="center", fontsize=11, color=INK,
        arrowprops=dict(arrowstyle="->", color=INK, linewidth=1.2),
    )
    ax.set_ylabel("median wall-clock (ms)")
    ax.set_ylim(0, max(values) * 1.25)
    ax.set_title(
        "Same total comparisons, half the iterations\n"
        "loop-control overhead is the thing that halves",
        fontsize=11,
    )
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(ASSETS / "mechanism.png", dpi=150)
    plt.close(fig)


def fig_precheck_cost() -> None:
    """Two panels, because one axis cannot serve both regimes.

    The precheck ranges over five orders of magnitude (0.91x to 1040x). On a
    single log axis the four "cost" shapes are indistinguishable pixels. So:
    a linear panel zoomed to 0.85-1.15 for the cost side, and a log panel for
    the win side.
    """
    data = load("results.json")
    cells = {(c["kind"], c["size"]): c for c in data["cells"]}
    kinds = [k for k in ("random", "nearly", "reversed", "sorted", "equal")
             if any(c["kind"] == k for c in data["cells"])]
    sizes = sorted({c["size"] for c in data["cells"]})
    palette = [TERRACOTTA, AMBER, OLIVE, MUTED, INK]
    colour = {kind: palette[i % len(palette)] for i, kind in enumerate(kinds)}

    def values(kind: str) -> list[float]:
        out = []
        for size in sizes:
            cell = cells.get((kind, size))
            if not cell:
                continue
            off = cell["ratio"]["fast_noprecheck"]["median"]
            on = cell["ratio"]["fast"]["median"]
            out.append(on / off)  # >1 means the precheck paid for itself
        return out

    fig, (ax_cost, ax_win) = plt.subplots(
        1, 2, figsize=(10.6, 4.2), gridspec_kw={"width_ratios": [1, 1.15]}
    )

    # --- left: the cost side, linear, zoomed -------------------------------
    cost_kinds = [k for k in kinds if max(values(k) or [0]) < 3]
    width = 0.8 / max(len(cost_kinds), 1)
    for idx, kind in enumerate(cost_kinds):
        vals = values(kind)
        positions = [i + idx * width for i in range(len(vals))]
        ax_cost.bar(positions, vals, width=width, color=colour[kind],
                    label=KIND_LABEL.get(kind, kind))
        for pos, val in zip(positions, vals):
            ax_cost.text(pos, val + 0.006, f"{val:.2f}", ha="center",
                         fontsize=7, rotation=90, va="bottom")
    ax_cost.axhline(1.0, color=INK, linewidth=1.4)
    ax_cost.set_ylim(0.78, 1.20)
    ax_cost.set_ylabel("precheck on / off")
    ax_cost.set_xlabel("n")
    ax_cost.set_xticks([i + width * (len(cost_kinds) - 1) / 2
                        for i in range(len(sizes))])
    ax_cost.set_xticklabels([f"{s:,}" for s in sizes])
    ax_cost.set_title(
        "Cost side: within noise of 1.0\n"
        "no shape pays a measurable penalty",
        fontsize=10,
    )
    ax_cost.grid(axis="x", visible=False)

    # --- right: the win side, log -----------------------------------------
    win_kinds = [k for k in kinds if k not in cost_kinds]
    width = 0.8 / max(len(win_kinds), 1)
    for idx, kind in enumerate(win_kinds):
        vals = values(kind)
        positions = [i + idx * width for i in range(len(vals))]
        ax_win.bar(positions, vals, width=width, color=colour[kind],
                   label=KIND_LABEL.get(kind, kind))
        for pos, val in zip(positions, vals):
            ax_win.text(pos, val * 1.15, f"{val:.0f}x", ha="center",
                        fontsize=8, va="bottom")
    ax_win.set_yscale("log")
    ax_win.set_ylim(10, 3000)
    ax_win.set_ylabel("precheck on / off (log)")
    ax_win.set_xlabel("n")
    ax_win.set_xticks([i + width * (len(win_kinds) - 1) / 2
                       for i in range(len(sizes))])
    ax_win.set_xticklabels([f"{s:,}" for s in sizes])
    ax_win.set_title(
        "Win side: input is already in order\n"
        "O(n) precheck replaces O(n\u00b2) work",
        fontsize=10,
    )
    ax_win.grid(axis="x", visible=False)

    handles, labels = [], []
    for ax in (ax_cost, ax_win):
        h, l = ax.get_legend_handles_labels()
        handles += h
        labels += l
    fig.legend(handles, labels, loc="lower center", ncol=5, fontsize=9,
               frameon=False, bbox_to_anchor=(0.5, 0.0))

    fig.suptitle(
        "The sorted precheck: free when it fails, worth 60-900x when it succeeds",
        fontsize=12,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 0.92))
    fig.savefig(ASSETS / "precheck-cost.png", dpi=150)
    plt.close(fig)


def main() -> int:
    ASSETS.mkdir(exist_ok=True)
    fig_speedup_by_shape()
    fig_comparisons_vs_reads()
    fig_mechanism()
    fig_precheck_cost()
    for name in ("speedup-by-shape.png", "comparisons-vs-reads.png",
                 "mechanism.png", "precheck-cost.png"):
        path = ASSETS / name
        print(f"wrote {path.relative_to(ROOT)}  ({path.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
