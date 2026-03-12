#!/usr/bin/env python3
"""Parse ngspice output files: wrdata CSV, .log measure results, and waveforms.

Provides structured DataFrames from raw ngspice simulation output.
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def parse_wrdata(filepath: Path | str) -> pd.DataFrame:
    """Parse ngspice wrdata CSV output (space-separated columns).

    ngspice wrdata format:
        - Lines starting with '#' or '*' are comments
        - First column is typically time or index
        - Remaining columns are signal values
        - Columns are whitespace-separated

    Args:
        filepath: Path to wrdata output file

    Returns:
        DataFrame with time as index and signal columns
    """
    filepath = Path(filepath)
    rows = []
    header_names = []

    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("*") or line.startswith("#"):
                # Try to extract column names from comment
                if "v(" in line.lower() or "i(" in line.lower():
                    # Header line with signal names
                    tokens = line.lstrip("*# ").split()
                    header_names = tokens
                continue
            parts = line.split()
            try:
                values = [float(x) for x in parts]
                rows.append(values)
            except ValueError:
                continue

    if not rows:
        return pd.DataFrame()

    data = np.array(rows)

    # Build column names
    n_cols = data.shape[1]
    if header_names and len(header_names) == n_cols:
        columns = header_names
    else:
        columns = ["time"] + [f"col_{i}" for i in range(1, n_cols)]

    df = pd.DataFrame(data, columns=columns)

    # Set time as index if first column looks like time
    if "time" in df.columns:
        df = df.set_index("time")

    return df


def parse_measure_log(filepath: Path | str) -> dict[str, float]:
    """Parse ngspice .log file for .measure results.

    ngspice prints measurements as:
        measure_name = value
        measure_name = value from=... to=...
    or with units.

    Also handles failed measurements:
        measure_name = failed

    Args:
        filepath: Path to ngspice log file

    Returns:
        Dictionary mapping measurement name to value (float).
        Failed measurements are excluded.
    """
    filepath = Path(filepath)
    measures = {}

    text = filepath.read_text()

    # Pattern: name = numeric_value [optional from=... to=...]
    pattern = re.compile(
        r"^\s*(\w+)\s*=\s*([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)",
        re.MULTILINE,
    )

    for match in pattern.finditer(text):
        name = match.group(1)
        value = float(match.group(2))
        measures[name] = value

    return measures


def parse_measure_stdout(stdout: str) -> dict[str, float]:
    """Parse .measure results directly from ngspice stdout/stderr.

    Same format as log file parsing but operates on string input.

    Args:
        stdout: Combined stdout+stderr text from ngspice run

    Returns:
        Dictionary mapping measurement name to value
    """
    measures = {}
    pattern = re.compile(
        r"^\s*(\w+)\s*=\s*([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)",
        re.MULTILINE,
    )
    for match in pattern.finditer(stdout):
        name = match.group(1)
        value = float(match.group(2))
        measures[name] = value
    return measures


def extract_timing_data(
    waveform_df: pd.DataFrame,
    input_col: str,
    output_col: str,
    vdd: float = 1.0,
) -> dict[str, float]:
    """Extract timing data from transient simulation waveforms.

    Computes propagation delays by finding threshold crossings
    at VDD/2 for both rising and falling edges.

    Args:
        waveform_df: DataFrame with time index and signal columns
        input_col: Column name for input signal
        output_col: Column name for output signal
        vdd: Supply voltage for threshold computation

    Returns:
        Dictionary with timing metrics:
            tpd_HL: high-to-low propagation delay (s)
            tpd_LH: low-to-high propagation delay (s)
            tpd_avg: average propagation delay (s)
            t_rise: output rise time 10%-90% (s)
            t_fall: output fall time 90%-10% (s)
    """
    threshold = vdd / 2.0
    thresh_10 = 0.1 * vdd
    thresh_90 = 0.9 * vdd

    time_arr = np.array(waveform_df.index)
    v_in = np.array(waveform_df[input_col])
    v_out = np.array(waveform_df[output_col])

    results = {}

    # Find input rising edge (VDD/2 crossing)
    in_rise_crossings = _find_crossings(time_arr, v_in, threshold, rising=True)
    in_fall_crossings = _find_crossings(time_arr, v_in, threshold, rising=False)

    # Find output rising/falling edges
    out_rise_crossings = _find_crossings(time_arr, v_out, threshold, rising=True)
    out_fall_crossings = _find_crossings(time_arr, v_out, threshold, rising=False)

    # tpd_HL: input rises -> output falls (inverting) or input falls -> output falls
    # For general circuits, measure first input transition to first output transition
    if in_rise_crossings and out_fall_crossings:
        t_in = in_rise_crossings[0]
        # Find first output fall AFTER input rise
        t_out_candidates = [t for t in out_fall_crossings if t > t_in]
        if t_out_candidates:
            results["tpd_HL"] = t_out_candidates[0] - t_in

    if in_fall_crossings and out_rise_crossings:
        t_in = in_fall_crossings[0]
        t_out_candidates = [t for t in out_rise_crossings if t > t_in]
        if t_out_candidates:
            results["tpd_LH"] = t_out_candidates[0] - t_in

    # Also check non-inverting path
    if in_rise_crossings and out_rise_crossings:
        t_in = in_rise_crossings[0]
        t_out_candidates = [t for t in out_rise_crossings if t > t_in]
        if t_out_candidates and "tpd_LH" not in results:
            results["tpd_LH"] = t_out_candidates[0] - t_in

    if in_fall_crossings and out_fall_crossings:
        t_in = in_fall_crossings[0]
        t_out_candidates = [t for t in out_fall_crossings if t > t_in]
        if t_out_candidates and "tpd_HL" not in results:
            results["tpd_HL"] = t_out_candidates[0] - t_in

    # Average propagation delay
    if "tpd_HL" in results and "tpd_LH" in results:
        results["tpd_avg"] = (results["tpd_HL"] + results["tpd_LH"]) / 2.0
    elif "tpd_HL" in results:
        results["tpd_avg"] = results["tpd_HL"]
    elif "tpd_LH" in results:
        results["tpd_avg"] = results["tpd_LH"]

    # Rise time (10% to 90%)
    out_rise_10 = _find_crossings(time_arr, v_out, thresh_10, rising=True)
    out_rise_90 = _find_crossings(time_arr, v_out, thresh_90, rising=True)
    if out_rise_10 and out_rise_90:
        t10 = out_rise_10[0]
        t90_candidates = [t for t in out_rise_90 if t > t10]
        if t90_candidates:
            results["t_rise"] = t90_candidates[0] - t10

    # Fall time (90% to 10%)
    out_fall_90 = _find_crossings(time_arr, v_out, thresh_90, rising=False)
    out_fall_10 = _find_crossings(time_arr, v_out, thresh_10, rising=False)
    if out_fall_90 and out_fall_10:
        t90 = out_fall_90[0]
        t10_candidates = [t for t in out_fall_10 if t > t90]
        if t10_candidates:
            results["t_fall"] = t10_candidates[0] - t90

    return results


def _find_crossings(
    time_arr: np.ndarray,
    signal: np.ndarray,
    threshold: float,
    rising: bool = True,
) -> list[float]:
    """Find threshold crossing times via linear interpolation.

    Args:
        time_arr: Time values
        signal: Signal values
        threshold: Voltage threshold
        rising: If True, find rising crossings; if False, falling

    Returns:
        List of interpolated crossing times
    """
    crossings = []
    for i in range(len(signal) - 1):
        if rising:
            if signal[i] < threshold <= signal[i + 1]:
                # Linear interpolation
                frac = (threshold - signal[i]) / (signal[i + 1] - signal[i])
                t_cross = time_arr[i] + frac * (time_arr[i + 1] - time_arr[i])
                crossings.append(t_cross)
        else:
            if signal[i] >= threshold > signal[i + 1]:
                frac = (signal[i] - threshold) / (signal[i] - signal[i + 1])
                t_cross = time_arr[i] + frac * (time_arr[i + 1] - time_arr[i])
                crossings.append(t_cross)
    return crossings


def waveform_to_digital(
    waveform_df: pd.DataFrame,
    vdd: float = 1.0,
    sample_time: float | None = None,
) -> pd.DataFrame:
    """Convert analog waveform DataFrame to digital (0/1) values.

    Applies VDD/2 threshold to all signal columns. If sample_time is
    provided, returns only the row closest to that time.

    Args:
        waveform_df: DataFrame with time index and analog signal columns
        vdd: Supply voltage for threshold
        sample_time: Optional specific time to sample (seconds)

    Returns:
        DataFrame with same columns but binary (0/1) values
    """
    threshold = vdd / 2.0

    if sample_time is not None:
        # Find closest time point
        idx = (np.abs(np.array(waveform_df.index) - sample_time)).argmin()
        row = waveform_df.iloc[[idx]]
        digital = (row > threshold).astype(int)
    else:
        digital = (waveform_df > threshold).astype(int)

    return digital


def assemble_digital_output(
    digital_row: pd.Series,
    bit_columns: list[str],
) -> int:
    """Assemble integer value from individual bit columns.

    Args:
        digital_row: Series with binary values for each bit
        bit_columns: Column names in LSB-to-MSB order

    Returns:
        Integer value
    """
    value = 0
    for i, col in enumerate(bit_columns):
        if digital_row[col]:
            value |= (1 << i)
    return value


def parse_batch_results(
    results_dir: Path | str,
    n_bits_out: int,
    vdd: float = 1.0,
) -> pd.DataFrame:
    """Parse all wrdata files in a batch results directory.

    Expects files named out_a{A}_b{B}.csv in the directory.

    Args:
        results_dir: Directory containing wrdata output files
        n_bits_out: Number of output bits
        vdd: Supply voltage for digital thresholding

    Returns:
        DataFrame with columns: a, b, output
    """
    results_dir = Path(results_dir)
    rows = []

    pattern = re.compile(r"out_a(\d+)_b(\d+)\.csv")

    for csv_file in sorted(results_dir.glob("out_a*_b*.csv")):
        match = pattern.match(csv_file.name)
        if not match:
            continue

        a_val = int(match.group(1))
        b_val = int(match.group(2))

        df = parse_wrdata(csv_file)
        if df.empty:
            rows.append({"a": a_val, "b": b_val, "output": None})
            continue

        # Use last time point (settled state)
        digital = waveform_to_digital(df, vdd=vdd)
        last_row = digital.iloc[-1]

        # Assemble output integer from bit columns
        bit_cols = [c for c in digital.columns if c.startswith("col_")]
        if bit_cols:
            output_val = assemble_digital_output(last_row, bit_cols[:n_bits_out])
        else:
            output_val = None

        rows.append({"a": a_val, "b": b_val, "output": output_val})

    return pd.DataFrame(rows)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Parse ngspice output files"
    )
    subparsers = parser.add_subparsers(dest="command")

    # wrdata subcommand
    wr_parser = subparsers.add_parser("wrdata", help="Parse wrdata CSV file")
    wr_parser.add_argument("file", help="Path to wrdata output file")

    # measure subcommand
    meas_parser = subparsers.add_parser("measure", help="Parse .measure log")
    meas_parser.add_argument("file", help="Path to ngspice log file")

    # timing subcommand
    time_parser = subparsers.add_parser("timing", help="Extract timing from waveform")
    time_parser.add_argument("file", help="Path to wrdata output file")
    time_parser.add_argument("--input-col", default="col_1")
    time_parser.add_argument("--output-col", default="col_2")
    time_parser.add_argument("--vdd", type=float, default=1.0)

    args = parser.parse_args()

    if args.command == "wrdata":
        df = parse_wrdata(args.file)
        print(f"Shape: {df.shape}")
        print(df.head(10))
        print(f"\nColumns: {list(df.columns)}")

    elif args.command == "measure":
        measures = parse_measure_log(args.file)
        print("Measurements:")
        for name, value in sorted(measures.items()):
            print(f"  {name} = {value:.6e}")

    elif args.command == "timing":
        df = parse_wrdata(args.file)
        timing = extract_timing_data(
            df, args.input_col, args.output_col, vdd=args.vdd,
        )
        print("Timing results:")
        for name, value in sorted(timing.items()):
            print(f"  {name} = {value:.6e} s ({value*1e12:.2f} ps)")

    else:
        parser.print_help()
