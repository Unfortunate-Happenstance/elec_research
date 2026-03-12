* ============================================================
* Monte Carlo Template: FeFET-BAM 4x4 Broken Array Multiplier
*
* Each FeFET AND gate (partial product) has a unique VT offset
* drawn from a distribution. The MC parameter file sets:
*   vt_offset_a0 .. vt_offset_a3  (per A-bit FeFET)
*
* In the BAM, each a[i] is used in multiple AND gates.
* The VT variation is per-a[i] FeFET, not per-product.
*
* FeFET Approximate CiM — IEEE-NANO 2026
* ============================================================

.include '../common/supply.inc'
.include '../../models/cmos45/ptm45_hp.pm'

* Convergence options — needed for ratioed FeFET pull-up topology
.options RELTOL=1e-3 VNTOL=1e-3 ABSTOL=1e-12 GMIN=1e-9 ITL1=500 ITL4=500

* ---- Sizing ----
.param wn_fe = 90n
.param wp_fe = 180n
.param lch_fe = 45n
.param wn = 90n
.param wp = 180n
.param lch = 45n

* ============================================================
* Monte Carlo Parameters (defaults, overridden by include)
* Per-row VT offsets (each a[i] row has its own FeFET variation)
* ============================================================
* Nominal values match CIRCUIT_VT_NOMINALS in run_monte_carlo.py.
* A = 0b1010 = 10 (4-bit): a0=0(HVT), a1=1(LVT), a2=0(HVT), a3=1(LVT)
* Partial products from HVT rows (a0, a2) are suppressed at nominal;
* variability can accidentally enable them → computable error metric.
* Overridden per-iteration by MC injection before .control.
.param vt_offset_a0 = 1.20
.param vt_offset_a1 = 0.12
.param vt_offset_a2 = 1.20
.param vt_offset_a3 = 0.12
.param mc_iteration = 0

* Uncomment to include MC parameter file:
* .include 'mc_params.inc'

* ============================================================
* Subcircuit definitions
* ============================================================

.subckt FEFET_PARAM drain gate_ext source bulk vt_offset=0.12
Vshift gate_ext gate_shifted dc {vt_offset}
Mn1 drain gate_shifted source bulk nmos w={wn_fe} l={lch_fe}
.ends FEFET_PARAM

* FeFET AND for partial products
.subckt FEFET_AND_PP out b_input vdd vss vt_a=0.12
Xfe_pd nand_out vdd mid_nd vss FEFET_PARAM vt_offset={vt_a}
Mn_b mid_nd b_input vss vss nmos w={2*wn} l={lch}
Mp_pu1 nand_out vss vdd vdd pmos w={wn} l={4*lch}  $ weak keeper (16x weaker than original)
Mp_pu2 nand_out b_input vdd vdd pmos w={2*wp} l={lch}
Mp_inv out nand_out vdd vdd pmos w={wp} l={lch}
Mn_inv out nand_out vss vss nmos w={wn} l={lch}
.ends FEFET_AND_PP

* Half Adder
.subckt HA A B Sum Cout vdd vss
Mp_ainv Abar A vdd vdd pmos w={wp} l={lch}
Mn_ainv Abar A vss vss nmos w={wn} l={lch}
Mp_binv Bbar B vdd vdd pmos w={wp} l={lch}
Mn_binv Bbar B vss vss nmos w={wn} l={lch}
Mn_tg1 Sum B Abar vss nmos w={wn} l={lch}
Mp_tg1 Sum B A vdd pmos w={wp} l={lch}
Mn_tg2 Sum Bbar A vss nmos w={wn} l={lch}
Mp_tg2 Sum Bbar Abar vdd pmos w={wp} l={lch}
* AND
Mn_and1 Cout_bar A vdd vdd pmos w={wp} l={lch}
Mp_and1 Cout_bar B vdd vdd pmos w={wp} l={lch}
Mn_and2 Cout_bar A mid_and vss nmos w={wn} l={lch}
Mn_and3 mid_and B vss vss nmos w={wn} l={lch}
Mp_cinv Cout Cout_bar vdd vdd pmos w={wp} l={lch}
Mn_cinv Cout Cout_bar vss vss nmos w={wn} l={lch}
.ends HA

* Full Adder
.subckt FA A B Cin Sum Cout vdd vss
Mp_ainv Abar A vdd vdd pmos w={wp} l={lch}
Mn_ainv Abar A vss vss nmos w={wn} l={lch}
Mp_binv Bbar B vdd vdd pmos w={wp} l={lch}
Mn_binv Bbar B vss vss nmos w={wn} l={lch}
Mn_tg1 P B Abar vss nmos w={wn} l={lch}
Mp_tg1 P B A vdd pmos w={wp} l={lch}
Mn_tg2 P Bbar A vss nmos w={wn} l={lch}
Mp_tg2 P Bbar Abar vdd pmos w={wp} l={lch}
Mp_pinv Pbar P vdd vdd pmos w={wp} l={lch}
Mn_pinv Pbar P vss vss nmos w={wn} l={lch}
Mn_tg3 Sum Cin Pbar vss nmos w={wn} l={lch}
Mp_tg3 Sum Cin P vdd pmos w={wp} l={lch}
Mp_cinv Cinbar Cin vdd vdd pmos w={wp} l={lch}
Mn_cinv Cinbar Cin vss vss nmos w={wn} l={lch}
Mn_tg4 Sum Cinbar P vss nmos w={wn} l={lch}
Mp_tg4 Sum Cinbar Pbar vdd pmos w={wp} l={lch}
Mn_c1 Cout_int A vss vss nmos w={wn} l={lch}
Mn_c2 Cout_int B Cout_int1 vss nmos w={wn} l={lch}
Mn_c3 Cout_int1 Cin vss vss nmos w={wn} l={lch}
Mn_c4 Cout_int P Cout_int1 vss nmos w={wn} l={lch}
Mp_c1 Cout_int Abar vdd vdd pmos w={wp} l={lch}
Mp_c2 Cout_int Bbar Cout_int2 vdd pmos w={wp} l={lch}
Mp_c3 Cout_int2 Cinbar vdd vdd pmos w={wp} l={lch}
Mp_c4 Cout_int2 Pbar Cout_int2 vdd pmos w={wp} l={lch}
Mp_coutinv Cout Cout_int vdd vdd pmos w={wp} l={lch}
Mn_coutinv Cout Cout_int vss vss nmos w={wn} l={lch}
.ends FA

* ============================================================
* BAM Top-Level with MC parameters
* ============================================================

* Partial Products (kept: i+j >= 2)
* Row 0 (a[0]): pp02, pp03
Xpp02 pp02 b2 vdd vss FEFET_AND_PP vt_a={vt_offset_a0}
Xpp03 pp03 b3 vdd vss FEFET_AND_PP vt_a={vt_offset_a0}

* Row 1 (a[1]): pp11, pp12, pp13
Xpp11 pp11 b1 vdd vss FEFET_AND_PP vt_a={vt_offset_a1}
Xpp12 pp12 b2 vdd vss FEFET_AND_PP vt_a={vt_offset_a1}
Xpp13 pp13 b3 vdd vss FEFET_AND_PP vt_a={vt_offset_a1}

* Row 2 (a[2]): pp20, pp21, pp22, pp23
Xpp20 pp20 b0 vdd vss FEFET_AND_PP vt_a={vt_offset_a2}
Xpp21 pp21 b1 vdd vss FEFET_AND_PP vt_a={vt_offset_a2}
Xpp22 pp22 b2 vdd vss FEFET_AND_PP vt_a={vt_offset_a2}
Xpp23 pp23 b3 vdd vss FEFET_AND_PP vt_a={vt_offset_a2}

* Row 3 (a[3]): pp30, pp31, pp32, pp33
Xpp30 pp30 b0 vdd vss FEFET_AND_PP vt_a={vt_offset_a3}
Xpp31 pp31 b1 vdd vss FEFET_AND_PP vt_a={vt_offset_a3}
Xpp32 pp32 b2 vdd vss FEFET_AND_PP vt_a={vt_offset_a3}
Xpp33 pp33 b3 vdd vss FEFET_AND_PP vt_a={vt_offset_a3}

* Skipped bits
Vp0 p0 0 dc 0
Vp1 p1 0 dc 0

* Adder tree
* Column 2: pp02 + pp11 + pp20
XFA_c2 pp02 pp11 pp20 p2 cc2 vdd vss FA

* Column 3: pp03 + pp12 + pp21 + pp30 + cc2
XHA_c3a pp03 pp12 s3a cc3a vdd vss HA
XFA_c3b pp21 pp30 cc2 s3b cc3b vdd vss FA
XHA_c3c s3a s3b p3 cc3c vdd vss HA

* Column 4: pp13 + pp22 + pp31 + cc3a + cc3b + cc3c
XFA_c4a pp13 pp22 pp31 s4a cc4a vdd vss FA
XFA_c4b cc3a cc3b cc3c s4b cc4b vdd vss FA
XHA_c4c s4a s4b p4 cc4c vdd vss HA

* Column 5: pp23 + pp32 + cc4a + cc4b + cc4c
XFA_c5a pp23 pp32 cc4a s5a cc5a vdd vss FA
XHA_c5b cc4b cc4c s5b cc5b vdd vss HA
XHA_c5c s5a s5b p5 cc5c vdd vss HA

* Column 6: pp33 + cc5a + cc5b + cc5c
XFA_c6 pp33 cc5a cc5b s6a cc6a vdd vss FA
XHA_c6b s6a cc5c p6 cc6b vdd vss HA

* Column 7: cc6a + cc6b
XHA_c7 cc6a cc6b p7 p8_overflow vdd vss HA

* Load capacitances
Cp0 p0 0 {cload}
Cp1 p1 0 {cload}
Cp2 p2 0 {cload}
Cp3 p3 0 {cload}
Cp4 p4 0 {cload}
Cp5 p5 0 {cload}
Cp6 p6 0 {cload}
Cp7 p7 0 {cload}

* Input sources
Vb0 b0 0 dc 0
Vb1 b1 0 dc 0
Vb2 b2 0 dc 0
Vb3 b3 0 dc 0

.tran 10p {period}
* Initial conditions: all product outputs start at 0.
* Used with UIC in tran to bypass DCOP for this ratioed-pull-up topology.
.ic v(p0)=0 v(p1)=0 v(p2)=0 v(p3)=0 v(p4)=0 v(p5)=0 v(p6)=0 v(p7)=0

.control
* Single test vector: B=15 (all ones) with A=0b1010 stored in FeFETs.
* meas tran uses the most recent tran dataset, so running one vector
* is equivalent to using the last vector of the original 16-iteration loop.
* B=15 = all b-bits high → maximum sensitivity to FeFET VT variability.
alter Vb0 dc = 1.0
alter Vb1 dc = 1.0
alter Vb2 dc = 1.0
alter Vb3 dc = 1.0

tran 10p 10n uic

wrdata results/raw/monte_carlo/mc_bam4x4_iter.csv v(p0) v(p1) v(p2) v(p3) v(p4) v(p5) v(p6) v(p7)

meas tran p0_val FIND v(p0) AT=9e-9
meas tran p1_val FIND v(p1) AT=9e-9
meas tran p2_val FIND v(p2) AT=9e-9
meas tran p3_val FIND v(p3) AT=9e-9
meas tran p4_val FIND v(p4) AT=9e-9
meas tran p5_val FIND v(p5) AT=9e-9
meas tran p6_val FIND v(p6) AT=9e-9
meas tran p7_val FIND v(p7) AT=9e-9

echo "======================================"
echo "MC FeFET-BAM 4x4 iteration complete"
echo "VT offsets: a0=$&vt_offset_a0 a1=$&vt_offset_a1 a2=$&vt_offset_a2 a3=$&vt_offset_a3"
echo "======================================"
.endc

.end
