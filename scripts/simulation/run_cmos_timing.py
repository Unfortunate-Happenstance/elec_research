#!/usr/bin/env python3
"""
Generate and run timing/power characterization netlists for CMOS circuits.

For each circuit:
  1. Extract subcircuit definitions from the original netlist (everything before .control)
  2. Build a clean timing test with PULSE sources + .measure directives
  3. Run via Docker ngspice
  4. Parse TPD and IDD from log → compute power = IDD × VDD
  5. Write results to results/processed/circuit_metrics.csv

Usage:
    uv run python scripts/simulation/run_cmos_timing.py
"""

from __future__ import annotations

import csv
import re
import subprocess
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
NETLISTS_DIR = PROJECT_ROOT / "netlists"
RAW_DIR = PROJECT_ROOT / "results" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "results" / "processed"

DOCKER_IMAGE = "docker-ngspice:latest"
VDD = 1.0  # V (from supply.inc)
SETTLE_TIME = "5n"   # ns — time to let circuit settle to initial state
MEAS_TIME = "10n"    # ns — time window for timing measurement after trigger

# Circuit specifications: (netlist_path, output_node, A_bits, B_bits, circuit_key, timing_cfg)
#
# timing_cfg keys:
#   a_dc  : list[float] — DC value for each A bit during settle (and non-pulse bits)
#   b_dc  : list[float] — DC value for each B bit during settle (and non-pulse bits)
#   a_pulse : list[int] — indices of A bits that PULSE 0→VDD at settle_time
#   b_pulse : list[int] — indices of B bits that PULSE 0→VDD at settle_time
#   trig_node : str     — node name for TRIG in .measure
#
# Worst-case carry ripple strategy:
#   RCA8   : A=all-1 DC, only b0 pulses 0→1 → 8-FA ripple chain
#   LOA/HEAA : A=all-1 DC, only b3 pulses → AND(a3,b3)=c4 → FA4..FA7 (4-FA chain)
#   AMA5   : a3 pulses 0→1 (c4=a3 wire), a4..a7=1 DC, B=all-0 → FA4..FA7 (4-FA chain)
#   Multipliers: A=all-1 DC, all B bits pulse simultaneously (tree, no clean ripple path)
CIRCUITS: list[tuple[str, str, int, int, str, dict | None]] = [
    (
        "cmos_baseline/rca8_exact_cmos45.sp", "cout", 8, 8, "rca8_exact",
        {"a_dc": [1.0]*8, "b_dc": [0.0]*8, "a_pulse": [], "b_pulse": [0], "trig_node": "b0"},
    ),
    (
        "cmos_baseline/mul4x4_exact_cmos45.sp", "p7", 4, 4, "mul4x4_exact",
        None,  # default: A=DC=VDD, all B pulse
    ),
    (
        "cmos_approx/loa8_k4_cmos45.sp", "cout", 8, 8, "loa8_k4",
        {"a_dc": [1.0]*8, "b_dc": [0.0]*8, "a_pulse": [], "b_pulse": [3], "trig_node": "b3"},
    ),
    (
        "cmos_approx/heaa8_k4_cmos45.sp", "cout", 8, 8, "heaa8_k4",
        {"a_dc": [1.0]*8, "b_dc": [0.0]*8, "a_pulse": [], "b_pulse": [3], "trig_node": "b3"},
    ),
    (
        "cmos_approx/ama5_8bit_cmos45.sp", "cout", 8, 8, "ama5_8bit",
        # a3 is the wire-carry (c4=a3); a4..a7=1 so FA4..FA7 propagate once c4 rises
        {
            "a_dc": [0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0],
            "b_dc": [0.0]*8,
            "a_pulse": [3], "b_pulse": [], "trig_node": "a3",
        },
    ),
    (
        "cmos_approx/bam4x4_v2_cmos45.sp", "p7", 4, 4, "bam4x4_v2",
        None,  # default: A=DC=VDD, all B pulse
    ),
]


def resolve_includes(line: str, netlist_path: Path) -> str:
    """Replace relative .include paths with absolute /workspace paths for Docker."""
    stripped = line.strip().lower()
    if not stripped.startswith(".include"):
        return line

    # Extract the quoted path
    m = re.search(r'["\']([^"\']+)["\']', line)
    if not m:
        return line

    rel = m.group(1)
    # Resolve relative to the netlist's directory, then make absolute
    abs_path = (netlist_path.parent / rel).resolve()
    # Convert to /workspace-relative path for Docker
    try:
        workspace_rel = abs_path.relative_to(PROJECT_ROOT)
        docker_path = f"/workspace/{workspace_rel}"
    except ValueError:
        return line  # can't resolve, leave as-is

    return f".include '{docker_path}'"


def extract_circuit_body(netlist_path: Path) -> str:
    """Extract everything up to (but not including) .control block.

    Returns subcircuit definitions, model includes, param statements.
    Resolves .include paths to absolute /workspace paths for Docker.
    """
    lines = netlist_path.read_text().splitlines()
    body_lines: list[str] = []
    in_subckt = False

    for line in lines:
        stripped = line.strip().lower()

        # Stop at .control block
        if stripped.startswith(".control"):
            break

        # Track subcircuit boundaries
        if stripped.startswith(".subckt"):
            in_subckt = True
        if stripped.startswith(".ends"):
            in_subckt = False
            body_lines.append(line)
            continue

        # Keep model includes (with resolved paths), param, subckt definitions
        if (in_subckt
                or stripped.startswith(".include")
                or stripped.startswith(".param")
                or stripped.startswith(".subckt")
                or stripped.startswith("*")
                or stripped == ""):
            if stripped.startswith(".include"):
                line = resolve_includes(line, netlist_path)
            body_lines.append(line)
            continue

        # Keep the top-level circuit instantiation lines
        # (lines starting with X = subcircuit calls, C = capacitors, R = resistors/wires)
        if stripped and stripped[0] in ("x", "c", "r"):
            # Replace zero-ohm wire resistors with 1m to avoid timestep convergence failure
            if stripped[0] == "r":
                line = re.sub(r'\s+0\s*$', ' 1m', line)
            body_lines.append(line)
            continue

    return "\n".join(body_lines)


def make_timing_netlist(
    circuit_name: str,
    body: str,
    a_bits: int,
    b_bits: int,
    output_node: str,
    timing_cfg: dict | None = None,
    settle_time: str = SETTLE_TIME,
    meas_time: str = MEAS_TIME,
) -> str:
    """Build a minimal worst-case timing netlist for the circuit.

    timing_cfg (optional) specifies per-circuit worst-case setup:
      a_dc, b_dc : per-bit DC values during settle (and non-pulse bits)
      a_pulse, b_pulse : indices of bits that PULSE from their dc val → VDD
      trig_node : SPICE node to TRIG on

    Default (timing_cfg=None) for multipliers: A=DC=VDD, all B bits PULSE.
    """
    vdd_val = VDD
    settle_ns = float(settle_time.rstrip("n"))
    meas_ns = float(meas_time.rstrip("n"))
    total_ns = settle_ns + meas_ns
    tstop = f"{total_ns}n"

    lines = [
        f"* Worst-case timing — {circuit_name}",
        "* Generated by run_cmos_timing.py",
        "",
    ]
    lines.append(body)
    lines.append("")

    if timing_cfg is not None:
        a_dc: list[float] = timing_cfg["a_dc"]
        b_dc: list[float] = timing_cfg["b_dc"]
        a_pulse: list[int] = timing_cfg["a_pulse"]
        b_pulse: list[int] = timing_cfg["b_pulse"]
        trig_node: str = timing_cfg["trig_node"]

        for i in range(a_bits):
            if i in a_pulse:
                lines.append(
                    f"Va{i} a{i} 0 PULSE({a_dc[i]} {vdd_val} {settle_time} 50p 50p {meas_time} {tstop})"
                )
            else:
                lines.append(f"Va{i} a{i} 0 dc {a_dc[i]}")
        for i in range(b_bits):
            if i in b_pulse:
                lines.append(
                    f"Vb{i} b{i} 0 PULSE({b_dc[i]} {vdd_val} {settle_time} 50p 50p {meas_time} {tstop})"
                )
            else:
                lines.append(f"Vb{i} b{i} 0 dc {b_dc[i]}")
        # Carry-in = 0 for adders
        if a_bits == b_bits == 8:
            lines.append("Vcin cin 0 dc 0")
    else:
        # Default: multipliers — A=DC=VDD, all B pulse
        trig_node = "b0"
        for i in range(a_bits):
            lines.append(f"Va{i} a{i} 0 dc {vdd_val}")
        for i in range(b_bits):
            lines.append(
                f"Vb{i} b{i} 0 PULSE(0 {vdd_val} {settle_time} 50p 50p {meas_time} {tstop})"
            )

    lines.append("")
    lines.append(f".tran 10p {tstop}")
    lines.append("")
    lines.append(
        f".measure tran tpd_rise TRIG v({trig_node}) VAL=0.5 RISE=1 TARG v({output_node}) VAL=0.5 RISE=1"
    )
    lines.append("")
    lines.append(".end")
    lines.append("")
    return "\n".join(lines)


def make_power_netlist(
    circuit_name: str,
    body: str,
    a_bits: int,
    b_bits: int,
    settle_time: str = SETTLE_TIME,
    meas_time: str = MEAS_TIME,
) -> str:
    """Build a max-activity power netlist: all inputs switch simultaneously."""
    vdd_val = VDD
    settle_ns = float(settle_time.rstrip("n"))
    meas_ns = float(meas_time.rstrip("n"))
    total_ns = settle_ns + meas_ns
    tstop = f"{total_ns}n"

    is_adder = (a_bits == b_bits == 8)

    lines = [
        f"* Max-activity power — {circuit_name}",
        "* Generated by run_cmos_timing.py",
        "",
    ]
    lines.append(body)
    lines.append("")

    if is_adder:
        # All A bits PULSE; B=DC=VDD
        for i in range(a_bits):
            lines.append(
                f"Va{i} a{i} 0 PULSE(0 {vdd_val} {settle_time} 50p 50p {meas_time} {tstop})"
            )
        for i in range(b_bits):
            lines.append(f"Vb{i} b{i} 0 dc {vdd_val}")
        lines.append("Vcin cin 0 dc 0")  # only needed by RCA; harmless for others
    else:
        # All B bits PULSE; A=DC=VDD
        for i in range(a_bits):
            lines.append(f"Va{i} a{i} 0 dc {vdd_val}")
        for i in range(b_bits):
            lines.append(
                f"Vb{i} b{i} 0 PULSE(0 {vdd_val} {settle_time} 50p 50p {meas_time} {tstop})"
            )

    lines.append("")
    lines.append(f".tran 10p {tstop}")
    lines.append("")
    lines.append(f".measure tran avg_idd AVG i(Vdd) FROM={settle_time} TO={tstop}")
    lines.append("")
    lines.append(".end")
    lines.append("")
    return "\n".join(lines)


def run_ngspice_docker(netlist_content: str, label: str) -> str:
    """Write netlist to a temp file and run via Docker. Returns stdout+stderr."""
    # Write to a temp file inside the project dir so Docker can access it
    tmp_dir = PROJECT_ROOT / "results" / "raw" / "timing_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_netlist = tmp_dir / f"timing_{label}.sp"
    tmp_netlist.write_text(netlist_content)

    rel_path = tmp_netlist.relative_to(PROJECT_ROOT)
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{PROJECT_ROOT}:/workspace",
        "-w", "/workspace",
        DOCKER_IMAGE,
        "ngspice", "-b", str(rel_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    output = result.stdout + result.stderr

    # Save log
    log_path = tmp_dir / f"timing_{label}.log"
    log_path.write_text(output)
    print(f"  Log saved: {log_path.relative_to(PROJECT_ROOT)}")
    return output


def parse_measure_output(log: str) -> dict[str, float]:
    """Parse ngspice .measure results from stdout.

    Handles:
        tpd_rise        =  3.45678e-10 from=... to=...
        avg_idd         = -5.23456e-05
    """
    measures: dict[str, float] = {}
    pattern = re.compile(
        r"^\s*(\w+)\s*=\s*([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)",
        re.MULTILINE | re.IGNORECASE,
    )
    for m in pattern.finditer(log):
        name = m.group(1).lower()
        val = float(m.group(2))
        measures[name] = val
    return measures


def compute_metrics(measures: dict[str, float]) -> dict[str, float]:
    """Convert raw measures to paper-ready metrics."""
    metrics: dict[str, float] = {}

    tpd = measures.get("tpd_rise")
    if tpd is not None and tpd > 0:
        metrics["tpd_ps"] = tpd * 1e12  # s → ps
    else:
        metrics["tpd_ps"] = float("nan")

    idd = measures.get("avg_idd")
    if idd is not None:
        # i(Vdd) is negative (current flowing INTO Vdd, i.e., out of circuit)
        # Power = |idd| × VDD
        power_w = abs(idd) * VDD
        metrics["power_uW"] = power_w * 1e6  # W → μW
    else:
        metrics["power_uW"] = float("nan")

    tpd_ps = metrics.get("tpd_ps", float("nan"))
    power_uW = metrics.get("power_uW", float("nan"))

    import math
    if not (math.isnan(tpd_ps) or math.isnan(power_uW)):
        metrics["pdp_fJ"] = power_uW * tpd_ps * 1e-3  # uW * ps → fJ
    else:
        metrics["pdp_fJ"] = float("nan")

    return metrics


def main() -> None:
    import math

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    for rel_path, output_node, a_bits, b_bits, key, timing_cfg in CIRCUITS:
        netlist_path = NETLISTS_DIR / rel_path
        if not netlist_path.exists():
            print(f"[SKIP] {key}: netlist not found at {netlist_path}")
            rows.append({"circuit": key, "tpd_ps": "N/A", "power_uW": "N/A", "pdp_fJ": "N/A"})
            continue

        print(f"\n[{key}] Extracting circuit body...")
        body = extract_circuit_body(netlist_path)

        # --- Timing test (worst-case critical path) ---
        print(f"[{key}] Running worst-case timing test...")
        timing_nl = make_timing_netlist(key, body, a_bits, b_bits, output_node, timing_cfg)
        timing_log = run_ngspice_docker(timing_nl, f"{key}_timing")
        timing_measures = parse_measure_output(timing_log)

        tpd = timing_measures.get("tpd_rise")
        tpd_ps = tpd * 1e12 if (tpd is not None and tpd > 0) else float("nan")
        print(f"  tpd_rise raw = {timing_measures.get('tpd_rise')}  →  tpd = {tpd_ps:.1f} ps")

        # --- Power test (max switching activity: all inputs toggle) ---
        print(f"[{key}] Running max-activity power test...")
        power_nl = make_power_netlist(key, body, a_bits, b_bits)
        power_log = run_ngspice_docker(power_nl, f"{key}_power")
        power_measures = parse_measure_output(power_log)

        idd = power_measures.get("avg_idd")
        power_uW = abs(idd) * VDD * 1e6 if idd is not None else float("nan")
        print(f"  avg_idd raw = {idd}  →  power = {power_uW:.3f} uW")

        measures = {"tpd_rise": tpd, "avg_idd": idd}
        metrics = compute_metrics(measures)
        print(f"  tpd = {tpd_ps:.1f} ps  power = {power_uW:.3f} uW  "
              f"PDP = {metrics.get('pdp_fJ', float('nan')):.4f} fJ")

        rows.append({"circuit": key, **metrics})

    # Write CSV
    out_csv = PROCESSED_DIR / "circuit_metrics.csv"
    fieldnames = ["circuit", "tpd_ps", "power_uW", "pdp_fJ"]
    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"\nCircuit metrics saved to: {out_csv}")
    print("\nSummary:")
    print(f"{'Circuit':<20} {'tpd (ps)':>10} {'Power (uW)':>12} {'PDP (fJ)':>10}")
    print("-" * 55)
    for row in rows:
        tpd = row.get("tpd_ps", float("nan"))
        pwr = row.get("power_uW", float("nan"))
        pdp = row.get("pdp_fJ", float("nan"))
        tpd_s = f"{tpd:.1f}" if isinstance(tpd, float) and not math.isnan(tpd) else "N/A"
        pwr_s = f"{pwr:.3f}" if isinstance(pwr, float) and not math.isnan(pwr) else "N/A"
        pdp_s = f"{pdp:.4f}" if isinstance(pdp, float) and not math.isnan(pdp) else "N/A"
        print(f"{row['circuit']:<20} {tpd_s:>10} {pwr_s:>12} {pdp_s:>10}")


if __name__ == "__main__":
    main()
