#!/usr/bin/env python3
"""Compute circuit-level performance metrics from ngspice simulation output.

Metrics computed:
  - Propagation delay: tpd_HL, tpd_LH, tpd_avg (ps)
  - Dynamic power (uW)
  - Leakage (static) power (nW)
  - Power-Delay Product (PDP) (fJ)
  - Energy-Delay Product (EDP) (fJ*ps)

Aggregates across all test vectors and outputs circuit_metrics.csv.
"""

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
RAW_DIR = RESULTS_DIR / "raw"
PROCESSED_DIR = RESULTS_DIR / "processed"


def parse_measure_file(filepath: Path) -> dict[str, float]:
    """Parse ngspice .measure results from a log or stdout file.

    Handles formats:
        measure_name = value
        measure_name = value from=... to=...

    Args:
        filepath: Path to ngspice log/output file

    Returns:
        Dictionary of measurement name -> value
    """
    measures = {}
    text = filepath.read_text()

    pattern = re.compile(
        r"^\s*(\w+)\s*=\s*([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)",
        re.MULTILINE,
    )
    for match in pattern.finditer(text):
        name = match.group(1).lower()
        value = float(match.group(2))
        measures[name] = value

    return measures


def compute_metrics_from_measures(measures: dict[str, float]) -> dict[str, float]:
    """Compute derived metrics from raw ngspice .measure results.

    Expected measure names (case-insensitive):
        tpd_rise, tpd_fall: propagation delays (s)
        avg_power: average dynamic power (W)
        leak_power: leakage power (W)

    Args:
        measures: Raw measurement dict from ngspice

    Returns:
        Dictionary of computed metrics with standardized names and units
    """
    metrics = {}

    # Propagation delays
    tpd_hl = measures.get("tpd_fall", measures.get("tpd_hl"))
    tpd_lh = measures.get("tpd_rise", measures.get("tpd_lh"))

    if tpd_hl is not None:
        metrics["tpd_HL_ps"] = abs(tpd_hl) * 1e12  # seconds -> ps
    if tpd_lh is not None:
        metrics["tpd_LH_ps"] = abs(tpd_lh) * 1e12

    if tpd_hl is not None and tpd_lh is not None:
        metrics["tpd_avg_ps"] = (abs(tpd_hl) + abs(tpd_lh)) / 2.0 * 1e12
    elif tpd_hl is not None:
        metrics["tpd_avg_ps"] = abs(tpd_hl) * 1e12
    elif tpd_lh is not None:
        metrics["tpd_avg_ps"] = abs(tpd_lh) * 1e12

    # Power
    avg_power = measures.get("avg_power")
    if avg_power is not None:
        metrics["dynamic_power_uW"] = abs(avg_power) * 1e6  # W -> uW

    leak_power = measures.get("leak_power")
    if leak_power is not None:
        metrics["leakage_power_nW"] = abs(leak_power) * 1e9  # W -> nW

    # Total power (dynamic + leakage)
    if avg_power is not None:
        metrics["total_power_uW"] = abs(avg_power) * 1e6
        if leak_power is not None:
            metrics["total_power_uW"] = (
                abs(avg_power) * 1e6 + abs(leak_power) * 1e3
            )

    # Power-Delay Product (PDP = power * delay)
    if "dynamic_power_uW" in metrics and "tpd_avg_ps" in metrics:
        # PDP in fJ = uW * ps = 1e-6 * 1e-12 = 1e-18 J -> fJ = 1e-15 J
        # uW * ps * 1e-3 = fJ
        metrics["PDP_fJ"] = (
            metrics["dynamic_power_uW"] * metrics["tpd_avg_ps"] * 1e-3
        )

    # Energy-Delay Product (EDP = PDP * delay)
    if "PDP_fJ" in metrics and "tpd_avg_ps" in metrics:
        # EDP in fJ*ps
        metrics["EDP_fJ_ps"] = metrics["PDP_fJ"] * metrics["tpd_avg_ps"]

    return metrics


def aggregate_across_vectors(
    metrics_list: list[dict[str, float]],
) -> dict[str, float]:
    """Aggregate circuit metrics across multiple test vectors.

    Computes mean and max for delay metrics, mean for power metrics.

    Args:
        metrics_list: List of per-vector metric dicts

    Returns:
        Aggregated metrics dictionary
    """
    if not metrics_list:
        return {}

    df = pd.DataFrame(metrics_list)
    agg = {}

    # Delay metrics: use worst-case (max)
    for col in ["tpd_HL_ps", "tpd_LH_ps", "tpd_avg_ps"]:
        if col in df.columns:
            valid = df[col].dropna()
            if len(valid) > 0:
                agg[col] = float(valid.mean())
                agg[f"{col}_max"] = float(valid.max())

    # Power metrics: use mean
    for col in ["dynamic_power_uW", "leakage_power_nW", "total_power_uW"]:
        if col in df.columns:
            valid = df[col].dropna()
            if len(valid) > 0:
                agg[col] = float(valid.mean())

    # Recompute PDP and EDP from aggregated values
    if "dynamic_power_uW" in agg and "tpd_avg_ps" in agg:
        agg["PDP_fJ"] = agg["dynamic_power_uW"] * agg["tpd_avg_ps"] * 1e-3
    if "PDP_fJ" in agg and "tpd_avg_ps" in agg:
        agg["EDP_fJ_ps"] = agg["PDP_fJ"] * agg["tpd_avg_ps"]

    return agg


def process_circuit_results(
    circuit_name: str,
    results_dir: Path | None = None,
) -> dict[str, float]:
    """Process all simulation results for a single circuit design.

    Scans the results directory for .log files, parses measurements,
    computes per-vector metrics, and aggregates.

    Args:
        circuit_name: Name of the circuit (e.g., 'loa8_k4', 'fefet_loa')
        results_dir: Directory containing simulation output files.
                     Defaults to results/raw/{circuit_name}/

    Returns:
        Aggregated metrics dict for the circuit
    """
    if results_dir is None:
        # Search across all raw subdirectories
        possible_dirs = [
            RAW_DIR / "cmos_baseline" / circuit_name,
            RAW_DIR / "cmos_approx" / circuit_name,
            RAW_DIR / "fefet" / circuit_name,
            RAW_DIR / circuit_name,
        ]
        results_dir = None
        for d in possible_dirs:
            if d.exists():
                results_dir = d
                break

        if results_dir is None:
            print(f"Warning: No results directory found for {circuit_name}")
            return {}

    # Find all log/output files
    log_files = sorted(results_dir.glob("*.log")) + sorted(results_dir.glob("*.out"))

    if not log_files:
        # Try parsing from a single combined output file
        combined = results_dir / f"{circuit_name}.log"
        if combined.exists():
            log_files = [combined]

    metrics_list = []
    for log_file in log_files:
        measures = parse_measure_file(log_file)
        if measures:
            metrics = compute_metrics_from_measures(measures)
            if metrics:
                metrics_list.append(metrics)

    if metrics_list:
        return aggregate_across_vectors(metrics_list)

    return {}


def build_circuit_metrics_table(
    circuit_names: list[str],
    output_path: Path | None = None,
) -> pd.DataFrame:
    """Build a comparison table of circuit metrics for all designs.

    Args:
        circuit_names: List of circuit design names
        output_path: Where to save circuit_metrics.csv

    Returns:
        DataFrame with one row per circuit, columns for each metric
    """
    rows = []

    for name in circuit_names:
        print(f"Processing {name}...")
        metrics = process_circuit_results(name)
        metrics["circuit"] = name
        rows.append(metrics)

    df = pd.DataFrame(rows)

    # Reorder columns
    col_order = [
        "circuit",
        "tpd_avg_ps", "tpd_HL_ps", "tpd_LH_ps",
        "dynamic_power_uW", "leakage_power_nW", "total_power_uW",
        "PDP_fJ", "EDP_fJ_ps",
    ]
    existing_cols = [c for c in col_order if c in df.columns]
    extra_cols = [c for c in df.columns if c not in col_order]
    df = df[existing_cols + extra_cols]

    if output_path is None:
        output_path = PROCESSED_DIR / "circuit_metrics.csv"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, float_format="%.6f")

    print(f"\nCircuit metrics saved to: {output_path}")
    print(df.to_string(index=False))

    return df


# Default circuit designs to analyze
DEFAULT_CIRCUITS = [
    "exact_adder_8bit",
    "loa8_k4",
    "heaa8_k4",
    "ama5_8bit_k4",
    "fefet_loa8_k4",
    "fefet_heaa8_k4",
    "exact_mul_4bit",
    "bam4x4_v2",
]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compute circuit-level performance metrics"
    )
    parser.add_argument(
        "--circuits", nargs="+", default=DEFAULT_CIRCUITS,
        help="List of circuit names to process",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output CSV path",
    )
    parser.add_argument(
        "--log-file", type=str, default=None,
        help="Parse a single log file instead of scanning directories",
    )
    args = parser.parse_args()

    if args.log_file:
        # Single file mode
        measures = parse_measure_file(Path(args.log_file))
        metrics = compute_metrics_from_measures(measures)
        print("Raw measurements:")
        for k, v in sorted(measures.items()):
            print(f"  {k} = {v:.6e}")
        print("\nComputed metrics:")
        for k, v in sorted(metrics.items()):
            print(f"  {k} = {v:.6f}")
    else:
        output = Path(args.output) if args.output else None
        build_circuit_metrics_table(args.circuits, output_path=output)
