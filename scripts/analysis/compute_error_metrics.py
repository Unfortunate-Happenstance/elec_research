#!/usr/bin/env python3
"""Compute error metrics for approximate arithmetic circuits.

Metrics: NMED, MRED, ER, WCE — standard approximate computing metrics.
"""

import csv
from pathlib import Path

import numpy as np


def nmed(exact: np.ndarray, approx: np.ndarray, n_bits_output: int) -> float:
    """Normalized Mean Error Distance.

    NMED = mean(|exact - approx|) / (2^n - 1)
    Lower is better. Range: [0, 1].
    """
    max_val = (1 << n_bits_output) - 1
    if max_val == 0:
        return 0.0
    errors = np.abs(exact.astype(np.float64) - approx.astype(np.float64))
    return float(np.mean(errors) / max_val)


def mred(exact: np.ndarray, approx: np.ndarray) -> float:
    """Mean Relative Error Distance.

    MRED = mean(|exact - approx| / |exact|) for exact != 0.
    Lower is better.
    """
    mask = exact != 0
    if not np.any(mask):
        return 0.0
    rel_errors = np.abs(exact[mask].astype(np.float64) - approx[mask].astype(np.float64)) / np.abs(exact[mask].astype(np.float64))
    return float(np.mean(rel_errors))


def error_rate(exact: np.ndarray, approx: np.ndarray) -> float:
    """Error Rate — fraction of inputs producing incorrect output.

    ER = count(exact != approx) / total.
    Range: [0, 1].
    """
    return float(np.mean(exact != approx))


def wce(exact: np.ndarray, approx: np.ndarray, n_bits_output: int) -> float:
    """Worst-Case Error (normalized).

    WCE = max(|exact - approx|) / (2^n - 1).
    """
    max_val = (1 << n_bits_output) - 1
    if max_val == 0:
        return 0.0
    return float(np.max(np.abs(exact.astype(np.float64) - approx.astype(np.float64))) / max_val)


def compute_all_metrics(
    exact: np.ndarray,
    approx: np.ndarray,
    n_bits_output: int,
) -> dict:
    """Compute all error metrics."""
    return {
        "NMED": nmed(exact, approx, n_bits_output),
        "MRED": mred(exact, approx),
        "ER": error_rate(exact, approx),
        "WCE": wce(exact, approx, n_bits_output),
    }


# ---- Exhaustive truth table generators ----

def exact_adder_truth_table(n_bits: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate exhaustive truth table for n-bit adder.

    Returns: (a_values, b_values, exact_sums)
    Each is a 1D array of length 2^(2n).
    """
    max_val = 1 << n_bits
    a = np.repeat(np.arange(max_val), max_val)
    b = np.tile(np.arange(max_val), max_val)
    sums = a.astype(np.int64) + b.astype(np.int64)
    return a, b, sums


def loa_adder(a: np.ndarray, b: np.ndarray, n_bits: int, k: int) -> np.ndarray:
    """Lower-part-OR Adder (LOA).

    Lower k bits: sum[i] = a[i] | b[i]
    Carry to upper part: c_k = a[k-1] & b[k-1]
    Upper (n-k) bits: exact ripple carry with c_k as carry-in.
    """
    lower_mask = (1 << k) - 1
    a_lower = a & lower_mask
    b_lower = b & lower_mask

    # Lower part: bitwise OR
    sum_lower = a_lower | b_lower

    # Carry from approximate part
    carry_k = (a >> (k - 1)) & (b >> (k - 1)) & 1

    # Upper part: exact addition with carry
    a_upper = a >> k
    b_upper = b >> k
    sum_upper = a_upper.astype(np.int64) + b_upper.astype(np.int64) + carry_k.astype(np.int64)

    # Combine
    result = (sum_upper << k) | sum_lower
    return result


def heaa_adder(a: np.ndarray, b: np.ndarray, n_bits: int, k: int) -> np.ndarray:
    """Hardware-Efficient Approximate Adder (HEAA).

    Bits 0..k-2: sum[i] = a[i] | b[i]
    Bit k-1: sum[k-1] = (a[k-1] & b[k-1]) ? 0 : (a[k-1] | b[k-1])
    Carry: c_k = a[k-1] & b[k-1]
    Upper bits: exact RCA with carry-in.
    """
    if k < 2:
        return loa_adder(a, b, n_bits, k)

    lower_mask = (1 << (k - 1)) - 1
    a_lower = a & lower_mask
    b_lower = b & lower_mask
    sum_lower = a_lower | b_lower  # bits 0..k-2

    # Boundary bit k-1
    a_km1 = (a >> (k - 1)) & 1
    b_km1 = (b >> (k - 1)) & 1
    both = a_km1 & b_km1
    either = a_km1 | b_km1
    sum_km1 = np.where(both, 0, either)  # MUX: if both=1, output 0
    carry_k = both

    # Upper part: exact
    a_upper = a >> k
    b_upper = b >> k
    sum_upper = a_upper.astype(np.int64) + b_upper.astype(np.int64) + carry_k.astype(np.int64)

    result = (sum_upper << k) | (sum_km1.astype(np.int64) << (k - 1)) | sum_lower
    return result


def ama5_adder(a: np.ndarray, b: np.ndarray, n_bits: int, k: int) -> np.ndarray:
    """AMA5/APPROX5 Adder.

    Lower k bits: sum[i] = b[i], carry[i] = a[i]
    Upper bits: exact RCA with carry from a[k-1].
    """
    lower_mask = (1 << k) - 1
    sum_lower = b & lower_mask

    carry_k = (a >> (k - 1)) & 1

    a_upper = a >> k
    b_upper = b >> k
    sum_upper = a_upper.astype(np.int64) + b_upper.astype(np.int64) + carry_k.astype(np.int64)

    result = (sum_upper << k) | sum_lower
    return result


def exact_multiplier_truth_table(n_bits: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate exhaustive truth table for n-bit multiplier."""
    max_val = 1 << n_bits
    a = np.repeat(np.arange(max_val), max_val)
    b = np.tile(np.arange(max_val), max_val)
    products = a.astype(np.int64) * b.astype(np.int64)
    return a, b, products


def bam_multiplier(a: np.ndarray, b: np.ndarray, n_bits: int, v: int) -> np.ndarray:
    """Broken Array Multiplier (BAM).

    Remove partial products where (i + j) < v.
    """
    result = np.zeros(len(a), dtype=np.int64)
    for i in range(n_bits):
        for j in range(n_bits):
            if (i + j) >= v:
                # Include this partial product
                ai = (a >> i) & 1
                bj = (b >> j) & 1
                pp = (ai & bj).astype(np.int64)
                result += pp << (i + j)
    return result


def generate_and_save_truth_tables(output_dir: str = "tests/golden_vectors"):
    """Generate all truth tables and save as .npz; also write error_metrics.csv."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print("Generating truth tables...")
    all_metrics = []

    # 8-bit adders
    a8, b8, exact_sum8 = exact_adder_truth_table(8)
    n_out_adder = 9  # 8-bit + carry

    for name, func, k in [
        ("loa8_k4", loa_adder, 4),
        ("heaa8_k4", heaa_adder, 4),
        ("ama5_8bit_k4", ama5_adder, 4),
    ]:
        approx = func(a8, b8, 8, k)
        metrics = compute_all_metrics(exact_sum8, approx, n_out_adder)
        print(f"  {name}: NMED={metrics['NMED']:.6f} MRED={metrics['MRED']:.6f} "
              f"ER={metrics['ER']:.4f} WCE={metrics['WCE']:.6f}")
        all_metrics.append({"circuit": name, **metrics})

        np.savez_compressed(
            out / f"{name}_truth_table.npz",
            a=a8, b=b8, exact=exact_sum8, approx=approx,
        )

    # 4x4 multiplier
    a4, b4, exact_prod4 = exact_multiplier_truth_table(4)
    n_out_mul = 8  # 4-bit × 4-bit = 8-bit

    for name, v in [("bam4x4_v2", 2)]:
        approx = bam_multiplier(a4, b4, 4, v)
        metrics = compute_all_metrics(exact_prod4, approx, n_out_mul)
        print(f"  {name}: NMED={metrics['NMED']:.6f} MRED={metrics['MRED']:.6f} "
              f"ER={metrics['ER']:.4f} WCE={metrics['WCE']:.6f}")
        all_metrics.append({"circuit": name, **metrics})

        np.savez_compressed(
            out / f"{name}_truth_table.npz",
            a=a4, b=b4, exact=exact_prod4, approx=approx,
        )

    # Save error_metrics.csv for downstream table generation
    project_root = Path(__file__).resolve().parent.parent.parent
    csv_path = project_root / "results" / "processed" / "error_metrics.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    import csv as csv_mod
    with open(csv_path, "w", newline="") as f:
        writer = csv_mod.DictWriter(f, fieldnames=["circuit", "NMED", "MRED", "ER", "WCE"])
        writer.writeheader()
        writer.writerows(all_metrics)
    print(f"Error metrics saved to {csv_path}")

    print("Done. Truth tables saved to", out)


if __name__ == "__main__":
    generate_and_save_truth_tables()
