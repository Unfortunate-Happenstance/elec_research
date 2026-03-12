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

# Circuit specifications: (netlist_path, output_node_for_tpd, A_bits, B_bits, circuit_key)
CIRCUITS: list[tuple[str, str, int, int, str]] = [
    ("cmos_baseline/rca8_exact_cmos45.sp",  "cout",  8, 8, "rca8_exact"),
    ("cmos_baseline/mul4x4_exact_cmos45.sp", "p7",   4, 4, "mul4x4_exact"),
    ("cmos_approx/loa8_k4_cmos45.sp",       "cout",  8, 8, "loa8_k4"),
    ("cmos_approx/heaa8_k4_cmos45.sp",      "cout",  8, 8, "heaa8_k4"),
    ("cmos_approx/ama5_8bit_cmos45.sp",     "cout",  8, 8, "ama5_8bit"),
    ("cmos_approx/bam4x4_v2_cmos45.sp",     "p7",    4, 4, "bam4x4_v2"),
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
            body_lines.append(line)
            continue

    return "\n".join(body_lines)


def make_timing_netlist(
    circuit_name: str,
    body: str,
    a_bits: int,
    b_bits: int,
    output_node: str,
    settle_time: str = SETTLE_TIME,
    meas_time: str = MEAS_TIME,
) -> str:
    """Build a minimal timing/power netlist for the circuit.

    For adders (a_bits == b_bits == 8):
      - B inputs: static DC = VDD (all 1s) — provides addend
      - A inputs: PULSE 0→VDD at settle_time — triggers worst-case carry ripple
      - Initial state: A=0, B=0xFF → sum=0xFF, COUT=0 (no carry)
      - After trigger: A=0xFF, B=0xFF → sum=0xFE, COUT=1 (carry ripples all 8 stages)
      - TRIG: v(a0) rising / TARG: v(cout) rising

    For multipliers (a_bits == b_bits == 4):
      - A inputs: static DC = VDD (all 1s) — provides multiplicand
      - B inputs: PULSE 0→VDD at settle_time — triggers worst-case output
      - TRIG: v(b0) rising / TARG: v(p7) rising
    """
    vdd_val = VDD
    settle_ns = float(settle_time.rstrip("n"))
    meas_ns = float(meas_time.rstrip("n"))
    total_ns = settle_ns + meas_ns
    tstop = f"{total_ns}n"

    is_adder = (a_bits == b_bits == 8)
    trig_node = "a0" if is_adder else "b0"

    lines = [
        f"* Timing/power characterization — {circuit_name}",
        "* Generated by run_cmos_timing.py",
        "",
    ]

    # Include model + supply
    lines.append(body)
    lines.append("")

    if is_adder:
        # A: PULSE (trigger) — initially 0, rises at settle_time
        for i in range(a_bits):
            lines.append(
                f"Va{i} a{i} 0 PULSE(0 {vdd_val} {settle_time} 50p 50p {meas_time} {tstop})"
            )
        # B: static DC = VDD (all 1s)
        for i in range(b_bits):
            lines.append(f"Vb{i} b{i} 0 dc {vdd_val}")
        # Carry-in = 0
        lines.append("Vcin cin 0 dc 0")
    else:
        # Multipliers: A static, B pulse
        for i in range(a_bits):
            lines.append(f"Va{i} a{i} 0 dc {vdd_val}")
        for i in range(b_bits):
            lines.append(
                f"Vb{i} b{i} 0 PULSE(0 {vdd_val} {settle_time} 50p 50p {meas_time} {tstop})"
            )

    lines.append("")

    # Transient analysis
    lines.append(f".tran 10p {tstop}")
    lines.append("")

    # Measurements (ngspice syntax: VAL= keyword required for TRIG/TARG)
    lines.append(
        f".measure tran tpd_rise TRIG v({trig_node}) VAL=0.5 RISE=1 TARG v({output_node}) VAL=0.5 RISE=1"
    )
    lines.append(
        f".measure tran avg_idd AVG i(Vdd) FROM={settle_time} TO={tstop}"
    )
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

    for rel_path, output_node, a_bits, b_bits, key in CIRCUITS:
        netlist_path = NETLISTS_DIR / rel_path
        if not netlist_path.exists():
            print(f"[SKIP] {key}: netlist not found at {netlist_path}")
            rows.append({"circuit": key, "tpd_ps": "N/A", "power_uW": "N/A", "pdp_fJ": "N/A"})
            continue

        print(f"\n[{key}] Extracting circuit body and building timing netlist...")
        body = extract_circuit_body(netlist_path)
        netlist = make_timing_netlist(key, body, a_bits, b_bits, output_node)

        print(f"[{key}] Running ngspice via Docker...")
        log = run_ngspice_docker(netlist, key)

        measures = parse_measure_output(log)
        print(f"  raw measures: {measures}")

        metrics = compute_metrics(measures)
        print(f"  tpd = {metrics.get('tpd_ps', float('nan')):.1f} ps  "
              f"power = {metrics.get('power_uW', float('nan')):.3f} uW  "
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
