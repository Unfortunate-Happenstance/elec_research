* ============================================================
* HERACLES HZO FeCap P-V Hysteresis Loop Characterization
* Phase 4a — FeFET Model Validation
*
* Drives a standalone HZO FeCap with a 50 kHz triangular wave
* and records the FeCap current to extract polarization P.
*
* Polarization extracted by Python post-processing:
*   P(t) = (1/area) * integral_0^t [ I(Vmeas) ] dt
*   (minus linear dielectric correction: eps0*eps_fe/t_fe * V_fe)
*
* Expected results (HERACLES default params):
*   Remnant polarization  Pr  ~= 0.27 C/m^2
*   Coercive voltage      Vc  ~= 0.20 V  (= e_off * t_fe = 2e7 * 9.8e-9)
*
* Run via Docker (from elec_research root):
*   docker run --rm -v $(pwd):/workspace docker-ngspice:latest \
*     ngspice -b /workspace/netlists/fefet/char/heracles_pv.sp
*
* FeFET Approximate CiM — IEEE-NANO 2026
* ============================================================

* ---- Simulation parameters ----
.param fecap_area = 625e-12   $ HZO capacitor area [m^2] (25x25 um^2)
.param freq       = 50e3      $ Triangular wave frequency [Hz]
.param period     = {1/freq}  $ = 20 us
.param t_sim      = {3*period} $ 3 full cycles = 60 us
.param amp        = 5.0       $ Peak voltage [V]
.param tstep      = 10n       $ Transient timestep

* ---- Convergence ----
.options RELTOL=1e-4 VNTOL=1e-5 ABSTOL=1e-18 ITL1=1000 ITL4=1000 GMIN=1e-13

* ---- Triangular wave drive ----
* Start at -amp, rise to +amp at T/2, fall to -amp at T, repeat x3
Vdrive te_drive 0 PWL(
+  0              {-amp}
+  {0.5*period}   {amp}
+  {period}       {-amp}
+  {1.5*period}   {amp}
+  {2*period}     {-amp}
+  {2.5*period}   {amp}
+  {3*period}     {-amp}
+ )

* ---- Zero-volt ammeter in series with te ----
* I(Vmeas) = current flowing into the top electrode (te)
* This captures: polarization switching current + displacement current + leakage
Vmeas te_drive te_int dc 0

* ---- HERACLES HZO FeCap model card ----
* ngspice XSPICE/OSDI: parameters go in .model, NOT inline on the A-element line.
* Port brackets [te] [be] are required for XSPICE A-devices.
*
* area    [m^2]: 625e-12 (25x25 um^2)
* t_fe    [m]:   9.8e-9  (HZO ferroelectric layer thickness)
* t_int   [m]:   1.5e-9  (interface / dead layer thickness)
* eps_fe  [1]:   70      (HZO relative permittivity)
* eps_int [1]:   90      (interface layer permittivity)
* p_s     [C/m^2]: 0.27  (saturation polarization density)
* e_off   [V/m]: 2e7     (offset E-field => Vc = e_off*t_fe = 0.196 V)
* w_b     [eV]:  1.05    (Merz-law energy barrier height)
* d_e     [m]:   7.5e-9  (ion displacement parameter)
.model hze_cap heracles
+  area=625e-12  t_fe=9.8e-9    t_int=1.5e-9
+  eps_fe=70     eps_int=90     p_s=27e-2
+  e_off=2e7     w_b=1.05       d_e=7.5e-9
+  n_depl=1.05e28  eps_depl=3.6
+  q_fix_depl_u=-9.8e-2  q_fix_depl_d=9.8e-2

Acfe %v [te_int] %v [be_node] hze_cap

* ---- Ground the bottom electrode ----
* 1 Ohm prevents floating node; negligible voltage drop
Rbe be_node 0 1

* ---- Transient analysis ----
* Run 3 full cycles; first cycle may show initial-state transient,
* cycles 2 and 3 give the saturated (repeatable) hysteresis loop.
.tran {tstep} {t_sim}

.control
* Load HERACLES OSDI model before running
pre_osdi /workspace/models/fefet/heracles/heracles.osdi

run

* Save: time, top-electrode voltage, bottom-electrode voltage,
*       FeCap current (into te)
* Python extracts: V_fe = v(te_int)-v(be_node), P = integ(i_fe)/area
wrdata results/raw/fefet/heracles_pv.csv time v(te_int) v(be_node) i(Vmeas)

echo "======================================"
echo "HERACLES P-V characterization complete"
echo "Output: results/raw/fefet/heracles_pv.csv"
echo "Columns: time [s], v_te [V], v_be [V], i_fe [A]"
echo "Post-process: P = integ(i_fe)/625e-12 C/m^2"
echo "Expected: Pr ~= 0.27 C/m^2, Vc ~= 0.20 V"
echo "======================================"
.endc

.end
