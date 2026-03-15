* ============================================================
* HERACLES FeFET Id-Vgs Characterization — HVT State
* Phase 4a — FeFET Model Validation
*
* Identical structure to fefet_iv_lvt.sp but with opposite
* write polarity: +5V on Vgs_ext programs the FeCap into
* HVT state (p -> 0, zero/negative spontaneous polarization,
* raises effective MOSFET VT to ~1.40V).
*
* Protocol:
*   Phase 1 (t=0..200ns):   Write +5V on Vgs_ext -> HVT state
*   Phase 2 (t=400ns..10.4us): Quasi-DC Id-Vgs sweep, Vds=0.05V
*   Phase 3 (t=10.6us..20.6us): Quasi-DC Id-Vgs sweep, Vds=1.0V
*
* Expected results:
*   VT_HVT  ~= 1.40 V   (VT0 + Vshift_hvt = 0.47 + 0.93)
*   Memory window  MW = VT_HVT - VT_LVT ~= 1.05 V
*
* Run via Docker:
*   docker run --rm -v $(pwd):/workspace docker-ngspice:latest \
*     ngspice -b /workspace/netlists/fefet/char/fefet_iv_hvt.sp
*
* FeFET Approximate CiM — IEEE-NANO 2026
* ============================================================

.include '../../models/cmos45/ptm45_hp.pm'

* ---- Device sizing ----
.param wn_fe = 90n
.param lch_fe = 45n

* ---- Convergence ----
.options RELTOL=1e-4 VNTOL=1e-5 ABSTOL=1e-18 ITL1=1000 ITL4=1000 GMIN=1e-13

* ---- Timing ----
.param t_write  = 200n
.param t_hold   = 200n
.param t_sweep  = 10u
.param t_reset  = 200n
.param vgs_max  = 1.5
.param v_write  = 5.0      $ Write voltage for HVT: +5V (p->0 -> HVT)

.param t0_sweep1 = {t_write + t_hold}
.param t1_sweep1 = {t0_sweep1 + t_sweep}
.param t0_sweep2 = {t1_sweep1 + t_reset}
.param t1_sweep2 = {t0_sweep2 + t_sweep}
.param t_total   = {t1_sweep2 + 100n}

* ---- Vgs_ext: write +5V then sweep ----
Vgs_ext vgs_ext 0 PWL(
+  0                 {v_write}
+  {t_write}         {v_write}
+  {t_write+1n}      0
+  {t0_sweep1}       0
+  {t1_sweep1}       {vgs_max}
+  {t1_sweep1+1n}    0
+  {t0_sweep2}       0
+  {t1_sweep2}       {vgs_max}
+  {t_total}         {vgs_max}
+ )

* ---- Vds: 0V during write, 0.05V sweep 1, 1.0V sweep 2 ----
Vds_src vd_node 0 PWL(
+  0                 0
+  {t_write+1n}      0
+  {t0_sweep1}       0.05
+  {t1_sweep1}       0.05
+  {t1_sweep1+1n}    0
+  {t0_sweep2-1n}    0
+  {t0_sweep2}       1.0
+  {t1_sweep2}       1.0
+  {t_total}         1.0
+ )

* ---- Ammeter on te ----
Vmeas_te vgs_ext te_int dc 0

* ---- HERACLES FeCap model + element ----
* ngspice XSPICE/OSDI: parameters go in .model; element line uses [port] brackets.
* te = te_int (top electrode, driven by Vgs_ext)
* be = gate_int (bottom electrode = MOSFET gate node)
.model hze_cap heracles
+  area=625e-12  t_fe=9.8e-9    t_int=1.5e-9
+  eps_fe=70     eps_int=90     p_s=27e-2
+  e_off=2e7     w_b=1.05       d_e=7.5e-9
+  n_depl=1.05e28  eps_depl=3.6
+  q_fix_depl_u=-9.8e-2  q_fix_depl_d=9.8e-2

Acfe %v [te_int] %v [gate_int] hze_cap

* ---- PTM 45nm HP NMOS ----
Mn1 vd_node gate_int 0 0 nmos w={wn_fe} l={lch_fe}

Cload vd_node 0 1f

.tran 1n {t_total}

.control
pre_osdi /workspace/models/fefet/heracles/heracles.osdi

run

wrdata results/raw/fefet/fefet_iv_hvt.csv time v(vgs_ext) v(gate_int) v(vd_node) i(Vds_src)

echo "======================================"
echo "FeFET Id-Vgs HVT characterization complete"
echo "Output: results/raw/fefet/fefet_iv_hvt.csv"
echo "Columns: time [s], vgs_ext [V], vgate_int [V], vd [V], id_src [A]"
echo "Note: Id = -i(Vds_src)"
echo "Sweep 1 window: Vds=0.05V"
echo "Sweep 2 window: Vds=1.0V"
echo "Expected: VT_HVT ~= 1.40 V"
echo "======================================"
.endc

.end
