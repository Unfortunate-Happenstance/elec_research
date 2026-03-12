#!/usr/bin/env python3
"""Grouped bar chart: power and delay for all circuit designs.

Generates a two-subplot figure:
  (a) Power (uW) for each design
  (b) Delay (ps) for each design

Reads from results/processed/circuit_metrics.csv.
Saves to results/figures/benchmark_bars.pdf.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "results" / "processed"
FIGURES_DIR = PROJECT_ROOT / "results" / "figures"

# Import plotting style
import sys
sys.path.insert(0, str(PROJECT_ROOT))
from scripts.plotting.style import (
    apply_ieee_style,
    get_figure_2col,
    save_figure,
    annotate_subplot,
    COLORS,
    COLOR_CYCLE,
    FONT_SIZE_TICK,
)

# Display order and names
DESIGN_ORDER = [
    "exact_adder_8bit",
    "loa8_k4",
    "heaa8_k4",
    "ama5_8bit_k4",
    "fefet_loa8_k4",
    "fefet_heaa8_k4",
]

DESIGN_LABELS = {
    "exact_adder_8bit": "Exact\nRCA",
    "loa8_k4": "LOA\n(k=4)",
    "heaa8_k4": "HEAA\n(k=4)",
    "ama5_8bit_k4": "AMA5\n(k=4)",
    "fefet_loa8_k4": "FeFET\nLOA",
    "fefet_heaa8_k4": "FeFET\nHEAA",
}

# Color mapping by technology
DESIGN_COLORS = {
    "exact_adder_8bit": COLORS["blue"],
    "loa8_k4": COLORS["cyan"],
    "heaa8_k4": COLORS["green"],
    "ama5_8bit_k4": COLORS["purple"],
    "fefet_loa8_k4": COLORS["orange"],
    "fefet_heaa8_k4": COLORS["red"],
}


def plot_benchmark_bars(
    metrics_csv: Path | None = None,
    output_name: str = "benchmark_bars",
):
    """Generate grouped bar chart comparing power and delay.

    Args:
        metrics_csv: Path to circuit_metrics.csv
        output_name: Base filename for output (without extension)
    """
    apply_ieee_style()

    if metrics_csv is None:
        metrics_csv = PROCESSED_DIR / "circuit_metrics.csv"

    df = pd.read_csv(metrics_csv)

    # Filter and reorder
    df = df[df["circuit"].isin(DESIGN_ORDER)]
    df = df.set_index("circuit").loc[
        [c for c in DESIGN_ORDER if c in df.index]
    ].reset_index()

    if df.empty:
        raise ValueError(
            f"No circuits from DESIGN_ORDER found in '{metrics_csv}'. "
            "Run SPICE timing/power sweeps to populate circuit_metrics.csv before plotting."
        )

    labels = [DESIGN_LABELS.get(c, c) for c in df["circuit"]]
    colors = [DESIGN_COLORS.get(c, COLORS["gray"]) for c in df["circuit"]]
    x = np.arange(len(labels))
    bar_width = 0.6

    fig, (ax1, ax2) = get_figure_2col(n_rows=1, n_cols=2)

    # (a) Power
    power_vals = df["dynamic_power_uW"].fillna(0).values
    bars1 = ax1.bar(
        x, power_vals,
        width=bar_width,
        color=colors,
        edgecolor="black",
        linewidth=0.5,
    )
    ax1.set_ylabel(r"Power ($\mu$W)")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=FONT_SIZE_TICK)
    ax1.set_ylim(0, max(power_vals) * 1.2 if max(power_vals) > 0 else 10)

    # Add value labels on bars
    for bar, val in zip(bars1, power_vals):
        if val > 0:
            ax1.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(power_vals) * 0.02,
                f"{val:.1f}",
                ha="center", va="bottom",
                fontsize=FONT_SIZE_TICK - 1,
            )
    annotate_subplot(ax1, "(a)")

    # (b) Delay
    delay_vals = df["tpd_avg_ps"].fillna(0).values
    bars2 = ax2.bar(
        x, delay_vals,
        width=bar_width,
        color=colors,
        edgecolor="black",
        linewidth=0.5,
    )
    ax2.set_ylabel("Delay (ps)")
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, fontsize=FONT_SIZE_TICK)
    ax2.set_ylim(0, max(delay_vals) * 1.2 if max(delay_vals) > 0 else 500)

    for bar, val in zip(bars2, delay_vals):
        if val > 0:
            ax2.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(delay_vals) * 0.02,
                f"{val:.0f}",
                ha="center", va="bottom",
                fontsize=FONT_SIZE_TICK - 1,
            )
    annotate_subplot(ax2, "(b)")

    fig.tight_layout()
    save_figure(fig, output_name)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Plot power and delay benchmark bars"
    )
    parser.add_argument(
        "--metrics", type=str, default=None,
        help="Path to circuit_metrics.csv",
    )
    parser.add_argument(
        "--output", type=str, default="benchmark_bars",
        help="Output filename (without extension)",
    )
    args = parser.parse_args()

    metrics = Path(args.metrics) if args.metrics else None
    plot_benchmark_bars(metrics_csv=metrics, output_name=args.output)
