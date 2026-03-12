#!/usr/bin/env python3
"""Run a single ngspice simulation via Docker and parse output."""

import subprocess
import re
import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DOCKER_CONTAINER = "ngspice-sim"


def run_ngspice(netlist_path: str, output_dir: str | None = None) -> dict:
    """Run ngspice in batch mode inside Docker container.

    Args:
        netlist_path: Path to .sp file (relative to project root)
        output_dir: Directory for output files (relative to project root)

    Returns:
        dict with 'returncode', 'stdout', 'stderr', 'measures'
    """
    # Convert to workspace-relative path for Docker
    workspace_path = f"/workspace/{netlist_path}"

    cmd = [
        "docker", "exec", DOCKER_CONTAINER,
        "ngspice", "-b", workspace_path,
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(PROJECT_ROOT),
    )

    measures = parse_measures(result.stdout + result.stderr)

    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "measures": measures,
    }


def run_ngspice_native(netlist_path: str) -> dict:
    """Run ngspice natively (fallback if Docker unavailable)."""
    abs_path = PROJECT_ROOT / netlist_path

    cmd = ["ngspice", "-b", str(abs_path)]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(PROJECT_ROOT),
    )

    measures = parse_measures(result.stdout + result.stderr)

    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "measures": measures,
    }


def parse_measures(output: str) -> dict:
    """Extract .measure results from ngspice output.

    ngspice prints measurements as:
        measure_name = value
    or:
        measure_name = value from=... to=...
    """
    measures = {}
    pattern = re.compile(
        r"^\s*(\w+)\s*=\s*([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)",
        re.MULTILINE,
    )
    for match in pattern.finditer(output):
        name = match.group(1)
        value = float(match.group(2))
        measures[name] = value
    return measures


def parse_csv_output(csv_path: str) -> list[dict]:
    """Parse ngspice wrdata CSV output."""
    rows = []
    with open(csv_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("*"):
                continue
            parts = line.split()
            rows.append([float(x) for x in parts])
    return rows


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: run_single.py <netlist.sp> [--native]")
        sys.exit(1)

    netlist = sys.argv[1]
    native = "--native" in sys.argv

    if native:
        result = run_ngspice_native(netlist)
    else:
        result = run_ngspice(netlist)

    print(f"Return code: {result['returncode']}")
    if result["measures"]:
        print("Measurements:")
        for k, v in result["measures"].items():
            print(f"  {k} = {v:.6e}")
    if result["returncode"] != 0:
        print("STDERR:", result["stderr"][-500:] if result["stderr"] else "")
