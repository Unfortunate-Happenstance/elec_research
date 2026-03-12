#!/usr/bin/env python3
"""Monte Carlo variability simulation for FeFET circuits.

Orchestrates N iterations of ngspice simulations with randomized
VT offsets for each FeFET device, then aggregates statistics.
"""

import argparse
import json
import os
import re
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np


def _parse_measures(output: str) -> dict:
    """Extract .measure results from ngspice stdout/stderr.

    Filters to keys ending in '_val' only, which is the naming convention
    used in all MC netlists (e.g. s0_val, cout_val, p3_val).  This avoids
    false positives from ngspice internal lines such as 'TEMP = 27.0' and
    'TNOM = 27.0', which would otherwise make the empty-measures guard
    unreliable.
    """
    measures = {}
    pattern = re.compile(
        r"^\s*(\w+_val)\s*=\s*([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)",
        re.MULTILINE,
    )
    for match in pattern.finditer(output):
        measures[match.group(1)] = float(match.group(2))
    return measures

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MC_PARAM_DIR = PROJECT_ROOT / "netlists" / "monte_carlo" / "params"
MC_RESULTS_DIR = PROJECT_ROOT / "results" / "raw" / "monte_carlo"

# Circuit-specific VT offset parameter names, matched to each netlist's .param block
CIRCUIT_VT_PARAMS: dict[str, list[str]] = {
    "mc_fefet_loa8": [
        "vt_offset_0", "vt_offset_1", "vt_offset_2", "vt_offset_3",
        "vt_offset_and3",
    ],
    "mc_fefet_heaa8": [
        "vt_offset_0", "vt_offset_1", "vt_offset_2", "vt_offset_3",
        "vt_offset_and2", "vt_offset_and3", "vt_offset_xor3",
    ],
    "mc_fefet_bam4x4": [
        "vt_offset_a0", "vt_offset_a1", "vt_offset_a2", "vt_offset_a3",
    ],
}

# Nominal VT offsets per FeFET — the base around which D2D/C2C variability is added.
#
# FeFET states:
#   LVT (stored "1"): vt_offset ≈ 0.12 V  →  gate_shifted = VDD − 0.12 = 0.88 V >> VTN  →  ON
#   HVT (stored "0"): vt_offset ≈ 1.20 V  →  gate_shifted = VDD − 1.20 = −0.20 V < VTN  →  OFF
#
# Operand A stored in FeFETs uses pattern A_lower = 0b1010 (a3=1, a2=0, a1=1, a0=0).
# This gives a realistic mixed-state circuit: half the FeFETs are LVT, half HVT.
# Variability-induced bit flips require ≫σ deviation from nominal, becoming probable
# only in the sigma-sweep regime (σ > ~200 mV), which is exactly where the
# "variability-as-approximation" comparison between exact and approximate circuits
# is scientifically interesting.
VT_LVT_NOMINAL = 0.12   # V — low-VT state (stored "1")
VT_HVT_NOMINAL = 1.20   # V — high-VT state (stored "0")

CIRCUIT_VT_NOMINALS: dict[str, list[float]] = {
    # LOA8  — A_lower = 0b1010: a0=0(HVT), a1=1(LVT), a2=0(HVT), a3=1(LVT), and3→a3=1(LVT)
    "mc_fefet_loa8": [VT_HVT_NOMINAL, VT_LVT_NOMINAL, VT_HVT_NOMINAL,
                      VT_LVT_NOMINAL, VT_LVT_NOMINAL],
    # HEAA8 — A_lower = 0b1010: same pattern; and2→a2=0(HVT), and3→a3=1(LVT), xor3→a3=1(LVT)
    "mc_fefet_heaa8": [VT_HVT_NOMINAL, VT_LVT_NOMINAL, VT_HVT_NOMINAL,
                       VT_LVT_NOMINAL, VT_HVT_NOMINAL, VT_LVT_NOMINAL, VT_LVT_NOMINAL],
    # BAM4x4 — A = 0b1010 = 10: a0=0(HVT), a1=1(LVT), a2=0(HVT), a3=1(LVT)
    "mc_fefet_bam4x4": [VT_HVT_NOMINAL, VT_LVT_NOMINAL,
                        VT_HVT_NOMINAL, VT_LVT_NOMINAL],
}


def generate_vt_offsets(
    num_fefets: int,
    sigma_d2d: float = 0.040,
    sigma_c2c: float = 0.020,
    seed: int | None = None,
) -> np.ndarray:
    """Generate VT offsets combining D2D and C2C variability.

    Args:
        num_fefets: Number of FeFET devices in circuit
        sigma_d2d: Device-to-device VT std dev (V)
        sigma_c2c: Cycle-to-cycle VT std dev (V)
        seed: Random seed for reproducibility

    Returns:
        Array of VT offsets (V) for each FeFET
    """
    rng = np.random.default_rng(seed)
    d2d = rng.normal(0, sigma_d2d, num_fefets)
    c2c = rng.normal(0, sigma_c2c, num_fefets)
    return d2d + c2c


def write_mc_param_file(
    iteration: int,
    vt_offsets: np.ndarray,
    output_dir: Path,
) -> Path:
    """Write ngspice parameter file with VT offsets for one MC iteration.

    The offsets are injected as voltage sources in series with FeFET gates.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    param_file = output_dir / f"mc_params_{iteration:04d}.inc"

    lines = [
        f"* Monte Carlo iteration {iteration}",
        f"* Generated VT offsets (D2D + C2C)",
    ]
    for i, offset in enumerate(vt_offsets):
        # Each FeFET gate has a series voltage source for VT shift
        lines.append(f".param vt_offset_{i} = {offset:.6e}")

    param_file.write_text("\n".join(lines) + "\n")
    return param_file


def run_single_mc_iteration(args: tuple) -> dict:
    """Run one MC iteration. Designed for ProcessPoolExecutor.

    Generates a per-iteration netlist copy with randomized VT offset
    .param lines injected before the .control block, then runs ngspice
    on that temp file. Temp file is written to the same directory as
    the template so relative .include paths resolve correctly.

    Args:
        args: (iteration, netlist_template, num_fefets, sigma_d2d, sigma_c2c,
               base_seed, use_docker)

    Returns:
        dict with iteration number, VT offsets, and simulation results
    """
    (iteration, netlist_template, num_fefets, sigma_d2d, sigma_c2c,
     base_seed, use_docker) = args

    seed = base_seed + iteration
    # Resolve to absolute so relative_to(PROJECT_ROOT) works regardless of cwd
    template_path = Path(netlist_template)
    if not template_path.is_absolute():
        template_path = (PROJECT_ROOT / template_path).resolve()
    circuit_stem = template_path.stem

    # Use circuit-specific param names if known, else fall back to generic
    param_names = CIRCUIT_VT_PARAMS.get(
        circuit_stem,
        [f"vt_offset_{i}" for i in range(num_fefets)],
    )

    # Nominal VT offset per FeFET (LVT=stored-1, HVT=stored-0).
    # Random D2D+C2C variability is added ON TOP of the nominal so that
    # the injection actually perturbs devices around their operating state.
    nominals = np.array(
        CIRCUIT_VT_NOMINALS.get(circuit_stem, [VT_LVT_NOMINAL] * len(param_names))
    )
    random_offsets = generate_vt_offsets(len(param_names), sigma_d2d, sigma_c2c, seed)
    vt_offsets = nominals + random_offsets

    # Build injected .param block — placed immediately before .control so it
    # overrides the netlist defaults (ngspice last-definition-wins).
    injected_lines = [
        f"* MC iter {iteration} — nominal + D2D/C2C variability (sigma_d2d={sigma_d2d:.4f})",
    ]
    for name, nom, rand, total in zip(param_names, nominals, random_offsets, vt_offsets):
        injected_lines.append(
            f".param {name} = {total:.6e}  $ nominal={nom:.4f} rand={rand:+.4f}"
        )
    injected_lines.append(f".param mc_iteration = {iteration}")
    injected_block = "\n".join(injected_lines)

    # Generate per-iteration netlist in the SAME directory as the template
    # so all relative .include paths (supply.inc, model files) still resolve.
    template_text = template_path.read_text()
    # Use a line-anchored regex so we match the actual ^.control directive,
    # not occurrences of ".control" inside comment lines (e.g. "before .control.").
    _ctrl_re = re.compile(r"(?m)^\.control\b")
    if not _ctrl_re.search(template_text):
        raise RuntimeError(
            f"[iter {iteration}] Template '{template_path}' contains no .control block — "
            "cannot inject .param lines."
        )
    modified = _ctrl_re.sub(f"{injected_block}\n\n.control", template_text, count=1)
    temp_netlist = template_path.parent / f"_iter{iteration:04d}_{circuit_stem}.sp"
    temp_netlist.write_text(modified)

    # Run ngspice on the per-iteration netlist
    if use_docker:
        rel_path = temp_netlist.relative_to(PROJECT_ROOT)
        cmd = [
            "docker", "exec", "ngspice-sim",
            "ngspice", "-b", f"/workspace/{rel_path}",
        ]
    else:
        cmd = ["ngspice", "-b", str(temp_netlist)]

    env = {**os.environ, "MC_ITERATION": str(iteration)}
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(PROJECT_ROOT),
            env=env,
        )
    except subprocess.TimeoutExpired:
        temp_netlist.unlink()
        raise RuntimeError(f"[iter {iteration}] ngspice timed out after 60 s") from None

    temp_netlist.unlink()  # clean up; let OSError propagate if it fails

    if result.returncode != 0:
        raise RuntimeError(
            f"[iter {iteration}] ngspice exited rc={result.returncode}.\n"
            f"--- stderr (last 600 chars) ---\n"
            f"{(result.stderr or result.stdout)[-600:]}"
        )

    measures = _parse_measures(result.stdout + result.stderr)
    if not measures:
        raise RuntimeError(
            f"[iter {iteration}] ngspice returned rc=0 but produced no .measure results.\n"
            f"--- stdout tail ---\n{result.stdout[-600:]}"
        )

    return {
        "iteration": iteration,
        "seed": seed,
        "vt_offsets": vt_offsets.tolist(),
        "vt_nominals": nominals.tolist(),
        "vt_param_names": param_names,
        "success": True,
        "measures": measures,
    }


def _atomic_json_write(path: Path, data: list[dict]) -> None:
    """Write JSON atomically via a temp file to avoid partial-write corruption.

    Sorts data by iteration number before writing.
    """
    data_sorted = sorted(data, key=lambda r: r["iteration"])
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(data_sorted, f, indent=2)
    os.replace(tmp, path)  # atomic on POSIX; overwrites destination


def run_monte_carlo(
    netlist_template: str,
    num_fefets: int,
    iterations: int = 1000,
    sigma_d2d: float = 0.040,
    sigma_c2c: float = 0.020,
    max_workers: int = 8,
    base_seed: int = 42,
    use_docker: bool = True,
    checkpoint_every: int = 50,
) -> list[dict]:
    """Run full Monte Carlo campaign.

    Args:
        netlist_template: Path to netlist template (includes MC params)
        num_fefets: Number of FeFET devices
        iterations: Number of MC iterations
        sigma_d2d: D2D VT std dev (V)
        sigma_c2c: C2C VT std dev (V)
        max_workers: Parallel workers
        base_seed: Base random seed
        use_docker: Use Docker for ngspice
        checkpoint_every: Save partial results to JSON every N completions.
                          Protects against data loss if the process is killed.
                          Use 0 to disable mid-run checkpoints.

    Returns:
        List of result dicts, one per iteration
    """
    MC_PARAM_DIR.mkdir(parents=True, exist_ok=True)
    MC_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # Resolve output path before the loop so checkpoints and final save
    # all go to the same file.
    output_file = MC_RESULTS_DIR / f"mc_results_{Path(netlist_template).stem}.json"

    # Prepare arguments for each iteration
    args_list = [
        (i, netlist_template, num_fefets, sigma_d2d, sigma_c2c,
         base_seed, use_docker)
        for i in range(iterations)
    ]

    results = []
    t0 = time.time()

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(run_single_mc_iteration, args): args[0]
            for args in args_list
        }

        for i, future in enumerate(as_completed(futures)):
            iter_num = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                # Print the full error immediately — no silent swallowing.
                print(f"\n  [FAIL iter {iter_num}] {type(exc).__name__}: {exc}\n", flush=True)
                result = {
                    "iteration": iter_num,
                    "success": False,
                    "error": str(exc),
                    "measures": {},
                    "vt_offsets": [],
                    "vt_nominals": [],
                }
            results.append(result)

            completed = i + 1
            n_success = sum(r["success"] for r in results)
            elapsed = time.time() - t0
            rate = completed / elapsed
            eta = (iterations - completed) / rate if rate > 0 else 0

            # Progress print: first completion, then every 100
            if completed % 100 == 0 or i == 0:
                print(
                    f"  [{completed}/{iterations}] "
                    f"elapsed={elapsed:.1f}s rate={rate:.1f}/s "
                    f"ETA={eta:.0f}s "
                    f"success={n_success}/{completed}"
                )

            # Checkpoint save: every N completions (and on the first result
            # so the file exists immediately and can be monitored externally)
            if checkpoint_every > 0 and (completed % checkpoint_every == 0 or i == 0):
                _atomic_json_write(output_file, results)
                print(
                    f"  [checkpoint] {completed}/{iterations} results "
                    f"saved → {output_file.name}"
                )

    # Final save (guaranteed to include every result, sorted)
    _atomic_json_write(output_file, results)

    elapsed = time.time() - t0
    n_success = sum(r["success"] for r in results)
    print(f"\nMonte Carlo complete: {n_success}/{iterations} succeeded in {elapsed:.1f}s")
    print(f"Results saved to: {output_file}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FeFET Monte Carlo simulation")
    parser.add_argument("--circuit", required=True, help="Netlist template path")
    parser.add_argument("--num-fefets", type=int, required=True,
                        help="Number of FeFET devices")
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--sigma-d2d", type=float, default=0.040)
    parser.add_argument("--sigma-c2c", type=float, default=0.020)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--native", action="store_true",
                        help="Use native ngspice instead of Docker")
    parser.add_argument("--checkpoint-every", type=int, default=50,
                        help="Save partial results every N completions (0 = disable)")
    args = parser.parse_args()

    results = run_monte_carlo(
        netlist_template=args.circuit,
        num_fefets=args.num_fefets,
        iterations=args.iterations,
        sigma_d2d=args.sigma_d2d,
        sigma_c2c=args.sigma_c2c,
        max_workers=args.workers,
        base_seed=args.seed,
        use_docker=not args.native,
        checkpoint_every=args.checkpoint_every,
    )
