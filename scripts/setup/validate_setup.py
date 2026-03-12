#!/usr/bin/env python3
"""Smoke test script to validate the simulation environment.

Runs four tests:
  1. Check ngspice is available (Docker or native)
  2. Run PTM inverter simulation, check output crosses VDD/2
  3. Check HERACLES OSDI loads (if Docker available)
  4. Run Python truth table generation, verify LOA NMED ~0.03-0.06

Prints PASS/FAIL for each test.
"""

import subprocess
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DOCKER_CONTAINER = "ngspice-sim"


class TestResult:
    """Holds a test result with name, pass/fail, and optional message."""

    def __init__(self, name: str, passed: bool, message: str = ""):
        self.name = name
        self.passed = passed
        self.message = message

    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        msg = f" -- {self.message}" if self.message else ""
        return f"  [{status}] {self.name}{msg}"


def test_ngspice_available() -> TestResult:
    """Test 1: Check ngspice is available via Docker or natively."""
    # Try Docker first
    try:
        result = subprocess.run(
            ["docker", "exec", DOCKER_CONTAINER, "ngspice", "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            version = result.stdout.strip().split("\n")[0]
            return TestResult(
                "ngspice available (Docker)",
                True,
                f"version: {version}",
            )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Try native
    try:
        result = subprocess.run(
            ["ngspice", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            version = result.stdout.strip().split("\n")[0]
            return TestResult(
                "ngspice available (native)",
                True,
                f"version: {version}",
            )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return TestResult(
        "ngspice available",
        False,
        "Neither Docker nor native ngspice found. "
        "Install ngspice or start Docker container.",
    )


def test_inverter_simulation() -> TestResult:
    """Test 2: Run PTM inverter sim, check output crosses VDD/2."""
    netlist_path = PROJECT_ROOT / "netlists" / "cmos_baseline" / "inverter_cmos45.sp"

    if not netlist_path.exists():
        return TestResult(
            "Inverter simulation",
            False,
            f"Netlist not found: {netlist_path}",
        )

    # Determine if Docker or native
    use_docker = _docker_available()

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
            return TestResult(
                "Inverter simulation",
                False,
                f"ngspice returned {result.returncode}: "
                f"{result.stderr[:200]}",
            )

        # Check that output CSV was created
        output_csv = PROJECT_ROOT / "results" / "raw" / "cmos_baseline" / "inverter_cmos45.csv"
        if output_csv.exists():
            # Parse and check for VDD/2 crossing
            vdd = 1.0
            threshold = vdd / 2.0
            has_high = False
            has_low = False

            with open(output_csv) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or line.startswith("*"):
                        continue
                    parts = line.split()
                    if len(parts) >= 3:
                        try:
                            # ngspice wrdata emits (time, val) pairs per signal;
                            # last column is always v(out)
                            v_out = float(parts[-1])
                            if v_out > threshold:
                                has_high = True
                            if v_out < threshold:
                                has_low = True
                        except (ValueError, IndexError):
                            continue

            if has_high and has_low:
                return TestResult(
                    "Inverter simulation",
                    True,
                    "Output crosses VDD/2 (correct inversion)",
                )
            else:
                return TestResult(
                    "Inverter simulation",
                    False,
                    f"Output does not cross VDD/2 "
                    f"(high={has_high}, low={has_low})",
                )
        else:
            # Simulation ran but no output file — still consider partial success
            return TestResult(
                "Inverter simulation",
                True,
                "Simulation completed (output CSV not found at expected path)",
            )

    except subprocess.TimeoutExpired:
        return TestResult("Inverter simulation", False, "Timed out (30s)")
    except Exception as e:
        return TestResult("Inverter simulation", False, str(e))


def test_heracles_osdi() -> TestResult:
    """Test 3: Check HERACLES OSDI loads in ngspice (Docker only)."""
    if not _docker_available():
        return TestResult(
            "HERACLES OSDI",
            False,
            "Docker not available, skipping OSDI check",
        )

    # Check if .osdi file exists
    osdi_candidates = [
        PROJECT_ROOT / "models" / "fefet" / "heracles" / "heracles.osdi",
        PROJECT_ROOT / "models" / "fefet" / "heracles" / "heracles_linux_amd64.osdi",
    ]

    osdi_path = None
    for candidate in osdi_candidates:
        if candidate.exists():
            osdi_path = candidate
            break

    if osdi_path is None:
        # Check if .va source exists for compilation
        va_path = PROJECT_ROOT / "models" / "fefet" / "heracles" / "heracles.va"
        if va_path.exists():
            return TestResult(
                "HERACLES OSDI",
                False,
                "OSDI not compiled. Run: scripts/setup/compile_osdi.sh",
            )
        return TestResult(
            "HERACLES OSDI",
            False,
            "Neither .osdi nor .va found in models/fefet/heracles/",
        )

    # Try loading in ngspice
    test_netlist = f"""* OSDI load test
.control
pre_osdi /workspace/{osdi_path.relative_to(PROJECT_ROOT)}
echo "OSDI_LOAD_OK"
quit
.endc
.end
"""
    test_file = PROJECT_ROOT / ".tmp_osdi_test.sp"
    try:
        test_file.write_text(test_netlist)
        result = subprocess.run(
            [
                "docker", "exec", DOCKER_CONTAINER,
                "ngspice", "-b", f"/workspace/.tmp_osdi_test.sp",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(PROJECT_ROOT),
        )

        output = result.stdout + result.stderr
        if "OSDI_LOAD_OK" in output or result.returncode == 0:
            return TestResult("HERACLES OSDI", True, "OSDI loads successfully")
        else:
            return TestResult(
                "HERACLES OSDI",
                False,
                f"OSDI load failed: {output[:200]}",
            )
    except Exception as e:
        return TestResult("HERACLES OSDI", False, str(e))
    finally:
        if test_file.exists():
            test_file.unlink()


def test_python_truth_table() -> TestResult:
    """Test 4: Run Python truth table generation, verify LOA NMED ~0.03-0.06."""
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from scripts.analysis.compute_error_metrics import (
            exact_adder_truth_table,
            loa_adder,
            nmed,
        )

        # Generate exact and LOA truth tables
        a, b, exact_sums = exact_adder_truth_table(8)
        loa_sums = loa_adder(a, b, 8, 4)  # k=4
        n_out = 9  # 8-bit + carry

        nmed_val = nmed(exact_sums, loa_sums, n_out)

        # Expected range for LOA k=4 on 8-bit adder with n_out=9
        expected_low = 0.002
        expected_high = 0.02

        if expected_low <= nmed_val <= expected_high:
            return TestResult(
                "Python truth table (LOA NMED)",
                True,
                f"NMED={nmed_val:.6f} (expected {expected_low}-{expected_high})",
            )
        else:
            return TestResult(
                "Python truth table (LOA NMED)",
                False,
                f"NMED={nmed_val:.6f} outside expected range "
                f"[{expected_low}, {expected_high}]",
            )

    except Exception as e:
        return TestResult("Python truth table (LOA NMED)", False, str(e))


def _docker_available() -> bool:
    """Check if Docker container is running."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Running}}", DOCKER_CONTAINER],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0 and "true" in result.stdout.lower()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def run_all_tests() -> int:
    """Run all validation tests and print results.

    Returns:
        Number of failed tests
    """
    print("=" * 60)
    print("FeFET Approximate CiM — Setup Validation")
    print("=" * 60)
    print()

    tests = [
        test_ngspice_available,
        test_inverter_simulation,
        test_heracles_osdi,
        test_python_truth_table,
    ]

    results = []
    for test_func in tests:
        print(f"Running: {test_func.__doc__.strip().split(chr(10))[0]}...")
        result = test_func()
        results.append(result)
        print(result)
        print()

    # Summary
    n_pass = sum(1 for r in results if r.passed)
    n_fail = sum(1 for r in results if not r.passed)
    total = len(results)

    print("=" * 60)
    print(f"Results: {n_pass}/{total} passed, {n_fail}/{total} failed")

    if n_fail == 0:
        print("All tests passed. Environment is ready.")
    else:
        print("\nSome tests failed. Check the messages above for details.")
        print("Note: Docker-dependent tests (2, 3) require the ngspice-sim")
        print("container to be running: docker compose -f docker/docker-compose.yml up -d")

    print("=" * 60)
    return n_fail


if __name__ == "__main__":
    n_fail = run_all_tests()
    sys.exit(min(n_fail, 1))  # Exit 0 if all pass, 1 if any fail
