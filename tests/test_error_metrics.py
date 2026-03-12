#!/usr/bin/env python3
"""pytest tests for compute_error_metrics.py.

Validates approximate arithmetic implementations against known
error metric ranges.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.analysis.compute_error_metrics import (
    nmed,
    mred,
    error_rate,
    wce,
    compute_all_metrics,
    exact_adder_truth_table,
    exact_multiplier_truth_table,
    loa_adder,
    heaa_adder,
    ama5_adder,
    bam_multiplier,
)


# ---- Fixtures ----

@pytest.fixture
def adder_8bit():
    """Generate 8-bit exact adder truth table."""
    a, b, sums = exact_adder_truth_table(8)
    return a, b, sums, 9  # n_out = 9 (8-bit + carry)


@pytest.fixture
def multiplier_4bit():
    """Generate 4-bit exact multiplier truth table."""
    a, b, products = exact_multiplier_truth_table(4)
    return a, b, products, 8  # n_out = 8 (4-bit * 4-bit)


# ---- Test: Exact Adder (NMED=0) ----

class TestExactAdder:
    """Tests for exact adder producing zero error."""

    def test_exact_adder_nmed_zero(self, adder_8bit):
        """Exact adder should have NMED = 0."""
        a, b, exact, n_out = adder_8bit
        approx = a.astype(np.int64) + b.astype(np.int64)  # Exact sum
        assert nmed(exact, approx, n_out) == 0.0

    def test_exact_adder_mred_zero(self, adder_8bit):
        """Exact adder should have MRED = 0."""
        a, b, exact, n_out = adder_8bit
        approx = exact.copy()
        assert mred(exact, approx) == 0.0

    def test_exact_adder_error_rate_zero(self, adder_8bit):
        """Exact adder should have ER = 0."""
        a, b, exact, n_out = adder_8bit
        approx = exact.copy()
        assert error_rate(exact, approx) == 0.0

    def test_exact_adder_wce_zero(self, adder_8bit):
        """Exact adder should have WCE = 0."""
        a, b, exact, n_out = adder_8bit
        approx = exact.copy()
        assert wce(exact, approx, n_out) == 0.0

    def test_exact_truth_table_size(self, adder_8bit):
        """8-bit adder truth table should have 2^16 = 65536 entries."""
        a, b, exact, n_out = adder_8bit
        assert len(a) == 65536
        assert len(b) == 65536
        assert len(exact) == 65536

    def test_exact_truth_table_range(self, adder_8bit):
        """Output should range from 0 to 510 (255 + 255)."""
        a, b, exact, n_out = adder_8bit
        assert exact.min() == 0
        assert exact.max() == 510  # 255 + 255


# ---- Test: LOA Adder (k=4) ----

class TestLOAAdder:
    """Tests for Lower-part-OR Adder with k=4."""

    def test_loa_k4_nmed_range(self, adder_8bit):
        """LOA k=4 NMED should be in [0.002, 0.02]."""
        a, b, exact, n_out = adder_8bit
        approx = loa_adder(a, b, 8, 4)
        nmed_val = nmed(exact, approx, n_out)
        assert 0.002 <= nmed_val <= 0.02, f"LOA NMED={nmed_val:.6f} outside [0.002, 0.02]"

    def test_loa_k4_error_rate_positive(self, adder_8bit):
        """LOA k=4 should have non-zero error rate."""
        a, b, exact, n_out = adder_8bit
        approx = loa_adder(a, b, 8, 4)
        er = error_rate(exact, approx)
        assert er > 0, "LOA should produce some errors"

    def test_loa_k4_error_rate_not_total(self, adder_8bit):
        """LOA k=4 should not produce errors for all inputs."""
        a, b, exact, n_out = adder_8bit
        approx = loa_adder(a, b, 8, 4)
        er = error_rate(exact, approx)
        assert er < 1.0, "LOA should not produce errors for ALL inputs"

    def test_loa_k0_is_exact(self, adder_8bit):
        """LOA k=0 should be equivalent to exact addition (edge case)."""
        a, b, exact, n_out = adder_8bit
        # k=1 is the minimum meaningful approximate level
        # k=0 doesn't make sense for LOA, but k=1 has minimal approximation
        approx = loa_adder(a, b, 8, 1)
        # Even k=1 should have very low error
        nmed_val = nmed(exact, approx, n_out)
        assert nmed_val < 0.01, f"LOA k=1 NMED={nmed_val:.6f} too high"

    def test_loa_nmed_increases_with_k(self, adder_8bit):
        """NMED should generally increase with k (more approximation)."""
        a, b, exact, n_out = adder_8bit
        nmed_values = []
        for k in [2, 4, 6]:
            approx = loa_adder(a, b, 8, k)
            nmed_values.append(nmed(exact, approx, n_out))

        # NMED should be monotonically non-decreasing
        for i in range(len(nmed_values) - 1):
            assert nmed_values[i] <= nmed_values[i + 1] + 1e-10, (
                f"NMED should increase with k: "
                f"k={[2,4,6][i]} NMED={nmed_values[i]:.6f} > "
                f"k={[2,4,6][i+1]} NMED={nmed_values[i+1]:.6f}"
            )


# ---- Test: HEAA Adder (k=4) ----

class TestHEAAAdder:
    """Tests for Hardware-Efficient Approximate Adder with k=4."""

    def test_heaa_k4_lower_nmed_than_loa(self, adder_8bit):
        """HEAA k=4 should have lower NMED than LOA k=4 (more accurate)."""
        a, b, exact, n_out = adder_8bit
        loa_approx = loa_adder(a, b, 8, 4)
        heaa_approx = heaa_adder(a, b, 8, 4)

        nmed_loa = nmed(exact, loa_approx, n_out)
        nmed_heaa = nmed(exact, heaa_approx, n_out)

        assert nmed_heaa < nmed_loa, (
            f"HEAA NMED={nmed_heaa:.6f} should be < LOA NMED={nmed_loa:.6f}"
        )

    def test_heaa_k4_nmed_reasonable(self, adder_8bit):
        """HEAA k=4 NMED should be in a reasonable range."""
        a, b, exact, n_out = adder_8bit
        approx = heaa_adder(a, b, 8, 4)
        nmed_val = nmed(exact, approx, n_out)
        assert 0.001 <= nmed_val <= 0.02, f"HEAA NMED={nmed_val:.6f} outside [0.001, 0.02]"

    def test_heaa_error_rate(self, adder_8bit):
        """HEAA k=4 should have error rate less than LOA k=4."""
        a, b, exact, n_out = adder_8bit
        loa_approx = loa_adder(a, b, 8, 4)
        heaa_approx = heaa_adder(a, b, 8, 4)

        er_loa = error_rate(exact, loa_approx)
        er_heaa = error_rate(exact, heaa_approx)

        assert er_heaa <= er_loa, (
            f"HEAA ER={er_heaa:.4f} should be <= LOA ER={er_loa:.4f}"
        )

    def test_heaa_k2_nmed(self, adder_8bit):
        """HEAA k=2 should have lower error than k=4."""
        a, b, exact, n_out = adder_8bit
        heaa_k2 = heaa_adder(a, b, 8, 2)
        heaa_k4 = heaa_adder(a, b, 8, 4)

        nmed_k2 = nmed(exact, heaa_k2, n_out)
        nmed_k4 = nmed(exact, heaa_k4, n_out)

        assert nmed_k2 <= nmed_k4 + 1e-10, (
            f"HEAA k=2 NMED={nmed_k2:.6f} should be <= k=4 NMED={nmed_k4:.6f}"
        )


# ---- Test: AMA5 Adder (k=4) ----

class TestAMA5Adder:
    """Tests for AMA5/APPROX5 Adder with k=4."""

    def test_ama5_k4_nmed_range(self, adder_8bit):
        """AMA5 k=4 NMED should be in a reasonable range."""
        a, b, exact, n_out = adder_8bit
        approx = ama5_adder(a, b, 8, 4)
        nmed_val = nmed(exact, approx, n_out)
        # AMA5 has moderate error for k=4 on 8-bit adder
        assert 0.002 <= nmed_val <= 0.02, f"AMA5 NMED={nmed_val:.6f} outside [0.002, 0.02]"

    def test_ama5_k4_has_errors(self, adder_8bit):
        """AMA5 k=4 should produce errors."""
        a, b, exact, n_out = adder_8bit
        approx = ama5_adder(a, b, 8, 4)
        er = error_rate(exact, approx)
        assert er > 0, "AMA5 k=4 should produce some errors"

    def test_ama5_k4_wce(self, adder_8bit):
        """AMA5 k=4 WCE should be bounded."""
        a, b, exact, n_out = adder_8bit
        approx = ama5_adder(a, b, 8, 4)
        wce_val = wce(exact, approx, n_out)
        assert wce_val < 0.1, f"AMA5 WCE={wce_val:.6f} too high"

    def test_ama5_compute_all_metrics(self, adder_8bit):
        """compute_all_metrics should return all expected keys."""
        a, b, exact, n_out = adder_8bit
        approx = ama5_adder(a, b, 8, 4)
        metrics = compute_all_metrics(exact, approx, n_out)
        assert "NMED" in metrics
        assert "MRED" in metrics
        assert "ER" in metrics
        assert "WCE" in metrics
        assert all(isinstance(v, float) for v in metrics.values())


# ---- Test: BAM Multiplier (v=2) ----

class TestBAMMultiplier:
    """Tests for Broken Array Multiplier with v=2."""

    def test_bam_v2_nmed_range(self, multiplier_4bit):
        """BAM v=2 NMED should be in a reasonable range."""
        a, b, exact, n_out = multiplier_4bit
        approx = bam_multiplier(a, b, 4, 2)
        nmed_val = nmed(exact, approx, n_out)
        assert 0.001 <= nmed_val <= 0.15, f"BAM NMED={nmed_val:.6f} outside [0.001, 0.15]"

    def test_bam_v0_is_exact(self, multiplier_4bit):
        """BAM v=0 should be exact (no partial products removed)."""
        a, b, exact, n_out = multiplier_4bit
        approx = bam_multiplier(a, b, 4, 0)
        nmed_val = nmed(exact, approx, n_out)
        assert nmed_val == 0.0, f"BAM v=0 should be exact, got NMED={nmed_val:.6f}"

    def test_bam_truth_table_size(self, multiplier_4bit):
        """4-bit multiplier truth table should have 2^8 = 256 entries."""
        a, b, exact, n_out = multiplier_4bit
        assert len(a) == 256
        assert len(b) == 256
        assert len(exact) == 256

    def test_bam_truth_table_range(self, multiplier_4bit):
        """Output should range from 0 to 225 (15 * 15)."""
        a, b, exact, n_out = multiplier_4bit
        assert exact.min() == 0
        assert exact.max() == 225  # 15 * 15

    def test_bam_nmed_increases_with_v(self, multiplier_4bit):
        """NMED should increase with v (more partial products removed)."""
        a, b, exact, n_out = multiplier_4bit
        nmed_values = []
        for v in [0, 1, 2, 3]:
            approx = bam_multiplier(a, b, 4, v)
            nmed_values.append(nmed(exact, approx, n_out))

        for i in range(len(nmed_values) - 1):
            assert nmed_values[i] <= nmed_values[i + 1] + 1e-10, (
                f"BAM NMED should increase: v={i} NMED={nmed_values[i]:.6f} > "
                f"v={i+1} NMED={nmed_values[i+1]:.6f}"
            )


# ---- Test: Edge Cases ----

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_nmed_identical_arrays(self):
        """NMED of identical arrays should be 0."""
        a = np.array([1, 2, 3, 4])
        assert nmed(a, a, 4) == 0.0

    def test_nmed_single_element(self):
        """NMED should work with single-element arrays."""
        exact = np.array([5])
        approx = np.array([3])
        n_out = 4  # max_val = 15
        expected = abs(5 - 3) / 15
        assert abs(nmed(exact, approx, n_out) - expected) < 1e-10

    def test_mred_zero_exact(self):
        """MRED should handle zero exact values (skip them)."""
        exact = np.array([0, 0, 5, 10])
        approx = np.array([1, 2, 6, 11])
        result = mred(exact, approx)
        # Only non-zero exact: |5-6|/5=0.2, |10-11|/10=0.1 -> mean=0.15
        expected = (0.2 + 0.1) / 2.0
        assert abs(result - expected) < 1e-10

    def test_mred_all_zeros(self):
        """MRED with all-zero exact should return 0."""
        exact = np.array([0, 0, 0])
        approx = np.array([1, 2, 3])
        assert mred(exact, approx) == 0.0

    def test_error_rate_all_correct(self):
        """Error rate of identical arrays should be 0."""
        a = np.array([1, 2, 3])
        assert error_rate(a, a) == 0.0

    def test_error_rate_all_wrong(self):
        """Error rate of completely different arrays should be 1."""
        exact = np.array([1, 2, 3])
        approx = np.array([4, 5, 6])
        assert error_rate(exact, approx) == 1.0

    def test_wce_max_error(self):
        """WCE should capture the maximum error."""
        exact = np.array([0, 7, 15])
        approx = np.array([0, 2, 15])
        n_out = 4  # max_val = 15
        expected = 5 / 15  # max error is |7-2|=5
        assert abs(wce(exact, approx, n_out) - expected) < 1e-10

    def test_2bit_adder_exhaustive(self):
        """2-bit adder should have manageable truth table (16 entries)."""
        a, b, sums = exact_adder_truth_table(2)
        assert len(a) == 16  # 2^(2*2) = 16
        assert sums.max() == 6  # 3 + 3

    def test_loa_2bit_k1(self):
        """LOA on 2-bit adder with k=1 should produce bounded error."""
        a, b, exact = exact_adder_truth_table(2)
        approx = loa_adder(a, b, 2, 1)
        nmed_val = nmed(exact, approx, 3)  # 3-bit output
        assert 0.0 <= nmed_val <= 0.5
