#!/usr/bin/env python3
"""Template-based netlist generation using Jinja2.

Generates SPICE netlists from Jinja2 templates for:
  - Single simulation with specific input vectors
  - Batch sweep with exhaustive truth table stimulus
  - Monte Carlo iterations with per-device parameter variation
"""

import argparse
from pathlib import Path

import numpy as np
from jinja2 import Environment, FileSystemLoader, StrictUndefined

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATE_DIR = PROJECT_ROOT / "netlists" / "templates"
OUTPUT_DIR = PROJECT_ROOT / "netlists" / "generated"


def get_jinja_env(template_dir: Path | None = None) -> Environment:
    """Create Jinja2 environment with custom filters for SPICE.

    Args:
        template_dir: Directory containing .j2 templates.
                      Defaults to netlists/templates/

    Returns:
        Configured Jinja2 Environment
    """
    if template_dir is None:
        template_dir = TEMPLATE_DIR

    template_dir.mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Custom filters for SPICE-compatible formatting
    env.filters["spice_eng"] = _spice_eng_notation
    env.filters["spice_voltage"] = lambda v, vdd=1.0: f"{vdd:.4f}" if v else "0.0000"
    env.filters["bits"] = _int_to_bits

    return env


def _spice_eng_notation(value: float) -> str:
    """Convert float to SPICE engineering notation.

    Examples: 1e-9 -> '1n', 45e-9 -> '45n', 1e-12 -> '1p'
    """
    if value == 0:
        return "0"

    abs_val = abs(value)
    prefixes = [
        (1e-15, "f"),
        (1e-12, "p"),
        (1e-9, "n"),
        (1e-6, "u"),
        (1e-3, "m"),
        (1, ""),
        (1e3, "k"),
        (1e6, "meg"),
        (1e9, "g"),
    ]

    for scale, suffix in prefixes:
        scaled = abs_val / scale
        if 0.1 <= scaled < 1000:
            sign = "-" if value < 0 else ""
            if scaled == int(scaled):
                return f"{sign}{int(scaled)}{suffix}"
            return f"{sign}{scaled:.4g}{suffix}"

    # Fallback to scientific notation
    return f"{value:.6e}"


def _int_to_bits(value: int, n_bits: int = 8) -> list[int]:
    """Convert integer to list of bits (LSB first)."""
    return [(value >> i) & 1 for i in range(n_bits)]


def generate_single_sim_netlist(
    template_name: str,
    a_val: int,
    b_val: int,
    n_bits: int = 8,
    vdd: float = 1.0,
    circuit_type: str = "adder",
    output_path: Path | None = None,
    extra_params: dict | None = None,
) -> Path:
    """Generate a netlist for a single simulation with fixed inputs.

    Args:
        template_name: Jinja2 template filename (e.g., 'adder_single.j2')
        a_val: Operand A value
        b_val: Operand B value
        n_bits: Operand bit width
        vdd: Supply voltage
        circuit_type: 'adder' or 'multiplier'
        output_path: Where to write the generated netlist
        extra_params: Additional template parameters

    Returns:
        Path to generated netlist file
    """
    env = get_jinja_env()

    n_out = n_bits + 1 if circuit_type == "adder" else 2 * n_bits

    # Build bit arrays
    a_bits = [(a_val >> i) & 1 for i in range(n_bits)]
    b_bits = [(b_val >> i) & 1 for i in range(n_bits)]

    context = {
        "a_val": a_val,
        "b_val": b_val,
        "a_bits": a_bits,
        "b_bits": b_bits,
        "n_bits": n_bits,
        "n_out": n_out,
        "vdd": vdd,
        "circuit_type": circuit_type,
        "project_root": str(PROJECT_ROOT),
    }
    if extra_params:
        context.update(extra_params)

    template = env.get_template(template_name)
    netlist = template.render(**context)

    if output_path is None:
        output_path = OUTPUT_DIR / f"single_a{a_val}_b{b_val}.sp"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(netlist)

    return output_path


def generate_batch_sweep_netlist(
    template_name: str,
    n_bits: int = 8,
    circuit_type: str = "adder",
    vdd: float = 1.0,
    period: float = 10e-9,
    output_path: Path | None = None,
    max_vectors: int | None = None,
    extra_params: dict | None = None,
) -> Path:
    """Generate a single netlist with PWL stimulus for all input vectors.

    Creates a long transient simulation where each input combination
    is applied for one period.

    Args:
        template_name: Jinja2 template filename
        n_bits: Operand bit width
        circuit_type: 'adder' or 'multiplier'
        vdd: Supply voltage
        period: Time per input vector (seconds)
        output_path: Where to write the generated netlist
        max_vectors: Limit number of vectors (for testing)
        extra_params: Additional template parameters

    Returns:
        Path to generated netlist file
    """
    env = get_jinja_env()

    max_val = 1 << n_bits
    n_out = n_bits + 1 if circuit_type == "adder" else 2 * n_bits
    total_vectors = max_val * max_val

    if max_vectors and max_vectors < total_vectors:
        total_vectors = max_vectors

    # Generate PWL data for each input bit
    pwl_data = {}
    for bit_idx in range(n_bits):
        pwl_a = []
        pwl_b = []
        vec_idx = 0
        for a in range(max_val):
            for b in range(max_val):
                if vec_idx >= total_vectors:
                    break
                t_start = vec_idx * period
                v_a = vdd if ((a >> bit_idx) & 1) else 0.0
                v_b = vdd if ((b >> bit_idx) & 1) else 0.0
                pwl_a.append((t_start, v_a))
                pwl_b.append((t_start, v_b))
                vec_idx += 1
            if vec_idx >= total_vectors:
                break

        pwl_data[f"a{bit_idx}"] = pwl_a
        pwl_data[f"b{bit_idx}"] = pwl_b

    total_time = total_vectors * period

    context = {
        "n_bits": n_bits,
        "n_out": n_out,
        "vdd": vdd,
        "period": period,
        "total_vectors": total_vectors,
        "total_time": total_time,
        "pwl_data": pwl_data,
        "circuit_type": circuit_type,
        "project_root": str(PROJECT_ROOT),
    }
    if extra_params:
        context.update(extra_params)

    template = env.get_template(template_name)
    netlist = template.render(**context)

    if output_path is None:
        output_path = OUTPUT_DIR / f"batch_{circuit_type}_{n_bits}bit.sp"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(netlist)

    print(f"Generated batch netlist: {total_vectors} vectors, "
          f"total_time={total_time:.6e}s")
    return output_path


def generate_mc_iteration_netlist(
    template_name: str,
    iteration: int,
    vt_offsets: np.ndarray,
    n_bits: int = 8,
    vdd: float = 1.0,
    circuit_type: str = "adder",
    output_path: Path | None = None,
    extra_params: dict | None = None,
) -> Path:
    """Generate a netlist for one Monte Carlo iteration.

    Includes per-device VT offset parameters for FeFET variability
    simulation.

    Args:
        template_name: Jinja2 template filename
        iteration: MC iteration number
        vt_offsets: Array of VT offsets (V) for each FeFET device
        n_bits: Operand bit width
        vdd: Supply voltage
        circuit_type: 'adder' or 'multiplier'
        output_path: Where to write the generated netlist
        extra_params: Additional template parameters

    Returns:
        Path to generated netlist file
    """
    env = get_jinja_env()

    n_out = n_bits + 1 if circuit_type == "adder" else 2 * n_bits

    context = {
        "iteration": iteration,
        "vt_offsets": vt_offsets.tolist(),
        "num_fefets": len(vt_offsets),
        "n_bits": n_bits,
        "n_out": n_out,
        "vdd": vdd,
        "circuit_type": circuit_type,
        "project_root": str(PROJECT_ROOT),
    }
    if extra_params:
        context.update(extra_params)

    template = env.get_template(template_name)
    netlist = template.render(**context)

    if output_path is None:
        output_path = (
            OUTPUT_DIR / "monte_carlo" / f"mc_iter_{iteration:04d}.sp"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(netlist)

    return output_path


def generate_mc_param_file(
    iteration: int,
    vt_offsets: np.ndarray,
    output_dir: Path | None = None,
) -> Path:
    """Generate a standalone .inc parameter file for MC iteration.

    This file is .included by the MC netlist template and provides
    device-specific VT shift values.

    Args:
        iteration: MC iteration number
        vt_offsets: Array of VT offsets (V)
        output_dir: Directory for parameter files

    Returns:
        Path to generated .inc file
    """
    if output_dir is None:
        output_dir = PROJECT_ROOT / "netlists" / "monte_carlo" / "params"

    output_dir.mkdir(parents=True, exist_ok=True)
    param_file = output_dir / f"mc_params_{iteration:04d}.inc"

    lines = [
        f"* Monte Carlo iteration {iteration}",
        f"* {len(vt_offsets)} FeFET VT offsets",
        "",
    ]

    for i, offset in enumerate(vt_offsets):
        lines.append(f".param vt_offset_{i} = {offset:.6e}")

    param_file.write_text("\n".join(lines) + "\n")
    return param_file


def create_default_templates():
    """Create default Jinja2 template files if they don't exist.

    Creates starter templates for single, batch, and MC simulations.
    """
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

    # Single simulation template
    single_template = TEMPLATE_DIR / "adder_single.j2"
    if not single_template.exists():
        single_template.write_text("""\
* Auto-generated single-vector testbench
* Circuit: {{ circuit_type }} {{ n_bits }}-bit
* Input: A={{ a_val }}, B={{ b_val }}

.include '{{ project_root }}/netlists/common/supply.inc'

* --- Circuit Under Test ---
* (include your circuit subcircuit here)

* --- Input Stimulus ---
{% for i in range(n_bits) %}
Va{{ i }} a{{ i }} 0 DC {{ (a_bits[i] * vdd)|spice_voltage }}
{% endfor %}
{% for i in range(n_bits) %}
Vb{{ i }} b{{ i }} 0 DC {{ (b_bits[i] * vdd)|spice_voltage }}
{% endfor %}

* --- Analysis ---
.tran 10p 20n

.control
run
{% set output_signals = [] %}
{% for i in range(n_out) %}
{% set _ = output_signals.append("v(s" ~ i ~ ")") %}
{% endfor %}
wrdata {{ project_root }}/results/raw/single_a{{ a_val }}_b{{ b_val }}.csv {{ output_signals | join(' ') }}
.endc

.end
""")

    # Batch sweep template
    batch_template = TEMPLATE_DIR / "adder_batch.j2"
    if not batch_template.exists():
        batch_template.write_text("""\
* Auto-generated batch sweep testbench
* Circuit: {{ circuit_type }} {{ n_bits }}-bit
* Vectors: {{ total_vectors }}, Period: {{ period|spice_eng }}

.include '{{ project_root }}/netlists/common/supply.inc'

* --- Circuit Under Test ---
* (include your circuit subcircuit here)

* --- PWL Input Stimulus ---
{% for bit_idx in range(n_bits) %}
Va{{ bit_idx }} a{{ bit_idx }} 0 PWL(
{% for t, v in pwl_data["a" ~ bit_idx] %}
+  {{ "%.6e"|format(t) }} {{ "%.4f"|format(v) }}
{% endfor %}
+ )
Vb{{ bit_idx }} b{{ bit_idx }} 0 PWL(
{% for t, v in pwl_data["b" ~ bit_idx] %}
+  {{ "%.6e"|format(t) }} {{ "%.4f"|format(v) }}
{% endfor %}
+ )
{% endfor %}

* --- Analysis ---
.tran {{ (period / 100)|spice_eng }} {{ total_time|spice_eng }}

.control
run
{% set output_signals = [] %}
{% for i in range(n_out) %}
{% set _ = output_signals.append("v(s" ~ i ~ ")") %}
{% endfor %}
wrdata {{ project_root }}/results/raw/batch_{{ circuit_type }}_{{ n_bits }}bit.csv {{ output_signals | join(' ') }}
.endc

.end
""")

    # Monte Carlo template
    mc_template = TEMPLATE_DIR / "fefet_mc.j2"
    if not mc_template.exists():
        mc_template.write_text("""\
* Auto-generated Monte Carlo iteration {{ iteration }}
* {{ num_fefets }} FeFET devices with VT offsets

.include '{{ project_root }}/netlists/common/supply.inc'

* --- VT Offset Parameters ---
{% for i in range(num_fefets) %}
.param vt_offset_{{ i }} = {{ "%.6e"|format(vt_offsets[i]) }}
{% endfor %}

* --- Circuit Under Test ---
* (include your FeFET circuit subcircuit here)

* --- Analysis ---
.tran 10p 20n

.include '{{ project_root }}/netlists/common/measure_template.inc'

.control
run
print all
.endc

.end
""")

    print(f"Default templates created in {TEMPLATE_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate SPICE netlists from Jinja2 templates"
    )
    subparsers = parser.add_subparsers(dest="command")

    # init subcommand — create default templates
    subparsers.add_parser("init", help="Create default template files")

    # single subcommand
    single_parser = subparsers.add_parser(
        "single", help="Generate single-vector netlist"
    )
    single_parser.add_argument("--template", required=True)
    single_parser.add_argument("-a", type=int, required=True)
    single_parser.add_argument("-b", type=int, required=True)
    single_parser.add_argument("--n-bits", type=int, default=8)
    single_parser.add_argument("--vdd", type=float, default=1.0)
    single_parser.add_argument("--output", type=str, default=None)

    # batch subcommand
    batch_parser = subparsers.add_parser(
        "batch", help="Generate batch sweep netlist"
    )
    batch_parser.add_argument("--template", required=True)
    batch_parser.add_argument("--n-bits", type=int, default=8)
    batch_parser.add_argument("--circuit-type", default="adder")
    batch_parser.add_argument("--vdd", type=float, default=1.0)
    batch_parser.add_argument("--max-vectors", type=int, default=None)
    batch_parser.add_argument("--output", type=str, default=None)

    # mc subcommand
    mc_parser = subparsers.add_parser(
        "mc", help="Generate Monte Carlo iteration netlist"
    )
    mc_parser.add_argument("--template", required=True)
    mc_parser.add_argument("--iteration", type=int, required=True)
    mc_parser.add_argument("--num-fefets", type=int, required=True)
    mc_parser.add_argument("--sigma-d2d", type=float, default=0.040)
    mc_parser.add_argument("--seed", type=int, default=42)
    mc_parser.add_argument("--output", type=str, default=None)

    args = parser.parse_args()

    if args.command == "init":
        create_default_templates()

    elif args.command == "single":
        output = Path(args.output) if args.output else None
        path = generate_single_sim_netlist(
            template_name=args.template,
            a_val=args.a,
            b_val=args.b,
            n_bits=args.n_bits,
            vdd=args.vdd,
            output_path=output,
        )
        print(f"Generated: {path}")

    elif args.command == "batch":
        output = Path(args.output) if args.output else None
        path = generate_batch_sweep_netlist(
            template_name=args.template,
            n_bits=args.n_bits,
            circuit_type=args.circuit_type,
            vdd=args.vdd,
            max_vectors=args.max_vectors,
            output_path=output,
        )
        print(f"Generated: {path}")

    elif args.command == "mc":
        from scripts.simulation.run_monte_carlo import generate_vt_offsets
        vt = generate_vt_offsets(
            args.num_fefets, args.sigma_d2d, seed=args.seed + args.iteration,
        )
        output = Path(args.output) if args.output else None
        path = generate_mc_iteration_netlist(
            template_name=args.template,
            iteration=args.iteration,
            vt_offsets=vt,
            output_path=output,
        )
        print(f"Generated: {path}")

    else:
        parser.print_help()
