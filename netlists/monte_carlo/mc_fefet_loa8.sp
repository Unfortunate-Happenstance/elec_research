* ============================================================
* Monte Carlo Template: FeFET-LOA 8-bit (k=4)
*
* Each FeFET instance has a unique VT offset parameter
* drawn from a distribution. The MC parameter file sets:
*   vt_offset_0 .. vt_offset_3  (for approximate OR gates)
*   vt_offset_and3              (for carry AND gate)
*
* The parameter file is generated externally (Python script)
* and included at simulation time.
*
* Usage:
*   ngspice -b mc_fefet_loa8.sp
*   (with mc_params.inc in the same directory or path adjusted)
*
* FeFET Approximate CiM — IEEE-NANO 2026
* ============================================================

.include '../common/supply.inc'
.include '../../models/cmos45/ptm45_hp.pm'

* ---- FeFET sizing ----
.param wn_fe = 90n
.param wp_fe = 180n
.param lch_fe = 45n
.param wn = 90n
.param wp = 180n
.param lch = 45n

* ============================================================
* Monte Carlo Parameters
* Include file defines per-instance VT offsets.
* Format of mc_params.inc:
*   .param vt_offset_0 = <value>
*   .param vt_offset_1 = <value>
*   .param vt_offset_2 = <value>
*   .param vt_offset_3 = <value>
*   .param vt_offset_and3 = <value>
*   .param mc_iteration = <N>
*
* For nominal run, use default values below.
* For MC sweep, generate mc_params.inc externally.
* ============================================================

* Nominal values match CIRCUIT_VT_NOMINALS in run_monte_carlo.py.
* A_lower = 0b1010 (a3=1, a2=0, a1=1, a0=0):
*   a0=0 → HVT (1.20 V) — OR gate OFF  → s0 = b0
*   a1=1 → LVT (0.12 V) — OR gate ON   → s1 = 1
*   a2=0 → HVT (1.20 V) — OR gate OFF  → s2 = b2
*   a3=1 → LVT (0.12 V) — OR gate ON   → s3 = 1, and3 active
* Overridden per-iteration by MC injection before .control.
.param vt_offset_0    = 1.20
.param vt_offset_1    = 0.12
.param vt_offset_2    = 1.20
.param vt_offset_3    = 0.12
.param vt_offset_and3 = 0.12
.param mc_iteration   = 0

* Uncomment to include MC parameter file:
* .include 'mc_params.inc'

* ============================================================
* FEFET_PARAM subcircuit (inline for MC independence)
* ============================================================
.subckt FEFET_PARAM drain gate_ext source bulk vt_offset=0.12
Vshift gate_ext gate_shifted dc {vt_offset}
Mn1 drain gate_shifted source bulk nmos w={wn_fe} l={lch_fe}
.ends FEFET_PARAM

* ============================================================
* FeFET OR Cell with MC offset
* ============================================================
.subckt FEFET_OR_MC out b_input vdd vss vt_a=0.12
Xfe_pd nor_out vdd vss vss FEFET_PARAM vt_offset={vt_a}
Mn_b nor_out b_input vss vss nmos w={wn} l={lch}
Mp_a nor_mid vdd vdd vdd pmos w={wp} l={lch}
Mp_b nor_out b_input nor_mid vdd pmos w={wp} l={lch}
Mp_inv out nor_out vdd vdd pmos w={wp} l={lch}
Mn_inv out nor_out vss vss nmos w={wn} l={lch}
.ends FEFET_OR_MC

* ============================================================
* FeFET AND Cell with MC offset
* ============================================================
.subckt FEFET_AND_MC out b_input vdd vss vt_a=0.12
Xfe_pd nand_out vdd mid_nd vss FEFET_PARAM vt_offset={vt_a}
Mn_b mid_nd b_input vss vss nmos w={2*wn} l={lch}
Mp_pu1 nand_out vss vdd vdd pmos w={2*wp} l={lch}
Mp_pu2 nand_out b_input vdd vdd pmos w={2*wp} l={lch}
Mp_inv out nand_out vdd vdd pmos w={wp} l={lch}
Mn_inv out nand_out vss vss nmos w={wn} l={lch}
.ends FEFET_AND_MC

* ============================================================
* Standard CMOS Full Adder
* ============================================================
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
* LOA Top-Level with MC parameters
* ============================================================

* Lower 4 bits: FeFET OR with per-instance MC offsets
Xor0 s0 b0 vdd vss FEFET_OR_MC vt_a={vt_offset_0}
Xor1 s1 b1 vdd vss FEFET_OR_MC vt_a={vt_offset_1}
Xor2 s2 b2 vdd vss FEFET_OR_MC vt_a={vt_offset_2}
Xor3 s3 b3 vdd vss FEFET_OR_MC vt_a={vt_offset_3}

* Carry: AND with MC offset
Xand3 c4 b3 vdd vss FEFET_AND_MC vt_a={vt_offset_and3}

* Upper 4 bits: CMOS RCA
XFA4 a4 b4 c4 s4 c5 vdd vss FA
XFA5 a5 b5 c5 s5 c6 vdd vss FA
XFA6 a6 b6 c6 s6 c7 vdd vss FA
XFA7 a7 b7 c7 s7 cout vdd vss FA

* Load capacitances
Cs0 s0 0 {cload}
Cs1 s1 0 {cload}
Cs2 s2 0 {cload}
Cs3 s3 0 {cload}
Cs4 s4 0 {cload}
Cs5 s5 0 {cload}
Cs6 s6 0 {cload}
Cs7 s7 0 {cload}
Ccout cout 0 {cload}

* Input sources
Vb0 b0 0 dc 0
Vb1 b1 0 dc 0
Vb2 b2 0 dc 0
Vb3 b3 0 dc 0
Vb4 b4 0 dc 0
Vb5 b5 0 dc 0
Vb6 b6 0 dc 0
Vb7 b7 0 dc 0
Va4 a4 0 dc 0
Va5 a5 0 dc 0
Va6 a6 0 dc 0
Va7 a7 0 dc 0

.tran 10p {period}

.control
* ============================================================
* Monte Carlo simulation driver
*
* For a single MC iteration:
*   1. Python script generates mc_params.inc with random offsets
*   2. ngspice runs this netlist
*   3. Output measured and recorded
*
* For batch MC:
*   Python loop: for each iteration:
*     - write mc_params.inc
*     - invoke ngspice
*     - collect results
*
* This control block runs a single test vector set.
* ============================================================

* Set upper A bits (exact part)
alter Va4 dc = 1.0
alter Va5 dc = 0
alter Va6 dc = 1.0
alter Va7 dc = 0

* Representative test vectors for B
let num_tests = 8
let test_b = vector(8)
let test_b[0] = 0
let test_b[1] = 15
let test_b[2] = 85
let test_b[3] = 170
let test_b[4] = 255
let test_b[5] = 128
let test_b[6] = 100
let test_b[7] = 50

let idx = 0
dowhile idx < num_tests
  let bval = test_b[idx]

  alter Vb0 dc = (floor(bval) % 2) * 1.0
  alter Vb1 dc = (floor(bval / 2) % 2) * 1.0
  alter Vb2 dc = (floor(bval / 4) % 2) * 1.0
  alter Vb3 dc = (floor(bval / 8) % 2) * 1.0
  alter Vb4 dc = (floor(bval / 16) % 2) * 1.0
  alter Vb5 dc = (floor(bval / 32) % 2) * 1.0
  alter Vb6 dc = (floor(bval / 64) % 2) * 1.0
  alter Vb7 dc = (floor(bval / 128) % 2) * 1.0

  tran 10p 10n
  let idx = idx + 1
end

* Output with MC iteration tag in filename
wrdata results/raw/monte_carlo/mc_loa8_iter.csv v(s0) v(s1) v(s2) v(s3) v(s4) v(s5) v(s6) v(s7) v(cout)

* Measure settled output values at end of period
meas tran s0_val FIND v(s0) AT=9e-9
meas tran s1_val FIND v(s1) AT=9e-9
meas tran s2_val FIND v(s2) AT=9e-9
meas tran s3_val FIND v(s3) AT=9e-9
meas tran s4_val FIND v(s4) AT=9e-9
meas tran s5_val FIND v(s5) AT=9e-9
meas tran s6_val FIND v(s6) AT=9e-9
meas tran s7_val FIND v(s7) AT=9e-9
meas tran cout_val FIND v(cout) AT=9e-9

echo "======================================"
echo "MC FeFET-LOA8 iteration complete"
echo "VT offsets: $&vt_offset_0 $&vt_offset_1 $&vt_offset_2 $&vt_offset_3"
echo "======================================"
.endc

.end
