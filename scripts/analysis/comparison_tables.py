#!/usr/bin/env python3
"""Generate LaTeX-formatted comparison tables for the paper.

Reads circuit_metrics.csv and error_metrics.csv to produce publication-ready
LaTeX table fragments for IEEE paper.
"""

import argparse
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "results" / "processed"
PAPER_DIR = PROJECT_ROOT / "paper" / "tables"


def load_circuit_metrics(filepath: Path | None = None) -> pd.DataFrame:
    """Load circuit performance metrics CSV.

    Args:
        filepath: Path to circuit_metrics.csv

    Returns:
        DataFrame with circuit metrics
    """
    if filepath is None:
        filepath = PROCESSED_DIR / "circuit_metrics.csv"
    return pd.read_csv(filepath)


def load_error_metrics(filepath: Path | None = None) -> pd.DataFrame:
    """Load error metrics CSV.

    Args:
        filepath: Path to error_metrics.csv

    Returns:
        DataFrame with error metrics
    """
    if filepath is None:
        filepath = PROCESSED_DIR / "error_metrics.csv"
    return pd.read_csv(filepath)


def load_mc_statistics(filepath: Path | None = None) -> pd.DataFrame:
    """Load Monte Carlo statistics CSV.

    Args:
        filepath: Path to mc_statistics.csv

    Returns:
        DataFrame with MC statistics
    """
    if filepath is None:
        filepath = PROCESSED_DIR / "mc_statistics.csv"
    return pd.read_csv(filepath)


def _escape_latex(s: str) -> str:
    """Escape special LaTeX characters in a string."""
    replacements = {
        "_": r"\_",
        "&": r"\&",
        "%": r"\%",
        "#": r"\#",
    }
    for old, new in replacements.items():
        s = s.replace(old, new)
    return s


def _format_value(val, fmt: str = ".2f") -> str:
    """Format a numeric value for LaTeX, handling NaN/None."""
    if pd.isna(val):
        return "--"
    try:
        return f"{val:{fmt}}"
    except (ValueError, TypeError):
        return str(val)


def _format_sci(val, precision: int = 2) -> str:
    """Format value in scientific notation for LaTeX.

    Returns something like $1.23 \\times 10^{-3}$ for small values,
    or plain format for values near 1.  Exact zero is printed as "0.0".
    """
    if pd.isna(val):
        return "--"
    if val == 0.0:
        return "0.0"
    if abs(val) < 0.001 or abs(val) >= 10000:
        import math
        exp = int(math.floor(math.log10(abs(val))))
        mantissa = val / (10 ** exp)
        return f"${mantissa:.{precision}f} \\times 10^{{{exp}}}$"
    return f"{val:.{precision}f}"


# Display names for circuits (both error-metrics keys and MC JSON keys)
CIRCUIT_DISPLAY_NAMES = {
    # Behavioural / error-metrics keys
    "exact_adder_8bit": "Exact RCA",
    "loa8_k4":          "LOA (k=4)",
    "heaa8_k4":         "HEAA (k=4)",
    "ama5_8bit_k4":     "AMA5 (k=4)",
    "fefet_loa8_k4":    "FeFET-LOA",
    "fefet_heaa8_k4":   "FeFET-HEAA",
    "exact_mul_4bit":   "Exact Mul",
    "bam4x4_v2":        "BAM (v=2)",
    # MC JSON circuit keys
    "mc_fefet_loa8":    "FeFET-LOA (k=4)",
    "mc_fefet_heaa8":   "FeFET-HEAA (k=4)",
    "mc_fefet_bam4x4":  r"FeFET-BAM $4{\times}4$",
}


def generate_table_ii(
    circuit_metrics: pd.DataFrame | None = None,
    error_metrics: pd.DataFrame | None = None,
    output_path: Path | None = None,
) -> str:
    """Generate Table II: Power, Delay, PDP, NMED, MRED for all designs.

    This is the main comparison table showing circuit performance alongside
    error characteristics.

    Args:
        circuit_metrics: DataFrame with circuit metrics (or loads from file)
        error_metrics: DataFrame with error metrics (or loads from file)
        output_path: Where to save .tex file

    Returns:
        LaTeX table string
    """
    if circuit_metrics is None:
        circuit_metrics = load_circuit_metrics()
    if error_metrics is None:
        error_metrics = load_error_metrics()

    # Merge on circuit name
    if "circuit" in circuit_metrics.columns and "circuit" in error_metrics.columns:
        df = pd.merge(circuit_metrics, error_metrics, on="circuit", how="outer")
    else:
        df = circuit_metrics

    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Circuit Performance and Error Metrics Comparison}",
        r"\label{tab:comparison}",
        r"\begin{tabular}{lrrrrr}",
        r"\toprule",
        r"Design & Power ($\mu$W) & Delay (ps) & PDP (fJ) & NMED & MRED \\",
        r"\midrule",
    ]

    for _, row in df.iterrows():
        circuit = row.get("circuit", "")
        display_name = CIRCUIT_DISPLAY_NAMES.get(circuit, _escape_latex(circuit))

        power = _format_value(row.get("dynamic_power_uW"), ".2f")
        delay = _format_value(row.get("tpd_avg_ps"), ".1f")
        pdp = _format_value(row.get("PDP_fJ"), ".3f")
        nmed_val = _format_sci(row.get("NMED"), 4)
        mred_val = _format_sci(row.get("MRED"), 4)

        lines.append(
            f"{display_name} & {power} & {delay} & {pdp} & {nmed_val} & {mred_val} \\\\"
        )

    lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])

    tex = "\n".join(lines)

    if output_path is None:
        output_path = PAPER_DIR / "table_ii_comparison.tex"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(tex)

    print(f"Table II saved to: {output_path}")
    return tex


def generate_table_iii(
    mc_statistics: pd.DataFrame | None = None,
    output_path: Path | None = None,
) -> str:
    """Generate Table III: MC Variability Statistics.

    Shows nominal NMED, MC mean/std NMED, and delta-NMED for each
    FeFET circuit design.

    Args:
        mc_statistics: DataFrame with MC stats (or loads from file)
        output_path: Where to save .tex file

    Returns:
        LaTeX table string
    """
    if mc_statistics is None:
        mc_statistics = load_mc_statistics()

    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Monte Carlo Variability Analysis ($\sigma_\mathrm{D2D} = 40$\,mV, $N=1000$ iterations)}",
        r"\label{tab:monte_carlo}",
        r"\begin{tabular}{lrrrrrr}",
        r"\toprule",
        (r"Design & $N_\mathrm{conv}$ & Consistency & "
         r"NMED$_\mathrm{nom}$ & $\mu$(NMED) & $\sigma$(NMED) & $\Delta$-NMED \\"),
        r"\midrule",
    ]

    for _, row in mc_statistics.iterrows():
        circuit = row.get("circuit", "")
        display_name = CIRCUIT_DISPLAY_NAMES.get(circuit, _escape_latex(circuit))

        n_success = row.get("n_success")
        n_conv = str(int(n_success)) if not pd.isna(n_success) else "--"

        consistency = row.get("output_consistency")
        if not pd.isna(consistency):
            cons_str = f"{consistency*100:.1f}\\%"
        else:
            cons_str = "--"

        nmed_nom  = _format_sci(row.get("NMED_nominal"), 4)
        nmed_mean = _format_sci(row.get("NMED_mean"), 4)
        nmed_std  = _format_sci(row.get("NMED_std"), 4)
        delta     = _format_sci(row.get("delta_NMED"), 4)

        lines.append(
            f"{display_name} & {n_conv} & {cons_str} & "
            f"{nmed_nom} & {nmed_mean} & {nmed_std} & {delta} \\\\"
        )

    lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])

    tex = "\n".join(lines)

    if output_path is None:
        output_path = PAPER_DIR / "table_iii_monte_carlo.tex"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(tex)

    print(f"Table III saved to: {output_path}")
    return tex


def generate_error_metrics_table(
    error_metrics: pd.DataFrame | None = None,
    output_path: Path | None = None,
) -> str:
    """Generate a detailed error metrics table (NMED, MRED, ER, WCE).

    Args:
        error_metrics: DataFrame with error metrics
        output_path: Where to save .tex file

    Returns:
        LaTeX table string
    """
    if error_metrics is None:
        error_metrics = load_error_metrics()

    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Error Metrics for Approximate Arithmetic Circuits}",
        r"\label{tab:error_metrics}",
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"Design & NMED & MRED & ER (\%) & WCE \\",
        r"\midrule",
    ]

    for _, row in error_metrics.iterrows():
        circuit = row.get("circuit", "")
        display_name = CIRCUIT_DISPLAY_NAMES.get(circuit, _escape_latex(circuit))

        nmed_val = _format_sci(row.get("NMED"), 6)
        mred_val = _format_sci(row.get("MRED"), 6)
        er_val = _format_value(row.get("ER", 0) * 100, ".2f") if not pd.isna(row.get("ER")) else "--"
        wce_val = _format_sci(row.get("WCE"), 6)

        lines.append(
            f"{display_name} & {nmed_val} & {mred_val} & {er_val} & {wce_val} \\\\"
        )

    lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])

    tex = "\n".join(lines)

    if output_path is None:
        output_path = PAPER_DIR / "table_error_metrics.tex"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(tex)

    print(f"Error metrics table saved to: {output_path}")
    return tex


def generate_all_tables():
    """Generate all LaTeX tables from available data."""
    PAPER_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating LaTeX tables...")

    # Table II: Performance + Error Comparison
    try:
        generate_table_ii()
    except FileNotFoundError as e:
        print(f"  Skipping Table II: {e}")

    # Table III: MC Variability
    try:
        generate_table_iii()
    except FileNotFoundError as e:
        print(f"  Skipping Table III: {e}")

    # Detailed error metrics
    try:
        generate_error_metrics_table()
    except FileNotFoundError as e:
        print(f"  Skipping error metrics table: {e}")

    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate LaTeX comparison tables"
    )
    parser.add_argument(
        "--table", choices=["ii", "iii", "error", "all"],
        default="all",
        help="Which table to generate",
    )
    parser.add_argument("--circuit-metrics", type=str, default=None)
    parser.add_argument("--error-metrics", type=str, default=None)
    parser.add_argument("--mc-statistics", type=str, default=None)
    parser.add_argument("--output", type=str, default=None)

    args = parser.parse_args()

    output = Path(args.output) if args.output else None

    if args.table == "ii":
        cm = load_circuit_metrics(Path(args.circuit_metrics)) if args.circuit_metrics else None
        em = load_error_metrics(Path(args.error_metrics)) if args.error_metrics else None
        tex = generate_table_ii(cm, em, output)
        print(tex)

    elif args.table == "iii":
        mc = load_mc_statistics(Path(args.mc_statistics)) if args.mc_statistics else None
        tex = generate_table_iii(mc, output)
        print(tex)

    elif args.table == "error":
        em = load_error_metrics(Path(args.error_metrics)) if args.error_metrics else None
        tex = generate_error_metrics_table(em, output)
        print(tex)

    else:
        generate_all_tables()
