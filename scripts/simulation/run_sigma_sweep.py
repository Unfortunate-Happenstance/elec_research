#!/usr/bin/env python3
"""
Phase 5 — FeFET σ sweep: Monte Carlo variability analysis.

Sweeps sigma_d2d over 5 values to study how FeFET VT variability affects
the error metrics (NMED) of each approximate circuit. Each sigma point
runs `--iterations` MC iterations per circuit.

σ sweep range: 20 mV → 100 mV in 20 mV steps
σ_c2c = σ_d2d / 2  (consistent with Phase 3 MC baseline, c2c ≈ half of d2d)

Circuits swept:
  mc_fefet_loa8    — 5 FeFET VT params
  mc_fefet_heaa8   — 7 FeFET VT params
  mc_fefet_bam4x4  — 4 FeFET VT params

Results layout:
  results/raw/sigma_sweep/sigma_<XXXX>mV/<circuit>_results.json
    (XXXX = sigma_d2d in mV, zero-padded to 4 digits, e.g. 0020)

Usage:
    uv run python scripts/simulation/run_sigma_sweep.py
    uv run python scripts/simulation/run_sigma_sweep.py --iterations 200
    uv run python scripts/simulation/run_sigma_sweep.py --sigma-values 0.02 0.04 0.06
    uv run python scripts/simulation/run_sigma_sweep.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Import the MC engine from the sibling module
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_monte_carlo import run_monte_carlo  # noqa: E402

SIGMA_SWEEP_DIR = PROJECT_ROOT / "results" / "raw" / "sigma_sweep"

# Default σ_d2d values (V) — 5 points from 20 mV to 100 mV
DEFAULT_SIGMA_D2D_VALUES: list[float] = [0.020, 0.040, 0.060, 0.080, 0.100]

# MC netlist templates → number of FeFET VT params per circuit
CIRCUITS: list[tuple[str, int]] = [
    ("netlists/monte_carlo/mc_fefet_loa8.sp",   5),
    ("netlists/monte_carlo/mc_fefet_heaa8.sp",  7),
    ("netlists/monte_carlo/mc_fefet_bam4x4.sp", 4),
]


def sigma_dir_name(sigma_d2d: float) -> str:
    """Convert σ_d2d value (V) to directory name, e.g. 0.040 → 'sigma_0040mV'."""
    mv = round(sigma_d2d * 1000)
    return f"sigma_{mv:04d}mV"


def already_done(out_path: Path, iterations: int) -> bool:
    """Return True if output JSON exists and has enough successful iterations."""
    if not out_path.exists():
        return False
    import json
    try:
        data = json.loads(out_path.read_text())
        n_success = sum(1 for r in data if r.get("success", False))
        return n_success >= iterations
    except Exception:
        return False


def run_sigma_sweep(
    sigma_d2d_values: list[float],
    iterations: int = 200,
    max_workers: int = 8,
    base_seed: int = 100,
    use_docker: bool = True,
    dry_run: bool = False,
    skip_done: bool = True,
) -> None:
    """Run all sigma sweep simulations.

    For each (sigma, circuit) pair, invokes run_monte_carlo() with the
    appropriate sigma_d2d and sigma_c2c = sigma_d2d / 2.

    Results are saved per-sigma-per-circuit to separate JSON files.

    Args:
        sigma_d2d_values: List of σ_d2d values to sweep (V)
        iterations: MC iterations per (sigma, circuit) point
        max_workers: Parallel ngspice workers per batch
        base_seed: Base random seed; per-point seed = base + sigma_index * 1000
        use_docker: Use Docker for ngspice
        dry_run: Print what would run without actually running
        skip_done: Skip (sigma, circuit) combos whose output already has enough iterations
    """
    total_batches = len(sigma_d2d_values) * len(CIRCUITS)
    total_sims = total_batches * iterations
    print(f"Sigma sweep plan:")
    print(f"  sigma_d2d values : {[f'{s*1000:.0f} mV' for s in sigma_d2d_values]}")
    print(f"  circuits         : {[Path(c).stem for c, _ in CIRCUITS]}")
    print(f"  iterations/batch : {iterations}")
    print(f"  total batches    : {total_batches}")
    print(f"  total sims       : {total_sims}")
    print(f"  workers/batch    : {max_workers}")
    print()

    if dry_run:
        print("[DRY RUN] Would execute the following batches:")
        for si, sigma_d2d in enumerate(sigma_d2d_values):
            sigma_c2c = sigma_d2d / 2.0
            sdir = sigma_dir_name(sigma_d2d)
            for netlist_rel, num_fefets in CIRCUITS:
                stem = Path(netlist_rel).stem
                out_dir = SIGMA_SWEEP_DIR / sdir
                out_file = out_dir / f"mc_results_{stem}.json"
                status = "SKIP (done)" if skip_done and already_done(out_file, iterations) else "RUN"
                print(f"  [{status}] sigma={sigma_d2d*1000:.0f}mV  {stem}  → {out_file.relative_to(PROJECT_ROOT)}")
        return

    completed = 0
    skipped = 0

    for si, sigma_d2d in enumerate(sigma_d2d_values):
        sigma_c2c = sigma_d2d / 2.0
        sdir = sigma_dir_name(sigma_d2d)
        out_dir = SIGMA_SWEEP_DIR / sdir
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'='*60}")
        print(f"σ_d2d = {sigma_d2d*1000:.0f} mV  |  σ_c2c = {sigma_c2c*1000:.0f} mV")
        print(f"{'='*60}")

        for ci, (netlist_rel, num_fefets) in enumerate(CIRCUITS):
            stem = Path(netlist_rel).stem
            out_file = out_dir / f"mc_results_{stem}.json"

            if skip_done and already_done(out_file, iterations):
                print(f"  [SKIP] {stem} — already has ≥{iterations} successful iterations")
                skipped += 1
                continue

            # Unique seed per (sigma, circuit) combination
            point_seed = base_seed + si * 1000 + ci * 100

            print(f"\n  [{ci+1}/{len(CIRCUITS)}] {stem}")
            print(f"    iterations={iterations}  seed={point_seed}  workers={max_workers}")

            netlist_path = PROJECT_ROOT / netlist_rel

            # Temporarily redirect MC output file to sigma-specific directory.
            # run_monte_carlo() saves to results/raw/monte_carlo/ by default,
            # so we copy the result to the sigma directory after completion.
            results = run_monte_carlo(
                netlist_template=str(netlist_path),
                num_fefets=num_fefets,
                iterations=iterations,
                sigma_d2d=sigma_d2d,
                sigma_c2c=sigma_c2c,
                max_workers=max_workers,
                base_seed=point_seed,
                use_docker=use_docker,
                checkpoint_every=50,
            )

            # run_monte_carlo saves to results/raw/monte_carlo/mc_results_<stem>.json
            # Copy to the sigma-sweep directory for organized storage.
            import json, shutil, os
            default_out = PROJECT_ROOT / "results" / "raw" / "monte_carlo" / f"mc_results_{stem}.json"
            if default_out.exists():
                shutil.copy2(default_out, out_file)
                print(f"    Results copied to: {out_file.relative_to(PROJECT_ROOT)}")
            else:
                # Fallback: write results directly
                data_sorted = sorted(results, key=lambda r: r["iteration"])
                tmp = out_file.with_suffix(".json.tmp")
                with open(tmp, "w") as f:
                    json.dump(data_sorted, f, indent=2)
                os.replace(tmp, out_file)
                print(f"    Results written to: {out_file.relative_to(PROJECT_ROOT)}")

            n_success = sum(1 for r in results if r.get("success", False))
            print(f"    Success rate: {n_success}/{iterations}")
            completed += 1

    print(f"\n{'='*60}")
    print(f"Sigma sweep complete.")
    print(f"  Completed: {completed}  Skipped: {skipped}")
    print(f"  Results in: {SIGMA_SWEEP_DIR.relative_to(PROJECT_ROOT)}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Phase 5: FeFET σ sweep Monte Carlo simulation"
    )
    parser.add_argument(
        "--sigma-values", type=float, nargs="+",
        default=DEFAULT_SIGMA_D2D_VALUES,
        metavar="V",
        help="σ_d2d values to sweep (V). Default: 0.02 0.04 0.06 0.08 0.10",
    )
    parser.add_argument(
        "--iterations", type=int, default=200,
        help="MC iterations per (sigma, circuit) point (default: 200)",
    )
    parser.add_argument(
        "--workers", type=int, default=8,
        help="Parallel ngspice workers per batch (default: 8)",
    )
    parser.add_argument(
        "--seed", type=int, default=100,
        help="Base random seed (default: 100)",
    )
    parser.add_argument(
        "--native", action="store_true",
        help="Use native ngspice instead of Docker",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would run without executing",
    )
    parser.add_argument(
        "--no-skip", action="store_true",
        help="Re-run even if output files already exist",
    )
    args = parser.parse_args()

    run_sigma_sweep(
        sigma_d2d_values=sorted(args.sigma_values),
        iterations=args.iterations,
        max_workers=args.workers,
        base_seed=args.seed,
        use_docker=not args.native,
        dry_run=args.dry_run,
        skip_done=not args.no_skip,
    )
