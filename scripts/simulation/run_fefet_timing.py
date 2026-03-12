#!/usr/bin/env python3
"""
Phase 4 — FeFET circuit timing and power characterization.

Runs worst-case timing and max-switching-activity power tests for the three
FeFET approximate circuits. Outputs fefet_circuit_metrics.csv alongside
the existing CMOS circuit_metrics.csv for side-by-side comparison.

FeFET CiM key difference vs CMOS:
  - Operand A[3:0] is *stored* in FeFET VT states via .param vt_a0..vt_a3
    (vt_a=0.12 ≡ LVT ≡ stored-1; vt_a=1.20 ≡ HVT ≡ stored-0)
  - No Va0..Va3 voltage sources; only Va4..Va7 for the exact CMOS upper half
  - BAM has no Va sources at all (all 4 A-bits stored)

Timing strategy (mirror of CMOS worst-case):
  LOA8  : b3 PULSE 0→1, Va4..Va7=1V DC, b4..b7=0 DC, stored A[3:0]=1111 (LVT)
           → AND(a3_stored=1, b3=↑) = c4 ↑ → 4-FA ripple chain → cout
  HEAA8 : same b3 PULSE strategy (boundary correction also triggered by b3↑)
  BAM4x4: all b bits PULSE simultaneously (adder tree — no serial ripple path)

Usage:
    uv run python scripts/simulation/run_fefet_timing.py
"""

from __future__ import annotations

import csv
import math
import re
import subprocess
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
NETLISTS_DIR = PROJECT_ROOT / "netlists"
RAW_DIR = PROJECT_ROOT / "results" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "results" / "processed"

DOCKER_IMAGE = "docker-ngspice:latest"
VDD = 1.0        # V (from supply.inc)
SETTLE_TIME = "5n"
MEAS_TIME = "10n"

# Circuit list: (netlist_rel_path, output_node, n_b_bits, n_a_upper, circuit_key, timing_cfg)
#
# n_b_bits    — number of B voltage sources needed (all circuits: full B width)
# n_a_upper   — number of upper A voltage sources (Va4..Va{n_a_upper+3}); 0 for BAM
#
# timing_cfg keys:
#   a_upper_dc  : list[float] — DC for Va4..Va{3+n_a_upper} (e.g. [1,1,1,1] for adders)
#   b_dc        : list[float] — DC for each Vb during settle/non-pulse
#   b_pulse     : list[int]   — indices of B bits that PULSE 0→VDD
#   trig_node   : str         — node for TRIG in .measure
CIRCUITS: list[tuple[str, str, int, int, str, dict]] = [
    (
        "fefet/fefet_loa8_k4.sp", "cout", 8, 4, "fefet_loa8_k4",
        {
            # b3 PULSE triggers AND(stored-a3=1, b3=↑) → c4 ↑ → 4-FA chain → cout
            "a_upper_dc": [1.0, 1.0, 1.0, 1.0],  # Va4..Va7 = 1 (propagate)
            "b_dc":       [0.0] * 8,
            "b_pulse":    [3],
            "trig_node":  "b3",
        },
    ),
    (
        "fefet/fefet_heaa8_k4.sp", "cout", 8, 4, "fefet_heaa8_k4",
        {
            # b3 PULSE: AND(a3,b3) → carry_gen3; XOR(a3,b3) changes too
            # → c4 ↑ → FA4..FA7 ripple → cout
            "a_upper_dc": [1.0, 1.0, 1.0, 1.0],
            "b_dc":       [0.0] * 8,
            "b_pulse":    [3],
            "trig_node":  "b3",
            # XOR cell TG port bug fixed (a_sense/b_input swapped); DCOP now converges.
            # UIC workaround removed — standard DCOP gives cout=0 at rest.
        },
    ),
    (
        "fefet/fefet_bam4x4_v2.sp", "p7", 4, 0, "fefet_bam4x4_v2",
        {
            # All B bits pulse (parallel adder tree — no serial chain)
            "a_upper_dc": [],   # no upper A voltage sources in BAM
            "b_dc":       [0.0, 0.0, 0.0, 0.0],
            "b_pulse":    [0, 1, 2, 3],
            "trig_node":  "b0",
        },
    ),
]


def resolve_includes(line: str, netlist_path: Path) -> str:
    """Replace relative .include paths with absolute /workspace paths for Docker."""
    stripped = line.strip().lower()
    if not stripped.startswith(".include"):
        return line
    m = re.search(r'["\']([^"\']+)["\']', line)
    if not m:
        return line
    rel = m.group(1)
    abs_path = (netlist_path.parent / rel).resolve()
    try:
        workspace_rel = abs_path.relative_to(PROJECT_ROOT)
        return f".include '/workspace/{workspace_rel}'"
    except ValueError:
        return line


def extract_circuit_body(netlist_path: Path) -> str:
    """Extract subcircuit defs, model includes, params, and top-level X/C/R lines.

    Stops before the .control block. Resolves .include paths to /workspace for Docker.
    Wire resistors with value 0 are replaced by 1m to avoid ngspice convergence failure.
    """
    lines = netlist_path.read_text().splitlines()
    body_lines: list[str] = []
    in_subckt = False

    for line in lines:
        stripped = line.strip().lower()

        if stripped.startswith(".control"):
            break

        if stripped.startswith(".subckt"):
            in_subckt = True
        if stripped.startswith(".ends"):
            in_subckt = False
            body_lines.append(line)
            continue

        if (in_subckt
                or stripped.startswith(".include")
                or stripped.startswith(".param")
                or stripped.startswith(".options")
                or stripped.startswith(".subckt")
                or stripped.startswith("*")
                or stripped == ""):
            if stripped.startswith(".include"):
                line = resolve_includes(line, netlist_path)
            body_lines.append(line)
            continue

        # Top-level instance lines: X (subcircuit calls), C (load caps), R (wire resistors)
        if stripped and stripped[0] in ("x", "c", "r"):
            if stripped[0] == "r":
                line = re.sub(r'\s+0\s*$', ' 1m', line)
            body_lines.append(line)
            continue
        # Skip V-source lines from the testbench — we'll build our own below

    return "\n".join(body_lines)


def make_timing_netlist(
    circuit_name: str,
    body: str,
    output_node: str,
    n_b_bits: int,
    n_a_upper: int,
    timing_cfg: dict,
    settle_time: str = SETTLE_TIME,
    meas_time: str = MEAS_TIME,
) -> str:
    """Build a minimal worst-case timing netlist for a FeFET circuit."""
    # Allow per-circuit override of settle/meas times (e.g. HEAA with TG convergence issue)
    settle_time = timing_cfg.get("settle_time", settle_time)
    meas_time   = timing_cfg.get("meas_time",   meas_time)

    settle_ns = float(settle_time.rstrip("n"))
    meas_ns = float(meas_time.rstrip("n"))
    tstop = f"{settle_ns + meas_ns}n"

    a_upper_dc: list[float]  = timing_cfg["a_upper_dc"]
    b_dc:       list[float]  = timing_cfg["b_dc"]
    b_pulse:    list[int]    = timing_cfg["b_pulse"]
    trig_node:  str          = timing_cfg["trig_node"]
    # use_uic: bypass DC op-point; circuit self-settles from 0V during the settle window
    use_uic: bool = timing_cfg.get("settle_time") is not None

    lines = [
        f"* FeFET worst-case timing — {circuit_name}",
        "* Generated by run_fefet_timing.py",
        "",
    ]
    lines.append(body)
    lines.append("")

    # Upper A inputs (Va4..Va7) — DC only (stored lower bits use .param)
    for idx, val in enumerate(a_upper_dc):
        vname = 4 + idx
        lines.append(f"Va{vname} a{vname} 0 dc {val}")

    # B inputs — PULSE for trigger bit(s), DC otherwise
    for i in range(n_b_bits):
        if i in b_pulse:
            lines.append(
                f"Vb{i} b{i} 0 PULSE({b_dc[i]} {VDD} {settle_time} 50p 50p {meas_time} {tstop})"
            )
        else:
            lines.append(f"Vb{i} b{i} 0 dc {b_dc[i]}")

    tran_line = f".tran 10p {tstop}" + (" UIC" if use_uic else "")
    lines += [
        "",
        tran_line,
        "",
        f".measure tran tpd_rise TRIG v({trig_node}) VAL=0.5 RISE=1 "
        f"TARG v({output_node}) VAL=0.5 RISE=1",
        "",
        ".end",
        "",
    ]
    return "\n".join(lines)


def make_power_netlist(
    circuit_name: str,
    body: str,
    n_b_bits: int,
    n_a_upper: int,
    settle_time: str = SETTLE_TIME,
    meas_time: str = MEAS_TIME,
) -> str:
    """Max-switching-activity power netlist.

    FeFET adders: Va4..Va7 all PULSE + all Vb PULSE.
    FeFET BAM  : all Vb PULSE only (no Va sources).
    """
    settle_ns = float(settle_time.rstrip("n"))
    meas_ns = float(meas_time.rstrip("n"))
    tstop = f"{settle_ns + meas_ns}n"

    lines = [
        f"* FeFET max-activity power — {circuit_name}",
        "* Generated by run_fefet_timing.py",
        "",
    ]
    lines.append(body)
    lines.append("")

    # All upper A inputs pulse (when present)
    for idx in range(n_a_upper):
        vname = 4 + idx
        lines.append(
            f"Va{vname} a{vname} 0 PULSE(0 {VDD} {settle_time} 50p 50p {meas_time} {tstop})"
        )

    # All B inputs pulse
    for i in range(n_b_bits):
        lines.append(
            f"Vb{i} b{i} 0 PULSE(0 {VDD} {settle_time} 50p 50p {meas_time} {tstop})"
        )

    lines += [
        "",
        f".tran 10p {tstop}",
        "",
        f".measure tran avg_idd AVG i(Vdd) FROM={settle_time} TO={tstop}",
        "",
        ".end",
        "",
    ]
    return "\n".join(lines)


def run_ngspice_docker(netlist_content: str, label: str) -> str:
    """Write netlist to a temp file inside project dir and run via Docker."""
    tmp_dir = RAW_DIR / "fefet_timing_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_netlist = tmp_dir / f"fefet_timing_{label}.sp"
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

    log_path = tmp_dir / f"fefet_timing_{label}.log"
    log_path.write_text(output)
    print(f"  Log saved: {log_path.relative_to(PROJECT_ROOT)}")
    return output


def parse_measure_output(log: str) -> dict[str, float]:
    """Parse .measure results from ngspice stdout."""
    measures: dict[str, float] = {}
    pattern = re.compile(
        r"^\s*(\w+)\s*=\s*([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)",
        re.MULTILINE | re.IGNORECASE,
    )
    for m in pattern.finditer(log):
        measures[m.group(1).lower()] = float(m.group(2))
    return measures


def compute_metrics(tpd_raw, idd_raw) -> dict[str, float]:
    """Convert raw .measure values to paper-ready metrics."""
    metrics: dict[str, float] = {}

    if tpd_raw is not None and tpd_raw > 0:
        metrics["tpd_ps"] = tpd_raw * 1e12
    else:
        metrics["tpd_ps"] = float("nan")

    if idd_raw is not None:
        metrics["power_uW"] = abs(idd_raw) * VDD * 1e6
    else:
        metrics["power_uW"] = float("nan")

    tpd_ps = metrics["tpd_ps"]
    pwr_uW = metrics["power_uW"]
    if not (math.isnan(tpd_ps) or math.isnan(pwr_uW)):
        metrics["pdp_fJ"] = pwr_uW * tpd_ps * 1e-3
    else:
        metrics["pdp_fJ"] = float("nan")

    return metrics


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    for rel_path, output_node, n_b_bits, n_a_upper, key, timing_cfg in CIRCUITS:
        netlist_path = NETLISTS_DIR / rel_path
        if not netlist_path.exists():
            print(f"[SKIP] {key}: netlist not found at {netlist_path}")
            rows.append({"circuit": key, "tpd_ps": "N/A", "power_uW": "N/A", "pdp_fJ": "N/A"})
            continue

        print(f"\n[{key}] Extracting circuit body...")
        body = extract_circuit_body(netlist_path)

        # --- Timing test ---
        print(f"[{key}] Running worst-case timing test...")
        timing_nl = make_timing_netlist(
            key, body, output_node, n_b_bits, n_a_upper, timing_cfg
        )
        timing_log = run_ngspice_docker(timing_nl, f"{key}_timing")
        timing_m = parse_measure_output(timing_log)

        tpd_raw = timing_m.get("tpd_rise")
        tpd_ps = tpd_raw * 1e12 if (tpd_raw is not None and tpd_raw > 0) else float("nan")
        print(f"  tpd_rise raw = {tpd_raw}  →  tpd = {tpd_ps:.1f} ps")

        # --- Power test ---
        print(f"[{key}] Running max-activity power test...")
        power_nl = make_power_netlist(key, body, n_b_bits, n_a_upper)
        power_log = run_ngspice_docker(power_nl, f"{key}_power")
        power_m = parse_measure_output(power_log)

        idd_raw = power_m.get("avg_idd")
        pwr_uW = abs(idd_raw) * VDD * 1e6 if idd_raw is not None else float("nan")
        print(f"  avg_idd raw = {idd_raw}  →  power = {pwr_uW:.3f} uW")

        metrics = compute_metrics(tpd_raw, idd_raw)
        pdp = metrics.get("pdp_fJ", float("nan"))
        pdp_s = f"{pdp:.4f}" if not math.isnan(pdp) else "N/A"
        print(f"  tpd = {tpd_ps:.1f} ps  power = {pwr_uW:.3f} uW  PDP = {pdp_s} fJ")

        rows.append({"circuit": key, **metrics})

    # Write CSV
    out_csv = PROCESSED_DIR / "fefet_circuit_metrics.csv"
    fieldnames = ["circuit", "tpd_ps", "power_uW", "pdp_fJ"]
    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"\nFeFET circuit metrics saved to: {out_csv}")
    print("\nSummary:")
    print(f"{'Circuit':<25} {'tpd (ps)':>10} {'Power (uW)':>12} {'PDP (fJ)':>10}")
    print("-" * 60)
    for row in rows:
        tpd = row.get("tpd_ps", float("nan"))
        pwr = row.get("power_uW", float("nan"))
        pdp = row.get("pdp_fJ", float("nan"))
        tpd_s = f"{tpd:.1f}"   if isinstance(tpd, float) and not math.isnan(tpd) else "N/A"
        pwr_s = f"{pwr:.3f}"   if isinstance(pwr, float) and not math.isnan(pwr) else "N/A"
        pdp_s = f"{pdp:.4f}"   if isinstance(pdp, float) and not math.isnan(pdp) else "N/A"
        print(f"{row['circuit']:<25} {tpd_s:>10} {pwr_s:>12} {pdp_s:>10}")


if __name__ == "__main__":
    main()
