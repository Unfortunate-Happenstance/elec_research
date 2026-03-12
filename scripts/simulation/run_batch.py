#!/usr/bin/env python3
"""Run exhaustive input sweep for truth table generation via ngspice.

Generates all input combinations for a given circuit (2^16 for 8-bit adder,
2^8 for 4-bit multiplier), creates SPICE stimulus files, runs ngspice in
parallel, collects outputs, and builds a truth table CSV.
"""

import argparse
import csv
import subprocess
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
NETLISTS_DIR = PROJECT_ROOT / "netlists"
RESULTS_DIR = PROJECT_ROOT / "results" / "raw"
DOCKER_CONTAINER = "ngspice-sim"


def generate_input_combinations(
    circuit_type: str,
    n_bits: int,
) -> list[tuple[int, int]]:
    """Generate all input pairs for exhaustive truth table.

    Args:
        circuit_type: 'adder' or 'multiplier'
        n_bits: Operand bit width

    Returns:
        List of (a, b) integer pairs
    """
    max_val = 1 << n_bits
    combinations = []
    for a in range(max_val):
        for b in range(max_val):
            combinations.append((a, b))
    return combinations


def create_pwl_stimulus(
    a_val: int,
    b_val: int,
    n_bits: int,
    vdd: float = 1.0,
    period: float = 10e-9,
    rise_time: float = 50e-12,
) -> str:
    """Create PWL voltage source lines for a single input vector.

    Each bit of a and b gets its own PWL voltage source, held constant
    for the measurement window.

    Args:
        a_val: Integer value for operand A
        b_val: Integer value for operand B
        n_bits: Bit width of each operand
        vdd: Supply voltage
        period: Settling period
        rise_time: Rise/fall time for transitions

    Returns:
        String of SPICE voltage source definitions
    """
    lines = []
    for i in range(n_bits):
        bit_a = (a_val >> i) & 1
        v_a = vdd if bit_a else 0.0
        lines.append(f"Va{i} a{i} 0 DC {v_a:.4f}")

    for i in range(n_bits):
        bit_b = (b_val >> i) & 1
        v_b = vdd if bit_b else 0.0
        lines.append(f"Vb{i} b{i} 0 DC {v_b:.4f}")

    return "\n".join(lines)


def create_batch_pwl_stimulus(
    combinations: list[tuple[int, int]],
    n_bits: int,
    vdd: float = 1.0,
    period: float = 10e-9,
    rise_time: float = 50e-12,
) -> str:
    """Create a single long PWL stimulus covering all input combinations.

    Each combination is held for one period. PWL transitions sweep
    through all vectors sequentially.

    Args:
        combinations: List of (a, b) input pairs
        n_bits: Bit width of each operand
        vdd: Supply voltage
        period: Time per vector
        rise_time: Rise/fall time

    Returns:
        String of SPICE PWL voltage sources
    """
    lines = []
    num_vectors = len(combinations)

    for bit_idx in range(n_bits):
        # Build PWL for a[bit_idx]
        pwl_points_a = []
        pwl_points_b = []
        for vec_idx, (a_val, b_val) in enumerate(combinations):
            t_start = vec_idx * period
            t_settled = t_start + rise_time
            v_a = vdd if ((a_val >> bit_idx) & 1) else 0.0
            v_b = vdd if ((b_val >> bit_idx) & 1) else 0.0
            pwl_points_a.append(f"{t_start:.6e} {v_a:.4f}")
            if vec_idx < num_vectors - 1:
                t_end = (vec_idx + 1) * period - rise_time
                pwl_points_a.append(f"{t_end:.4e} {v_a:.4f}")
            pwl_points_b.append(f"{t_start:.6e} {v_b:.4f}")
            if vec_idx < num_vectors - 1:
                t_end = (vec_idx + 1) * period - rise_time
                pwl_points_b.append(f"{t_end:.4e} {v_b:.4f}")

        pwl_str_a = " ".join(pwl_points_a)
        pwl_str_b = " ".join(pwl_points_b)
        lines.append(f"Va{bit_idx} a{bit_idx} 0 PWL({pwl_str_a})")
        lines.append(f"Vb{bit_idx} b{bit_idx} 0 PWL({pwl_str_b})")

    return "\n".join(lines)


def create_single_vector_netlist(
    template_path: Path,
    a_val: int,
    b_val: int,
    n_bits: int,
    output_file: Path,
    vdd: float = 1.0,
) -> Path:
    """Create a complete netlist for a single input vector.

    Reads the circuit template and appends stimulus, analysis, and
    measurement commands.

    Args:
        template_path: Path to base circuit netlist (subcircuit definition)
        a_val: Operand A value
        b_val: Operand B value
        n_bits: Bit width
        output_file: Path for wrdata output
        vdd: Supply voltage

    Returns:
        Path to generated netlist
    """
    stimulus = create_pwl_stimulus(a_val, b_val, n_bits, vdd=vdd)

    template_text = template_path.read_text()

    # Determine number of output bits
    n_out = n_bits + 1  # adder: n+1 bits
    output_nodes = " ".join([f"v(s{i})" for i in range(n_out)])

    netlist = f"""* Auto-generated batch vector: A={a_val} B={b_val}
{template_text}

* --- Stimulus ---
{stimulus}

* --- Analysis ---
.tran 10p 20n

.control
run
let settle_time = 15n
wrdata {output_file} {output_nodes}
.endc

.end
"""
    netlist_path = output_file.parent / f"vec_a{a_val}_b{b_val}.sp"
    netlist_path.write_text(netlist)
    return netlist_path


def run_single_vector(args: tuple) -> dict:
    """Run ngspice for a single input vector. Designed for ProcessPoolExecutor.

    Args:
        args: (a_val, b_val, n_bits, template_path, work_dir, use_docker, vdd)

    Returns:
        dict with a, b, output_bits, success
    """
    a_val, b_val, n_bits, template_path, work_dir, use_docker, vdd = args
    n_out = n_bits + 1  # adder output bits

    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    output_csv = work_dir / f"out_a{a_val}_b{b_val}.csv"

    # Create netlist
    netlist_path = create_single_vector_netlist(
        Path(template_path), a_val, b_val, n_bits, output_csv, vdd=vdd,
    )

    # Run ngspice
    try:
        if use_docker:
            rel_path = netlist_path.relative_to(PROJECT_ROOT)
            cmd = [
                "docker", "exec", DOCKER_CONTAINER,
                "ngspice", "-b", f"/workspace/{rel_path}",
            ]
        else:
            cmd = ["ngspice", "-b", str(netlist_path)]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(PROJECT_ROOT),
        )

        if result.returncode != 0:
            return {
                "a": a_val, "b": b_val, "output": None,
                "success": False, "error": result.stderr[:200],
            }

        # Parse output CSV — extract final settled values
        output_bits = parse_wrdata_digital(output_csv, n_out, vdd)

        return {
            "a": a_val, "b": b_val, "output": output_bits,
            "success": True, "error": None,
        }

    except subprocess.TimeoutExpired:
        return {
            "a": a_val, "b": b_val, "output": None,
            "success": False, "error": "timeout",
        }
    except Exception as e:
        return {
            "a": a_val, "b": b_val, "output": None,
            "success": False, "error": str(e),
        }


def parse_wrdata_digital(
    csv_path: Path,
    n_signals: int,
    vdd: float = 1.0,
) -> int | None:
    """Parse ngspice wrdata output and convert to digital value.

    Reads the last row (settled state), applies VDD/2 threshold to
    each signal column, and assembles the integer output.

    Args:
        csv_path: Path to wrdata output file
        n_signals: Number of output signals
        vdd: Supply voltage for threshold computation

    Returns:
        Integer value assembled from output bits, or None on parse error
    """
    threshold = vdd / 2.0

    try:
        rows = []
        with open(csv_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("*"):
                    continue
                parts = line.split()
                if len(parts) >= n_signals + 1:  # time + signals
                    rows.append([float(x) for x in parts])

        if not rows:
            return None

        # Use last row (fully settled)
        last_row = rows[-1]
        # Columns: time, v(s0), v(s1), ...
        digital_value = 0
        for i in range(n_signals):
            voltage = last_row[1 + i]  # skip time column
            if voltage > threshold:
                digital_value |= (1 << i)

        return digital_value

    except (OSError, ValueError, IndexError):
        return None


def run_batch_sweep(
    template_path: str,
    circuit_type: str = "adder",
    n_bits: int = 8,
    max_workers: int = 8,
    use_docker: bool = True,
    vdd: float = 1.0,
    output_csv: str | None = None,
) -> Path:
    """Run exhaustive truth table sweep.

    Args:
        template_path: Path to circuit netlist template
        circuit_type: 'adder' or 'multiplier'
        n_bits: Operand bit width
        max_workers: Number of parallel ngspice processes
        use_docker: Use Docker for ngspice execution
        vdd: Supply voltage
        output_csv: Path for output truth table CSV

    Returns:
        Path to generated truth table CSV
    """
    combinations = generate_input_combinations(circuit_type, n_bits)
    total = len(combinations)
    print(f"Batch sweep: {circuit_type} {n_bits}-bit, {total} vectors, "
          f"{max_workers} workers")

    # Working directory for temporary netlists
    circuit_name = Path(template_path).stem
    work_dir = RESULTS_DIR / "batch" / circuit_name
    work_dir.mkdir(parents=True, exist_ok=True)

    # Prepare arguments
    args_list = [
        (a, b, n_bits, template_path, str(work_dir), use_docker, vdd)
        for a, b in combinations
    ]

    results = []
    t0 = time.time()

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(run_single_vector, args): (args[0], args[1])
            for args in args_list
        }

        for i, future in enumerate(as_completed(futures)):
            result = future.result()
            results.append(result)

            if (i + 1) % 1000 == 0 or (i + 1) == total:
                elapsed = time.time() - t0
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                n_ok = sum(1 for r in results if r["success"])
                print(f"  [{i+1}/{total}] elapsed={elapsed:.1f}s "
                      f"rate={rate:.1f}/s success={n_ok}/{i+1}")

    # Sort by (a, b)
    results.sort(key=lambda r: (r["a"], r["b"]))

    # Write truth table CSV
    if output_csv is None:
        output_csv = RESULTS_DIR / "batch" / f"{circuit_name}_truth_table.csv"
    else:
        output_csv = Path(output_csv)

    output_csv.parent.mkdir(parents=True, exist_ok=True)

    n_out = n_bits + 1 if circuit_type == "adder" else 2 * n_bits

    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["a", "b", "output", "success"])
        for r in results:
            out_val = r["output"] if r["output"] is not None else ""
            writer.writerow([r["a"], r["b"], out_val, r["success"]])

    elapsed = time.time() - t0
    n_ok = sum(1 for r in results if r["success"])
    n_fail = total - n_ok
    print(f"\nBatch complete: {n_ok}/{total} succeeded, "
          f"{n_fail} failed, {elapsed:.1f}s total")
    print(f"Truth table saved to: {output_csv}")

    return output_csv


def build_python_truth_table(
    circuit_type: str = "adder",
    n_bits: int = 8,
    approx_func=None,
    approx_kwargs: dict | None = None,
    output_csv: str | None = None,
) -> Path:
    """Build truth table using Python approximate arithmetic models.

    This is a fast alternative to SPICE simulation for functional
    verification. Uses the approximate adder/multiplier functions from
    compute_error_metrics.py.

    Args:
        circuit_type: 'adder' or 'multiplier'
        n_bits: Operand bit width
        approx_func: Approximate function (e.g., loa_adder)
        approx_kwargs: Additional kwargs for the function
        output_csv: Output path

    Returns:
        Path to generated truth table CSV
    """
    import sys
    sys.path.insert(0, str(PROJECT_ROOT))
    from scripts.analysis.compute_error_metrics import (
        exact_adder_truth_table,
        exact_multiplier_truth_table,
    )

    if circuit_type == "adder":
        a, b, exact = exact_adder_truth_table(n_bits)
        n_out = n_bits + 1
    else:
        a, b, exact = exact_multiplier_truth_table(n_bits)
        n_out = 2 * n_bits

    if approx_func is not None:
        kwargs = approx_kwargs or {}
        approx = approx_func(a, b, n_bits=n_bits, **kwargs)
    else:
        approx = exact.copy()

    # Save CSV
    if output_csv is None:
        func_name = approx_func.__name__ if approx_func else "exact"
        output_csv = (
            RESULTS_DIR / "batch"
            / f"{func_name}_{n_bits}bit_truth_table.csv"
        )
    else:
        output_csv = Path(output_csv)

    output_csv.parent.mkdir(parents=True, exist_ok=True)

    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["a", "b", "exact", "approx"])
        for i in range(len(a)):
            writer.writerow([int(a[i]), int(b[i]), int(exact[i]), int(approx[i])])

    print(f"Python truth table ({len(a)} vectors) saved to: {output_csv}")
    return output_csv


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Exhaustive truth table generation via ngspice batch sweep"
    )
    parser.add_argument(
        "--template", type=str,
        help="Path to circuit netlist template",
    )
    parser.add_argument(
        "--circuit-type", choices=["adder", "multiplier"],
        default="adder",
    )
    parser.add_argument("--n-bits", type=int, default=8)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--native", action="store_true",
                        help="Use native ngspice instead of Docker")
    parser.add_argument("--vdd", type=float, default=1.0)
    parser.add_argument("--output", type=str, default=None,
                        help="Output CSV path")
    parser.add_argument("--python-only", action="store_true",
                        help="Use Python models instead of SPICE")
    parser.add_argument("--approx", type=str, default=None,
                        choices=["loa", "heaa", "ama5", "bam"],
                        help="Approximate circuit to simulate (Python mode)")
    parser.add_argument("-k", type=int, default=4,
                        help="Approximation parameter k (or v for BAM)")

    args = parser.parse_args()

    if args.python_only:
        # Use Python arithmetic models
        import sys
        sys.path.insert(0, str(PROJECT_ROOT))
        from scripts.analysis.compute_error_metrics import (
            loa_adder, heaa_adder, ama5_adder, bam_multiplier,
        )

        func_map = {
            "loa": (loa_adder, {"k": args.k}),
            "heaa": (heaa_adder, {"k": args.k}),
            "ama5": (ama5_adder, {"k": args.k}),
            "bam": (bam_multiplier, {"v": args.k}),
            None: (None, {}),
        }
        func, kwargs = func_map[args.approx]

        build_python_truth_table(
            circuit_type=args.circuit_type,
            n_bits=args.n_bits,
            approx_func=func,
            approx_kwargs=kwargs,
            output_csv=args.output,
        )
    else:
        if not args.template:
            parser.error("--template is required for SPICE simulation mode")

        run_batch_sweep(
            template_path=args.template,
            circuit_type=args.circuit_type,
            n_bits=args.n_bits,
            max_workers=args.workers,
            use_docker=not args.native,
            vdd=args.vdd,
            output_csv=args.output,
        )
