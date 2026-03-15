* ============================================================
* HERACLES FeFET Id-Vgs Characterization — LVT State
* Phase 4a — FeFET Model Validation
*
* Structure: HERACLES FeCap (te=external gate) in series with
*            PTM 45nm HP NMOS (gate=FeCap bottom electrode be)
*
* Protocol:
*   Phase 1 (t=0..200ns):   Write -5V on Vgs_ext -> programs FeCap
*                            into LVT state (large negative field,
*                            p -> 1, positive spontaneous polarization,
*                            lowers effective MOSFET VT to ~0.35V).
*   Phase 2 (t=400ns..10.4us): Quasi-DC Id-Vgs sweep at Vds=0.05V
*                            (linear/triode region).  Vgs ramps
*                            0 -> 1.5V over 10 us (0.15 V/us).
*   Phase 3 (t=10.6us..20.6us): Same sweep at Vds=1.0V
*                            (saturation region).
*
* FeCap state is preserved throughout: quasi-DC ramp rates are
* orders of magnitude faster than Merz-law switching at Vgs<5V.
*
* Expected results:
*   VT_LVT  ~= 0.35 V  (extrapolated from linear Id-Vgs)
*   ION/IOFF > 1e5 at Vds=1.0V
*
* Run via Docker:
*   docker run --rm -v $(pwd):/workspace docker-ngspice:latest \
*     ngspice -b /workspace/netlists/fefet/char/fefet_iv_lvt.sp
*
* FeFET Approximate CiM — IEEE-NANO 2026
* ============================================================

.include '../../models/cmos45/ptm45_hp.pm'

* ---- Device sizing ----
.param wn_fe = 90n     $ FeFET NMOS width (PTM45 HP)
.param lch_fe = 45n    $ Channel length

* ---- FeCap parameters (same as heracles_pv.sp) ----
.param fecap_area = 625e-12

* ---- Convergence ----
.options RELTOL=1e-4 VNTOL=1e-5 ABSTOL=1e-18 ITL1=1000 ITL4=1000 GMIN=1e-13

* ---- Timing parameters ----
.param t_write  = 200n     $ Write pulse duration
.param t_hold   = 200n     $ Hold/settle before sweep
.param t_sweep  = 10u      $ Quasi-DC sweep duration (0->1.5V in 10us)
.param t_reset  = 200n     $ Reset between sweeps
.param vgs_max  = 1.5      $ Maximum Vgs for sweep [V]
.param v_write  = -5.0     $ Write voltage for LVT: -5V (p->1 -> LVT)

* Derived timing offsets
.param t0_sweep1 = {t_write + t_hold}
.param t1_sweep1 = {t0_sweep1 + t_sweep}
.param t0_sweep2 = {t1_sweep1 + t_reset}
.param t1_sweep2 = {t0_sweep2 + t_sweep}
.param t_total   = {t1_sweep2 + 100n}

* ---- Vgs_ext source (external gate drive) ----
* Phase 1: write -5V to program LVT
* Phase 2: ramp 0 -> 1.5V (Vds=0.05V sweep)
* Phase 3: ramp 0 -> 1.5V (Vds=1.0V sweep)
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

* ---- Vds source ----
* 0V during write, 0.05V during sweep 1, 1.0V during sweep 2
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

* ---- Zero-volt ammeter on te (measures FeCap current) ----
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
* gate=gate_int (FeCap bottom electrode drives MOSFET gate)
* drain=vd_node, source=0 (bulk tied to source)
Mn1 vd_node gate_int 0 0 nmos w={wn_fe} l={lch_fe}

* Load capacitance on drain (realistic fanout)
Cload vd_node 0 1f

* ---- Transient ----
.tran 1n {t_total}

.control
pre_osdi /workspace/models/fefet/heracles/heracles.osdi

run

* Save full waveform: time, v_gs_ext, v_gate_int, v_drain, i_drain
* Python extracts two Id-Vgs sweeps by time-windowing
* Sweep 1: t=[t0_sweep1, t1_sweep1], Vds=0.05V
* Sweep 2: t=[t0_sweep2, t1_sweep2], Vds=1.0V
wrdata results/raw/fefet/fefet_iv_lvt.csv time v(vgs_ext) v(gate_int) v(vd_node) i(Vds_src)

echo "======================================"
echo "FeFET Id-Vgs LVT characterization complete"
echo "Output: results/raw/fefet/fefet_iv_lvt.csv"
echo "Columns: time [s], vgs_ext [V], vgate_int [V], vd [V], id_src [A]"
echo "Note: Id = -i(Vds_src)  (SPICE sign convention)"
echo "Sweep 1 window: Vds=0.05V"
echo "Sweep 2 window: Vds=1.0V"
echo "Expected: VT_LVT ~= 0.35 V"
echo "======================================"
.endc

.end
