#!/usr/bin/env python3
"""Phase 4a: Run HERACLES FeCap/FeFET characterization simulations.

Executes three netlists in sequence via Docker/ngspice:
  1. heracles_pv.sp  — P-V hysteresis loop (50 kHz triangular wave, ±5 V)
  2. fefet_iv_lvt.sp — Id-Vgs in LVT state (write -5V, then sweep Vgs)
  3. fefet_iv_hvt.sp — Id-Vgs in HVT state (write +5V, then sweep Vgs)

All outputs are saved to results/raw/fefet/ as CSV files.

Usage (from elec_research root):
    uv run python scripts/simulation/run_fefet_char.py
    uv run python scripts/simulation/run_fefet_char.py --native  # use system ngspice
    uv run python scripts/simulation/run_fefet_char.py --sim pv  # only run P-V
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CHAR_DIR = PROJECT_ROOT / "netlists" / "fefet" / "char"
RESULTS_DIR = PROJECT_ROOT / "results" / "raw" / "fefet"

NETLISTS = {
    "pv":  CHAR_DIR / "heracles_pv.sp",
    "lvt": CHAR_DIR / "fefet_iv_lvt.sp",
    "hvt": CHAR_DIR / "fefet_iv_hvt.sp",
}

EXPECTED_OUTPUTS = {
    "pv":  RESULTS_DIR / "heracles_pv.csv",
    "lvt": RESULTS_DIR / "fefet_iv_lvt.csv",
    "hvt": RESULTS_DIR / "fefet_iv_hvt.csv",
}

# Expected simulation times (approximate, for progress display)
SIM_TIMES = {
    "pv":  "~60 µs transient (60 s wall-clock)",
    "lvt": "~20.7 µs transient (45 s wall-clock)",
    "hvt": "~20.7 µs transient (45 s wall-clock)",
}


def run_ngspice(netlist: Path, use_docker: bool = True) -> tuple[bool, str]:
    """Run one ngspice simulation. Returns (success, output_text)."""
    if use_docker:
        rel = netlist.relative_to(PROJECT_ROOT)
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{PROJECT_ROOT}:/workspace",
            "docker-ngspice:latest",
            "ngspice", "-b", f"/workspace/{rel}",
        ]
    else:
        cmd = ["ngspice", "-b", str(netlist)]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min max per sim
            cwd=str(PROJECT_ROOT),
        )
    except subprocess.TimeoutExpired:
        return False, "ngspice timed out after 300 s"
    except FileNotFoundError as e:
        return False, f"Command not found: {e}"

    combined = result.stdout + result.stderr
    if result.returncode != 0:
        # ngspice returns non-zero even on success sometimes; check for output file
        return False, combined
    return True, combined


def validate_output(sim_name: str, output_text: str) -> bool:
    """Check that the expected CSV file was created and has data."""
    out_file = EXPECTED_OUTPUTS[sim_name]
    if not out_file.exists():
        print(f"  [FAIL] Output file not found: {out_file}")
        return False

    size = out_file.stat().st_size
    if size < 1000:
        print(f"  [WARN] Output file suspiciously small ({size} bytes): {out_file}")
        return False

    # Count rows (header + data)
    with open(out_file) as f:
        lines = [l for l in f if l.strip() and not l.startswith("#")]
    print(f"  [OK] {out_file.name}  {size/1024:.1f} KB  {len(lines)} rows")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Run HERACLES FeFET characterization")
    parser.add_argument(
        "--sim", choices=["pv", "lvt", "hvt", "all"], default="all",
        help="Which simulation to run (default: all)",
    )
    parser.add_argument(
        "--native", action="store_true",
        help="Use native ngspice instead of Docker",
    )
    args = parser.parse_args()

    use_docker = not args.native
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    sims = list(NETLISTS.keys()) if args.sim == "all" else [args.sim]

    print("=" * 60)
    print("Phase 4a: HERACLES FeFET Characterization")
    print(f"Backend: {'Docker (docker-ngspice:latest)' if use_docker else 'native ngspice'}")
    print("=" * 60)

    all_passed = True
    for sim in sims:
        netlist = NETLISTS[sim]
        print(f"\n[{sim.upper()}] {netlist.name}")
        print(f"  Expected time: {SIM_TIMES[sim]}")
        print(f"  Running...", flush=True)

        t0 = time.time()
        ok, output = run_ngspice(netlist, use_docker)
        elapsed = time.time() - t0

        # ngspice often returns rc=1 even on success (e.g. "warning" messages).
        # Re-check by looking for output file rather than relying on rc.
        file_ok = validate_output(sim, output)
        success = file_ok  # file existence is the real pass criterion

        if not success:
            print(f"  [FAIL] Simulation failed after {elapsed:.1f}s")
            print(f"  ngspice OK flag: {ok}")
            # Print last 20 lines of output for diagnosis
            tail = "\n".join(output.splitlines()[-20:])
            print(f"  --- ngspice output (tail) ---\n{tail}")
            all_passed = False
        else:
            print(f"  [PASS] Completed in {elapsed:.1f}s")

    print("\n" + "=" * 60)
    if all_passed:
        print("All characterization simulations PASSED.")
        print("Next step: uv run python scripts/analysis/plot_fefet_char.py")
    else:
        print("One or more simulations FAILED — see output above.")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
