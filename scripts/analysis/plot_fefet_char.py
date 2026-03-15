#!/usr/bin/env python3
"""Phase 4a: Plot HERACLES FeCap P-V loop and FeFET Id-Vgs curves.

Reads the CSV files produced by run_fefet_char.py and generates:
  results/figures/heracles_pv_loop.pdf   — P-V hysteresis loop (cycles 2+3)
  results/figures/fefet_iv_curves.pdf    — Id-Vgs log-scale, LVT+HVT, two Vds

Usage (from elec_research root):
    uv run python scripts/analysis/plot_fefet_char.py

Requires: numpy, matplotlib, scipy
"""

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend for headless/Docker use
import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import cumulative_trapezoid

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_DIR   = PROJECT_ROOT / "results" / "raw" / "fefet"
FIG_DIR   = PROJECT_ROOT / "results" / "figures"

# FeCap parameters (must match netlist)
FECAP_AREA = 625e-12   # m^2
EPS0       = 8.854e-12
EPS_FE     = 70
T_FE       = 9.8e-9    # m
EPS_INT    = 90
T_INT      = 1.5e-9

# Timing offsets for Id-Vgs sweeps (must match fefet_iv_*.sp)
T_WRITE  = 200e-9
T_HOLD   = 200e-9
T_SWEEP  = 10e-6
T_RESET  = 200e-9
T0_SW1   = T_WRITE + T_HOLD              # start of sweep 1
T1_SW1   = T0_SW1 + T_SWEEP             # end of sweep 1
T0_SW2   = T1_SW1 + T_RESET             # start of sweep 2
T1_SW2   = T0_SW2 + T_SWEEP             # end of sweep 2


def parse_wrdata(csv_path: Path) -> dict[str, np.ndarray]:
    """Parse ngspice wrdata CSV output (space-delimited, no header).

    ngspice wrdata format:
      - First column is always 'time' (or the sweep variable)
      - Remaining columns are in pairs: each data point has
        alternating x-value and y-value rows in some versions,
        OR flat time/v1/v2.../vN rows.
    Returns a dict mapping column index (as str) to array.
    """
    rows = []
    with open(csv_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("*") or line.startswith("#"):
                continue
            try:
                vals = [float(v) for v in line.split()]
                if vals:
                    rows.append(vals)
            except ValueError:
                continue  # skip header-like text lines

    if not rows:
        raise ValueError(f"No numeric data found in {csv_path}")

    arr = np.array(rows)
    # ngspice wrdata with multiple columns:
    # column 0 = time, columns 1.. = requested signals in order
    return arr


def extract_pv(pv_path: Path):
    """Extract P-V hysteresis from heracles_pv.csv.

    Columns: time, v_te, v_be, i_fe

    Voltage across FeCap: V_fe = v_te - v_be
    Polarization (total charge): P_total = cumtrapz(i_fe) / area
    Linear correction: P_lin = eps0*eps_fe/t_fe * V_fe  (displacement only)
    Ferroelectric contribution: P_ferro = P_total - P_lin
    """
    arr = parse_wrdata(pv_path)
    if arr.shape[1] < 4:
        raise ValueError(f"Expected 4 columns in {pv_path}, got {arr.shape[1]}")

    t      = arr[:, 0]
    v_te   = arr[:, 1]
    v_be   = arr[:, 2]
    i_fe   = arr[:, 3]

    v_fe = v_te - v_be  # voltage across FeCap (te - be)

    # Integrate total current to get total charge density (C/m^2)
    # Note: i_fe = I(Vmeas) = current into te
    # dt is non-uniform in general — use trapezoid
    q_total = cumulative_trapezoid(i_fe, t, initial=0) / FECAP_AREA  # C/m^2

    # Subtract linear dielectric displacement to isolate ferroelectric P
    # The total charge = eps_fe*eps0/t_fe * V_fecap (linear) + P_ferro (switching)
    p_ferro = q_total - EPS0 * EPS_FE / T_FE * v_fe

    # Use only cycles 2 and 3 (t > period = 20µs) to get saturated loop
    period = 1 / 50e3  # 20 µs
    mask = t > period
    return v_fe[mask], p_ferro[mask], t[mask]


def extract_iv(iv_path: Path, sweep_label: str = ""):
    """Extract two Id-Vgs sweeps from fefet_iv_*.csv.

    Columns: time, vgs_ext, vgate_int, vd, id_src
    Id = -id_src  (SPICE current convention: I(Vds_src) is negative for NMOS)

    Returns: (vgs_sw1, id_sw1, vgs_sw2, id_sw2) for Vds=0.05V and Vds=1.0V
    """
    arr = parse_wrdata(iv_path)
    if arr.shape[1] < 5:
        raise ValueError(f"Expected >=5 columns in {iv_path}, got {arr.shape[1]}")

    t       = arr[:, 0]
    vgs_ext = arr[:, 1]
    # vgate_int = arr[:, 2]  (available but not needed for VT extraction)
    # vd      = arr[:, 3]
    id_src  = arr[:, 4]

    id_drain = -id_src  # conventional NMOS drain current (positive)
    id_drain = np.clip(id_drain, 1e-15, None)  # floor at 1 fA for log scale

    # Time windows for each sweep (from netlist timing)
    def window(t_start, t_end):
        mask = (t >= t_start) & (t <= t_end)
        return vgs_ext[mask], id_drain[mask]

    # Add 5ns margin to avoid edge glitches
    vgs_sw1, id_sw1 = window(T0_SW1 + 5e-9, T1_SW1 - 5e-9)  # Vds=0.05V
    vgs_sw2, id_sw2 = window(T0_SW2 + 5e-9, T1_SW2 - 5e-9)  # Vds=1.0V

    return vgs_sw1, id_sw1, vgs_sw2, id_sw2


def extract_vt(vgs: np.ndarray, id_drain: np.ndarray, vds: float) -> float:
    """Extrapolate VT from linear Id-Vgs at Vds=0.05V using max-gm method.

    VT = Vgs(max gm) - Id(max gm) / max(gm)
    More robust than simple linear extrapolation for short-channel devices.
    Returns VT in volts.
    """
    if len(vgs) < 5:
        return float("nan")
    # Sort by Vgs
    idx = np.argsort(vgs)
    vgs_s = vgs[idx]
    id_s  = id_drain[idx]

    # Transconductance gm = dId/dVgs
    gm = np.gradient(id_s, vgs_s)

    # Peak gm index
    peak_idx = np.argmax(gm)
    gm_peak  = gm[peak_idx]
    if gm_peak <= 0:
        return float("nan")

    # Linear extrapolation from peak-gm point
    vgs_peak = vgs_s[peak_idx]
    id_peak  = id_s[peak_idx]
    vt = vgs_peak - id_peak / gm_peak

    return float(vt)


def plot_pv(pv_path: Path, out_path: Path) -> None:
    """Generate P-V hysteresis loop figure."""
    print(f"  Plotting P-V loop from {pv_path.name}...")
    v_fe, p_ferro, t = extract_pv(pv_path)

    pr_pos = float(np.max(p_ferro))   # remnant P at V=0 going negative
    pr_neg = float(np.min(p_ferro))   # remnant P at V=0 going positive

    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot(v_fe, p_ferro * 100, "b-", linewidth=1.2, label="HERACLES (HZO sim.)")
    ax.axhline(0, color="k", linewidth=0.5, linestyle="--")
    ax.axvline(0, color="k", linewidth=0.5, linestyle="--")

    # Annotate Pr and Vc
    # Vc: zero-crossings of P (coercive field)
    sign_changes = np.where(np.diff(np.sign(p_ferro)))[0]
    vc_vals = []
    for sc in sign_changes:
        if sc + 1 < len(v_fe):
            vc = float(np.interp(0, [p_ferro[sc], p_ferro[sc + 1]],
                                 [v_fe[sc], v_fe[sc + 1]]))
            vc_vals.append(vc)

    vc_str = f"{np.mean(np.abs(vc_vals)):.2f} V" if vc_vals else "N/A"
    pr_str = f"{max(abs(pr_pos), abs(pr_neg)) * 100:.1f} µC/cm²"

    ax.set_xlabel("Applied Voltage $V_{FE}$ (V)", fontsize=11)
    ax.set_ylabel("Polarization $P$ (µC/cm²)", fontsize=11)
    ax.set_title("HERACLES HZO P–V Hysteresis Loop (50 kHz)", fontsize=11)

    text = f"$P_r$ ≈ {pr_str}\n$V_c$ ≈ {vc_str}"
    ax.text(0.05, 0.95, text, transform=ax.transAxes,
            verticalalignment="top", fontsize=9,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="wheat", alpha=0.8))

    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, format="pdf", bbox_inches="tight", dpi=150)
    plt.close(fig)

    print(f"  Pr = {max(abs(pr_pos), abs(pr_neg)):.4f} C/m² "
          f"(expected ~0.27), Vc = {vc_str} (expected ~0.20 V)")
    print(f"  Saved: {out_path.name}")


def plot_iv(lvt_path: Path, hvt_path: Path, out_path: Path) -> None:
    """Generate Id-Vgs figure: LVT and HVT, Vds=0.05V and 1.0V."""
    print(f"  Plotting Id-Vgs from {lvt_path.name} and {hvt_path.name}...")

    vgs_l1, id_l1, vgs_l2, id_l2 = extract_iv(lvt_path, "LVT")
    vgs_h1, id_h1, vgs_h2, id_h2 = extract_iv(hvt_path, "HVT")

    vt_lvt = extract_vt(vgs_l1, id_l1, 0.05)
    vt_hvt = extract_vt(vgs_h1, id_h1, 0.05)
    mw = vt_hvt - vt_lvt

    fig, ax = plt.subplots(figsize=(5.5, 4))

    # LVT state
    if len(vgs_l1) > 0:
        ax.semilogy(vgs_l1, id_l1 * 1e6, "b-",  linewidth=1.5,
                    label=f"LVT, $V_{{DS}}$=0.05 V")
    if len(vgs_l2) > 0:
        ax.semilogy(vgs_l2, id_l2 * 1e6, "b--", linewidth=1.5,
                    label=f"LVT, $V_{{DS}}$=1.0 V")

    # HVT state
    if len(vgs_h1) > 0:
        ax.semilogy(vgs_h1, id_h1 * 1e6, "r-",  linewidth=1.5,
                    label=f"HVT, $V_{{DS}}$=0.05 V")
    if len(vgs_h2) > 0:
        ax.semilogy(vgs_h2, id_h2 * 1e6, "r--", linewidth=1.5,
                    label=f"HVT, $V_{{DS}}$=1.0 V")

    # VT markers
    for vt, color, label in [(vt_lvt, "b", "VT_LVT"), (vt_hvt, "r", "VT_HVT")]:
        if not np.isnan(vt):
            ax.axvline(vt, color=color, linewidth=0.8, linestyle=":",
                       label=f"${label}$={vt:.2f} V")

    ax.set_xlabel("$V_{GS,ext}$ (V)", fontsize=11)
    ax.set_ylabel("$I_D$ (µA)", fontsize=11)
    ax.set_title("HERACLES FeFET $I_D$–$V_{GS}$ (PTM 45nm HP NMOS)", fontsize=11)
    ax.set_xlim([-0.1, 1.6])
    ax.set_ylim([1e-9, None])

    mw_str = f"{mw:.2f} V" if not np.isnan(mw) else "N/A"
    text = (f"$V_T^{{LVT}}$ ≈ {vt_lvt:.2f} V  (exp. 0.35)\n"
            f"$V_T^{{HVT}}$ ≈ {vt_hvt:.2f} V  (exp. 1.40)\n"
            f"Memory window ≈ {mw_str}  (exp. 1.05)")
    ax.text(0.04, 0.97, text, transform=ax.transAxes,
            verticalalignment="top", fontsize=8,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="wheat", alpha=0.8))

    ax.legend(fontsize=8, loc="lower right")
    ax.grid(True, which="both", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, format="pdf", bbox_inches="tight", dpi=150)
    plt.close(fig)

    print(f"  VT_LVT = {vt_lvt:.3f} V (expected ~0.35 V)")
    print(f"  VT_HVT = {vt_hvt:.3f} V (expected ~1.40 V)")
    print(f"  Memory window = {mw_str}")
    print(f"  Saved: {out_path.name}")


def main() -> int:
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    pv_csv  = RAW_DIR / "heracles_pv.csv"
    lvt_csv = RAW_DIR / "fefet_iv_lvt.csv"
    hvt_csv = RAW_DIR / "fefet_iv_hvt.csv"

    ok = True
    print("Phase 4a: Plotting HERACLES characterization results")
    print("=" * 55)

    # P-V loop
    if pv_csv.exists():
        try:
            plot_pv(pv_csv, FIG_DIR / "heracles_pv_loop.pdf")
        except Exception as e:
            print(f"  [ERROR] P-V plot failed: {e}")
            ok = False
    else:
        print(f"  [SKIP] {pv_csv.name} not found — run run_fefet_char.py first")
        ok = False

    # Id-Vgs curves
    if lvt_csv.exists() and hvt_csv.exists():
        try:
            plot_iv(lvt_csv, hvt_csv, FIG_DIR / "fefet_iv_curves.pdf")
        except Exception as e:
            print(f"  [ERROR] Id-Vgs plot failed: {e}")
            ok = False
    else:
        missing = [p.name for p in [lvt_csv, hvt_csv] if not p.exists()]
        print(f"  [SKIP] Missing files: {missing} — run run_fefet_char.py first")
        ok = False

    if ok:
        print("\nAll plots generated successfully.")
        print(f"  results/figures/heracles_pv_loop.pdf")
        print(f"  results/figures/fefet_iv_curves.pdf")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
