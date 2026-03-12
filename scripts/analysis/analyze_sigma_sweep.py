#!/usr/bin/env python3
"""
Phase 5 — Analyse FeFET σ sweep results.

Reads all Monte Carlo JSON files in results/raw/sigma_sweep/ and computes
NMED and ER for each (sigma, circuit) point. Outputs:
  - results/processed/sigma_sweep_stats.csv
  - figures/sigma_sweep_nmed.pdf  (NMED vs σ_d2d per circuit)
  - figures/sigma_sweep_er.pdf    (ER   vs σ_d2d per circuit)

Analysis logic:
  For each MC iteration the ngspice netlist runs the LAST test vector
  (B=50 for LOA/HEAA, B=15 for BAM) and measures settled output voltages.
  We threshold at VDD/2=0.5 V to recover bits, reconstruct the output
  integer, then compare to the behavioural-model nominal output (using
  the same stored-A and test-B, but zero VT variability).

  NMED_variability = mean(|nominal_out - perturbed_out|) / max_val
  ER_variability   = fraction(nominal_out != perturbed_out)

  These capture "how often does device variability change the CiM output?"
  — the core "variability-as-approximation" thesis metric.

Usage:
    uv run python scripts/analysis/analyze_sigma_sweep.py
    uv run python scripts/analysis/analyze_sigma_sweep.py --no-plots
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SIGMA_SWEEP_DIR = PROJECT_ROOT / "results" / "raw" / "sigma_sweep"
PROCESSED_DIR = PROJECT_ROOT / "results" / "processed"
FIGURES_DIR = PROJECT_ROOT / "figures"

VDD_HALF = 0.5   # threshold for bit decoding

# -----------------------------------------------------------------------
# Behavioural models to compute nominal outputs (zero variability)
# -----------------------------------------------------------------------

def loa_nominal(a: int, b: int, k: int = 4) -> int:
    """LOA 8-bit output (integer) for stored A and input B."""
    lower_mask = (1 << k) - 1
    sum_lower = (a & lower_mask) | (b & lower_mask)
    carry_k = ((a >> (k - 1)) & 1) & ((b >> (k - 1)) & 1)
    a_upper = a >> k
    b_upper = b >> k
    sum_upper = a_upper + b_upper + carry_k
    return (sum_upper << k) | sum_lower


def heaa_nominal(a: int, b: int, k: int = 4) -> int:
    """HEAA 8-bit output (integer) for stored A and input B."""
    lower_mask = (1 << (k - 1)) - 1
    sum_lower = (a & lower_mask) | (b & lower_mask)
    a_km1 = (a >> (k - 1)) & 1
    b_km1 = (b >> (k - 1)) & 1
    both = a_km1 & b_km1
    either = a_km1 | b_km1
    sum_km1 = 0 if both else either
    carry_k = both
    a_upper = a >> k
    b_upper = b >> k
    sum_upper = a_upper + b_upper + carry_k
    return (sum_upper << k) | (sum_km1 << (k - 1)) | sum_lower


def bam_nominal(a: int, b: int, n: int = 4, v: int = 2) -> int:
    """BAM 4x4 output (integer) for stored A and input B."""
    result = 0
    for i in range(n):
        for j in range(n):
            if (i + j) >= v:
                ai = (a >> i) & 1
                bj = (b >> j) & 1
                result += (ai & bj) << (i + j)
    return result


# Circuit-specific configuration for output decoding
# Keys: (circuit_stem, sigma_dir) → (nominal_func, test_A, test_B, output_bits, bit_names)
#
# Stored A values from CIRCUIT_VT_NOMINALS in run_monte_carlo.py:
#   LOA/HEAA: vt_nominals = [HVT, LVT, HVT, LVT, LVT] → a0=0,a1=1,a2=0,a3=1 → lower=0b1010=10
#   A_upper from testbench: Va4=1,Va5=0,Va6=1,Va7=0 → a4=1,a5=0,a6=1,a7=0 → upper=0b0101=5
#   → A_full = 0b01011010 = 90
#   BAM: vt_nominals = [HVT, LVT, HVT, LVT] → a0=0,a1=1,a2=0,a3=1 → A=0b1010=10
#   BAM last test B=15 (all ones in the testbench dowhile)
#   LOA/HEAA last test B=50 (test_b[7]=50 is last in the list)

CIRCUIT_CONFIG: dict[str, dict] = {
    "mc_fefet_loa8": {
        "nominal_func": lambda a, b: loa_nominal(a, b, k=4),
        "test_A": 90,     # 0b01011010: lower=0b1010, upper=0b0101
        "test_B": 50,     # last test vector in mc_fefet_loa8.sp
        "output_bits": 9, # s0..s7 + cout = 9-bit sum
        "bit_names": [f"s{i}_val" for i in range(8)] + ["cout_val"],
        "bit_weights": [1 << i for i in range(8)] + [256],
    },
    "mc_fefet_heaa8": {
        "nominal_func": lambda a, b: heaa_nominal(a, b, k=4),
        "test_A": 90,
        "test_B": 50,
        "output_bits": 9,
        "bit_names": [f"s{i}_val" for i in range(8)] + ["cout_val"],
        "bit_weights": [1 << i for i in range(8)] + [256],
    },
    "mc_fefet_bam4x4": {
        "nominal_func": lambda a, b: bam_nominal(a, b, n=4, v=2),
        "test_A": 10,     # 0b1010
        "test_B": 15,     # all b-bits high in mc_fefet_bam4x4.sp
        "output_bits": 8, # p0..p7 = 8-bit product
        "bit_names": [f"p{i}_val" for i in range(8)],
        "bit_weights": [1 << i for i in range(8)],
    },
}


def decode_output(measures: dict[str, float], cfg: dict) -> int | None:
    """Decode measured voltages to an integer output.

    Returns None if any required bit is missing from measures.
    """
    result = 0
    for name, weight in zip(cfg["bit_names"], cfg["bit_weights"]):
        v = measures.get(name)
        if v is None:
            return None
        bit = 1 if v >= VDD_HALF else 0
        result += bit * weight
    return result


def load_sigma_results() -> dict[float, dict[str, list[dict]]]:
    """Scan sigma_sweep directory and load all results.

    Returns: {sigma_d2d_V: {circuit_stem: [iteration_result, ...]}}
    """
    data: dict[float, dict[str, list[dict]]] = {}

    if not SIGMA_SWEEP_DIR.exists():
        return data

    sigma_dir_re = re.compile(r"sigma_(\d+)mV$")
    for sdir in sorted(SIGMA_SWEEP_DIR.iterdir()):
        if not sdir.is_dir():
            continue
        m = sigma_dir_re.match(sdir.name)
        if not m:
            continue
        sigma_mv = int(m.group(1))
        sigma_v = sigma_mv / 1000.0

        data[sigma_v] = {}
        for jfile in sorted(sdir.glob("mc_results_*.json")):
            stem = jfile.stem.replace("mc_results_", "")
            try:
                with open(jfile) as f:
                    iterations = json.load(f)
                data[sigma_v][stem] = iterations
            except Exception as e:
                print(f"  [WARN] Failed to load {jfile}: {e}")

    return data


def compute_sigma_stats(
    sigma_results: dict[float, dict[str, list[dict]]],
) -> list[dict]:
    """Compute NMED and ER statistics for each (sigma, circuit) point.

    Returns list of dicts suitable for CSV writing.
    """
    rows: list[dict] = []

    for sigma_v in sorted(sigma_results):
        circuit_data = sigma_results[sigma_v]
        for stem, iterations in sorted(circuit_data.items()):
            cfg = CIRCUIT_CONFIG.get(stem)
            if cfg is None:
                print(f"  [WARN] No config for circuit '{stem}', skipping.")
                continue

            nominal_out = cfg["nominal_func"](cfg["test_A"], cfg["test_B"])
            max_val = (1 << cfg["output_bits"]) - 1

            errors: list[float] = []
            is_wrong: list[int] = []
            n_success = 0
            n_fail = 0

            for it in iterations:
                if not it.get("success", False):
                    n_fail += 1
                    continue
                n_success += 1
                measures = it.get("measures", {})
                decoded = decode_output(measures, cfg)
                if decoded is None:
                    n_fail += 1
                    n_success -= 1
                    continue
                err = abs(nominal_out - decoded) / max_val
                errors.append(err)
                is_wrong.append(1 if decoded != nominal_out else 0)

            if not errors:
                mean_nmed = std_nmed = mean_er = std_er = float("nan")
            else:
                arr = np.array(errors, dtype=float)
                wr  = np.array(is_wrong, dtype=float)
                mean_nmed = float(np.mean(arr))
                std_nmed  = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
                mean_er   = float(np.mean(wr))
                std_er    = float(np.std(wr, ddof=1)) if len(wr) > 1 else 0.0

            rows.append({
                "sigma_d2d_mV":  round(sigma_v * 1000),
                "circuit":       stem,
                "n_success":     n_success,
                "n_fail":        n_fail,
                "nominal_out":   nominal_out,
                "mean_NMED":     mean_nmed,
                "std_NMED":      std_nmed,
                "mean_ER":       mean_er,
                "std_ER":        std_er,
            })

    return rows


def write_stats_csv(rows: list[dict], out_path: Path) -> None:
    """Write sigma sweep stats to CSV."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "sigma_d2d_mV", "circuit", "n_success", "n_fail", "nominal_out",
        "mean_NMED", "std_NMED", "mean_ER", "std_ER",
    ]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Stats written to: {out_path.relative_to(PROJECT_ROOT)}")


def plot_results(rows: list[dict], figures_dir: Path) -> None:
    """Generate NMED and ER vs σ_d2d plots."""
    try:
        import matplotlib
        matplotlib.use("Agg")  # non-interactive backend
        import matplotlib.pyplot as plt
    except ImportError:
        print("  [WARN] matplotlib not available, skipping plots.")
        return

    figures_dir.mkdir(parents=True, exist_ok=True)

    # Group by circuit
    circuits = sorted({r["circuit"] for r in rows})
    sigmas = sorted({r["sigma_d2d_mV"] for r in rows})

    # Map stem → display name
    DISPLAY = {
        "mc_fefet_loa8":   "LOA-8 (k=4)",
        "mc_fefet_heaa8":  "HEAA-8 (k=4)",
        "mc_fefet_bam4x4": "BAM 4×4 (v=2)",
    }
    COLORS = {
        "mc_fefet_loa8":   "#1f77b4",
        "mc_fefet_heaa8":  "#ff7f0e",
        "mc_fefet_bam4x4": "#2ca02c",
    }
    MARKERS = {
        "mc_fefet_loa8":   "o",
        "mc_fefet_heaa8":  "s",
        "mc_fefet_bam4x4": "^",
    }

    # Index rows
    idx: dict[tuple, dict] = {(r["sigma_d2d_mV"], r["circuit"]): r for r in rows}

    for metric, ylabel, fname in [
        ("mean_NMED", "NMED (variability-induced)", "sigma_sweep_nmed.pdf"),
        ("mean_ER",   "Error Rate (variability-induced)", "sigma_sweep_er.pdf"),
    ]:
        fig, ax = plt.subplots(figsize=(6, 4))

        for stem in circuits:
            xs, ys, errs = [], [], []
            for smv in sigmas:
                r = idx.get((smv, stem))
                if r is None:
                    continue
                v = r.get(metric, float("nan"))
                import math
                if math.isnan(v):
                    continue
                xs.append(smv)
                ys.append(v)
                err_key = "std_" + metric.split("_", 1)[1]
                errs.append(r.get(err_key, 0.0))

            if not xs:
                continue
            label = DISPLAY.get(stem, stem)
            color = COLORS.get(stem, None)
            marker = MARKERS.get(stem, "o")
            ax.errorbar(
                xs, ys, yerr=errs,
                label=label, color=color, marker=marker,
                linewidth=1.8, markersize=6, capsize=3,
            )

        ax.set_xlabel("σ$_{D2D}$ (mV)", fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_title("FeFET Variability Impact on CiM Outputs", fontsize=12)
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(left=0)
        ax.set_ylim(bottom=0)

        out_file = figures_dir / fname
        fig.tight_layout()
        fig.savefig(out_file, dpi=150)
        plt.close(fig)
        print(f"  Plot saved: {out_file.relative_to(PROJECT_ROOT)}")


def print_table(rows: list[dict]) -> None:
    """Pretty-print sigma sweep stats to terminal."""
    if not rows:
        print("No data to display.")
        return

    print(f"\n{'σ_d2d (mV)':>12} {'Circuit':<20} {'N_ok':>6} {'mean NMED':>12} {'std NMED':>10} {'mean ER':>10}")
    print("-" * 75)
    for r in rows:
        import math
        nmed_s = f"{r['mean_NMED']:.5f}" if not math.isnan(r['mean_NMED']) else "  N/A  "
        std_s  = f"{r['std_NMED']:.5f}"  if not math.isnan(r['std_NMED'])  else "  N/A  "
        er_s   = f"{r['mean_ER']:.4f}"   if not math.isnan(r['mean_ER'])   else " N/A"
        print(
            f"{r['sigma_d2d_mV']:>12}  "
            f"{r['circuit']:<20} "
            f"{r['n_success']:>6} "
            f"{nmed_s:>12} "
            f"{std_s:>10} "
            f"{er_s:>10}"
        )


def main(make_plots: bool = True) -> None:
    print("Loading sigma sweep results...")
    sigma_results = load_sigma_results()

    if not sigma_results:
        print(f"No results found in {SIGMA_SWEEP_DIR}.")
        print("Run scripts/simulation/run_sigma_sweep.py first.")
        sys.exit(0)

    sigma_vals = sorted(sigma_results)
    circuits = sorted({stem for d in sigma_results.values() for stem in d})
    print(f"Found {len(sigma_vals)} sigma points: {[f'{s*1000:.0f}mV' for s in sigma_vals]}")
    print(f"Found {len(circuits)} circuits: {circuits}")

    print("\nComputing statistics...")
    rows = compute_sigma_stats(sigma_results)

    # CSV output
    out_csv = PROCESSED_DIR / "sigma_sweep_stats.csv"
    write_stats_csv(rows, out_csv)

    # Terminal table
    print_table(rows)

    # Plots
    if make_plots:
        print("\nGenerating plots...")
        plot_results(rows, FIGURES_DIR)

    print("\nDone.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Phase 5: Analyse FeFET σ sweep Monte Carlo results"
    )
    parser.add_argument(
        "--no-plots", action="store_true",
        help="Skip matplotlib figure generation",
    )
    args = parser.parse_args()
    main(make_plots=not args.no_plots)
