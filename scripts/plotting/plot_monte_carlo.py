#!/usr/bin/env python3
"""Monte Carlo variability plots.

Two subplots:
  (a) Histogram of NMED across MC iterations (approx vs exact)
  (b) Line plot: NMED vs sigma_D2D for each circuit

Reads from results/processed/ and results/raw/monte_carlo/.
Saves to results/figures/monte_carlo.pdf.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "results" / "processed"
MC_RAW_DIR = PROJECT_ROOT / "results" / "raw" / "monte_carlo"
FIGURES_DIR = PROJECT_ROOT / "results" / "figures"

import sys
sys.path.insert(0, str(PROJECT_ROOT))
from scripts.plotting.style import (
    apply_ieee_style,
    get_figure_2col,
    save_figure,
    annotate_subplot,
    COLORS,
    COLOR_CYCLE,
    LINE_STYLES,
    MARKER_STYLES,
    MARKER_SIZE,
    FONT_SIZE_ANNOTATION,
)


def load_mc_nmed_values(json_path: Path) -> np.ndarray:
    """Extract NMED values from MC results JSON.

    Args:
        json_path: Path to mc_results_*.json

    Returns:
        Array of NMED values across iterations
    """
    with open(json_path) as f:
        results = json.load(f)

    nmed_values = []
    for r in results:
        if r.get("success") and "measures" in r:
            if "nmed" in r["measures"]:
                nmed_values.append(r["measures"]["nmed"])

    return np.array(nmed_values) if nmed_values else np.array([])


def plot_monte_carlo(
    mc_json_dir: Path | None = None,
    sigma_sweep_csv: Path | None = None,
    output_name: str = "monte_carlo",
):
    """Generate Monte Carlo analysis figure.

    Args:
        mc_json_dir: Directory with MC result JSON files
        sigma_sweep_csv: CSV with sigma sweep data (sigma_d2d, NMED_mean, ...)
        output_name: Base filename for output
    """
    apply_ieee_style()

    if mc_json_dir is None:
        mc_json_dir = MC_RAW_DIR

    fig, (ax1, ax2) = get_figure_2col(n_rows=1, n_cols=2)

    # ---- (a) Histogram of NMED across MC iterations ----
    _plot_nmed_histogram(ax1, mc_json_dir)
    annotate_subplot(ax1, "(a)")

    # ---- (b) NMED vs sigma_D2D ----
    _plot_nmed_vs_sigma(ax2, mc_json_dir, sigma_sweep_csv)
    annotate_subplot(ax2, "(b)")

    fig.tight_layout()
    save_figure(fig, output_name)
    plt.close(fig)


def _plot_nmed_histogram(ax: plt.Axes, mc_json_dir: Path):
    """Plot histogram of NMED across MC iterations.

    Shows distributions for both approximate and exact circuits
    to illustrate the spread due to variability.

    Args:
        ax: Matplotlib axes to plot on
        mc_json_dir: Directory with MC JSON files
    """
    mc_json_dir = Path(mc_json_dir)

    # Collect NMED arrays for each circuit
    circuit_data = {}
    for json_file in sorted(mc_json_dir.glob("mc_results_*.json")):
        circuit_name = json_file.stem.replace("mc_results_", "")
        nmed_vals = load_mc_nmed_values(json_file)
        if len(nmed_vals) > 0:
            circuit_data[circuit_name] = nmed_vals

    if not circuit_data:
        raise FileNotFoundError(
            f"No MC result JSON files found in '{mc_json_dir}' or all files yielded "
            "zero NMED values. Run the Monte Carlo simulations first:\n"
            "  uv run python scripts/simulation/run_monte_carlo.py --circuit <netlist> ..."
        )

    # Plot histograms
    bins = 40
    alpha = 0.6
    for i, (name, values) in enumerate(circuit_data.items()):
        color = COLOR_CYCLE[i % len(COLOR_CYCLE)]
        ax.hist(
            values, bins=bins, alpha=alpha,
            color=color, edgecolor="black", linewidth=0.3,
            label=name, density=True,
        )

        # Add vertical line at mean
        mean_val = np.mean(values)
        ax.axvline(
            mean_val, color=color, linestyle="--", linewidth=0.8,
        )
        ax.text(
            mean_val, ax.get_ylim()[1] * 0.9,
            f"$\\mu$={mean_val:.4f}",
            color=color,
            fontsize=FONT_SIZE_ANNOTATION,
            ha="center",
        )

    ax.set_xlabel("NMED")
    ax.set_ylabel("Density")
    ax.legend(loc="upper right")


def _plot_nmed_vs_sigma(
    ax: plt.Axes,
    mc_json_dir: Path,
    sigma_sweep_csv: Path | None = None,
):
    """Plot NMED vs sigma_D2D for each circuit.

    Args:
        ax: Matplotlib axes to plot on
        mc_json_dir: Directory with MC JSON files
        sigma_sweep_csv: Pre-computed sigma sweep data
    """
    # Try loading pre-computed sigma sweep data
    if sigma_sweep_csv and Path(sigma_sweep_csv).exists():
        df = pd.read_csv(sigma_sweep_csv)
        circuits = df["circuit"].unique() if "circuit" in df.columns else []

        for i, circuit in enumerate(circuits):
            cdf = df[df["circuit"] == circuit].sort_values("sigma_d2d")
            color = COLOR_CYCLE[i % len(COLOR_CYCLE)]
            ls = LINE_STYLES[i % len(LINE_STYLES)]
            ms = MARKER_STYLES[i % len(MARKER_STYLES)]

            ax.errorbar(
                cdf["sigma_d2d"] * 1000,  # V -> mV
                cdf["NMED_mean"],
                yerr=cdf["NMED_std"] if "NMED_std" in cdf.columns else None,
                fmt=f"{ms}{ls}",
                color=color,
                markersize=MARKER_SIZE,
                linewidth=1.0,
                capsize=2,
                label=circuit,
            )
    else:
        # Try to extract sigma sweep from multiple JSON files
        mc_json_dir = Path(mc_json_dir)
        sigma_data = {}

        for json_file in sorted(mc_json_dir.glob("mc_*.json")):
            name = json_file.stem
            # Try to parse sigma from filename
            import re
            sigma_match = re.search(r"sigma[_]?(\d+\.?\d*)", name)
            circuit_match = re.search(r"mc_results?_(.+?)_sigma", name)
            if sigma_match and circuit_match:
                sigma = float(sigma_match.group(1))
                circuit = circuit_match.group(1)
                nmed_vals = load_mc_nmed_values(json_file)
                if len(nmed_vals) > 0:
                    key = circuit
                    if key not in sigma_data:
                        sigma_data[key] = []
                    sigma_data[key].append({
                        "sigma": sigma,
                        "mean": np.mean(nmed_vals),
                        "std": np.std(nmed_vals),
                    })

        if sigma_data:
            for i, (circuit, data) in enumerate(sigma_data.items()):
                data.sort(key=lambda d: d["sigma"])
                sigmas = [d["sigma"] * 1000 for d in data]
                means = [d["mean"] for d in data]
                stds = [d["std"] for d in data]
                color = COLOR_CYCLE[i % len(COLOR_CYCLE)]
                ls = LINE_STYLES[i % len(LINE_STYLES)]
                ms = MARKER_STYLES[i % len(MARKER_STYLES)]

                ax.errorbar(
                    sigmas, means, yerr=stds,
                    fmt=f"{ms}{ls}",
                    color=color,
                    markersize=MARKER_SIZE,
                    linewidth=1.0,
                    capsize=2,
                    label=circuit,
                )
        else:
            raise FileNotFoundError(
                f"No sigma-sweep CSV found at '{sigma_sweep_csv}' and no sigma metadata "
                "in MC JSON files. Run the sigma sweep first:\n"
                "  for sigma in 0.04 0.10 0.20 0.30 0.40; do\n"
                "    uv run python scripts/simulation/run_monte_carlo.py "
                "--circuit <netlist> --sigma-d2d $sigma ...\n"
                "  done"
            )

    ax.set_xlabel(r"$\sigma_\mathrm{D2D}$ (mV)")
    ax.set_ylabel("NMED")
    ax.legend(loc="upper left")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Plot Monte Carlo variability analysis"
    )
    parser.add_argument("--mc-dir", type=str, default=None,
                        help="Directory with MC JSON files")
    parser.add_argument("--sigma-csv", type=str, default=None,
                        help="Pre-computed sigma sweep CSV")
    parser.add_argument("--output", type=str, default="monte_carlo")
    args = parser.parse_args()

    mc_dir = Path(args.mc_dir) if args.mc_dir else None
    sigma_csv = Path(args.sigma_csv) if args.sigma_csv else None
    plot_monte_carlo(mc_dir, sigma_csv, output_name=args.output)
