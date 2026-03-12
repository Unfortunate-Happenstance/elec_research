#!/usr/bin/env python3
"""Scatter plot: NMED vs PDP with Pareto frontier.

X-axis: NMED (Normalized Mean Error Distance)
Y-axis: PDP (Power-Delay Product, fJ)

Different markers/colors distinguish CMOS, FeFET, and NCFET designs.
A Pareto frontier line connects the non-dominated points.

Reads from results/processed/ (circuit_metrics.csv + error_metrics.csv).
Saves to results/figures/error_pareto.pdf.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "results" / "processed"
FIGURES_DIR = PROJECT_ROOT / "results" / "figures"

import sys
sys.path.insert(0, str(PROJECT_ROOT))
from scripts.plotting.style import (
    apply_ieee_style,
    get_figure_1col,
    save_figure,
    COLORS,
    TECH_MARKERS,
    FONT_SIZE_ANNOTATION,
    MARKER_SIZE,
)


# Map circuit names to technology category
CIRCUIT_TECHNOLOGY = {
    "exact_adder_8bit": "CMOS",
    "loa8_k4": "CMOS",
    "heaa8_k4": "CMOS",
    "ama5_8bit_k4": "CMOS",
    "fefet_loa8_k4": "FeFET",
    "fefet_heaa8_k4": "FeFET",
    "exact_mul_4bit": "CMOS",
    "bam4x4_v2": "CMOS",
}

# Short labels for annotation
CIRCUIT_SHORT_LABELS = {
    "exact_adder_8bit": "Exact",
    "loa8_k4": "LOA",
    "heaa8_k4": "HEAA",
    "ama5_8bit_k4": "AMA5",
    "fefet_loa8_k4": "Fe-LOA",
    "fefet_heaa8_k4": "Fe-HEAA",
    "exact_mul_4bit": "Exact Mul",
    "bam4x4_v2": "BAM",
}


def compute_pareto_frontier(
    x: np.ndarray,
    y: np.ndarray,
) -> np.ndarray:
    """Compute the Pareto frontier (minimize both x and y).

    Args:
        x: X-axis values (NMED)
        y: Y-axis values (PDP)

    Returns:
        Boolean mask — True for Pareto-optimal points
    """
    n = len(x)
    is_pareto = np.ones(n, dtype=bool)

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            # j dominates i if j is <= in both and < in at least one
            if x[j] <= x[i] and y[j] <= y[i]:
                if x[j] < x[i] or y[j] < y[i]:
                    is_pareto[i] = False
                    break

    return is_pareto


def plot_error_pareto(
    circuit_metrics_csv: Path | None = None,
    error_metrics_csv: Path | None = None,
    output_name: str = "error_pareto",
):
    """Generate NMED vs PDP scatter plot with Pareto frontier.

    Args:
        circuit_metrics_csv: Path to circuit_metrics.csv
        error_metrics_csv: Path to error_metrics.csv
        output_name: Base filename for output
    """
    apply_ieee_style()

    # Load data
    if circuit_metrics_csv is None:
        circuit_metrics_csv = PROCESSED_DIR / "circuit_metrics.csv"
    if error_metrics_csv is None:
        error_metrics_csv = PROCESSED_DIR / "error_metrics.csv"

    try:
        cm = pd.read_csv(circuit_metrics_csv)
        em = pd.read_csv(error_metrics_csv)
        df = pd.merge(cm, em, on="circuit", how="inner")
    except FileNotFoundError:
        print("Data files not found. Creating demo plot with synthetic data.")
        df = pd.DataFrame({
            "circuit": [
                "exact_adder_8bit", "loa8_k4", "heaa8_k4",
                "ama5_8bit_k4", "fefet_loa8_k4", "fefet_heaa8_k4",
            ],
            "NMED": [0.0, 0.035, 0.022, 0.048, 0.035, 0.022],
            "PDP_fJ": [1.66, 1.06, 1.19, 0.95, 0.38, 0.44],
        })

    # Filter to circuits with both NMED and PDP
    df = df.dropna(subset=["NMED", "PDP_fJ"])

    if df.empty:
        print("No data to plot.")
        return

    fig, ax = get_figure_1col()

    # Plot each technology group
    plotted_techs = set()
    for _, row in df.iterrows():
        circuit = row["circuit"]
        tech = CIRCUIT_TECHNOLOGY.get(circuit, "CMOS")
        style = TECH_MARKERS.get(tech, TECH_MARKERS["CMOS"])

        label = style["label"] if tech not in plotted_techs else None
        plotted_techs.add(tech)

        ax.scatter(
            row["NMED"], row["PDP_fJ"],
            marker=style["marker"],
            color=style["color"],
            s=MARKER_SIZE ** 2 * 4,
            edgecolors="black",
            linewidths=0.3,
            label=label,
            zorder=5,
        )

        # Annotate point
        short_label = CIRCUIT_SHORT_LABELS.get(circuit, circuit)
        ax.annotate(
            short_label,
            (row["NMED"], row["PDP_fJ"]),
            textcoords="offset points",
            xytext=(5, 5),
            fontsize=FONT_SIZE_ANNOTATION,
            ha="left",
        )

    # Compute and draw Pareto frontier
    x_vals = df["NMED"].values
    y_vals = df["PDP_fJ"].values
    pareto_mask = compute_pareto_frontier(x_vals, y_vals)

    if np.sum(pareto_mask) >= 2:
        pareto_x = x_vals[pareto_mask]
        pareto_y = y_vals[pareto_mask]
        # Sort by x for line drawing
        sort_idx = np.argsort(pareto_x)
        ax.plot(
            pareto_x[sort_idx], pareto_y[sort_idx],
            "k--", linewidth=0.8, alpha=0.5, zorder=3,
            label="Pareto frontier",
        )

    ax.set_xlabel("NMED")
    ax.set_ylabel("PDP (fJ)")
    ax.legend(loc="upper right")

    # Set axis limits with margin
    x_margin = (x_vals.max() - x_vals.min()) * 0.15 if x_vals.max() > x_vals.min() else 0.01
    y_margin = (y_vals.max() - y_vals.min()) * 0.15 if y_vals.max() > y_vals.min() else 0.1
    ax.set_xlim(x_vals.min() - x_margin, x_vals.max() + x_margin)
    ax.set_ylim(0, y_vals.max() + y_margin)

    fig.tight_layout()
    save_figure(fig, output_name)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Plot NMED vs PDP Pareto scatter plot"
    )
    parser.add_argument("--circuit-metrics", type=str, default=None)
    parser.add_argument("--error-metrics", type=str, default=None)
    parser.add_argument("--output", type=str, default="error_pareto")
    args = parser.parse_args()

    cm = Path(args.circuit_metrics) if args.circuit_metrics else None
    em = Path(args.error_metrics) if args.error_metrics else None
    plot_error_pareto(cm, em, output_name=args.output)
