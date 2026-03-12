* ============================================================
* Monte Carlo Template: FeFET-HEAA 8-bit (k=4)
*
* Each FeFET instance has a unique VT offset parameter
* drawn from a distribution. The MC parameter file sets:
*   vt_offset_0 .. vt_offset_3  (for approximate/boundary FeFETs)
*   vt_offset_and2, vt_offset_and3, vt_offset_xor3
*
* FeFET Approximate CiM — IEEE-NANO 2026
* ============================================================

.include '../common/supply.inc'
.include '../../models/cmos45/ptm45_hp.pm'

* ---- Sizing ----
.param wn_fe = 90n
.param wp_fe = 180n
.param lch_fe = 45n
.param wn = 90n
.param wp = 180n
.param lch = 45n

* ============================================================
* Monte Carlo Parameters (defaults, overridden by include)
* ============================================================
* Nominal values match CIRCUIT_VT_NOMINALS in run_monte_carlo.py.
* A_lower = 0b1010 (a3=1, a2=0, a1=1, a0=0):
*   a0=0 → HVT (1.20 V),  a1=1 → LVT (0.12 V)
*   a2=0 → HVT (1.20 V),  a3=1 → LVT (0.12 V)
*   and2 gate follows a2=0 → HVT; and3/xor3 follow a3=1 → LVT
* Overridden per-iteration by MC injection before .control.
.param vt_offset_0    = 1.20
.param vt_offset_1    = 0.12
.param vt_offset_2    = 1.20
.param vt_offset_3    = 0.12
.param vt_offset_and2 = 1.20
.param vt_offset_and3 = 0.12
.param vt_offset_xor3 = 0.12
.param mc_iteration   = 0

* Uncomment to include MC parameter file:
* .include 'mc_params.inc'

* ============================================================
* Subcircuit definitions
* ============================================================

.subckt FEFET_PARAM drain gate_ext source bulk vt_offset=0.12
Vshift gate_ext gate_shifted dc {vt_offset}
Mn1 drain gate_shifted source bulk nmos w={wn_fe} l={lch_fe}
.ends FEFET_PARAM

* FeFET OR Cell
.subckt FEFET_OR_MC out b_input vdd vss vt_a=0.12
Xfe_pd nor_out vdd vss vss FEFET_PARAM vt_offset={vt_a}
Mn_b nor_out b_input vss vss nmos w={wn} l={lch}
Mp_a nor_mid vdd vdd vdd pmos w={wp} l={lch}
Mp_b nor_out b_input nor_mid vdd pmos w={wp} l={lch}
Mp_inv out nor_out vdd vdd pmos w={wp} l={lch}
Mn_inv out nor_out vss vss nmos w={wn} l={lch}
.ends FEFET_OR_MC

* FeFET AND Cell
.subckt FEFET_AND_MC out b_input vdd vss vt_a=0.12
Xfe_pd nand_out vdd mid_nd vss FEFET_PARAM vt_offset={vt_a}
Mn_b mid_nd b_input vss vss nmos w={2*wn} l={lch}
Mp_pu1 nand_out vss vdd vdd pmos w={2*wp} l={lch}
Mp_pu2 nand_out b_input vdd vdd pmos w={2*wp} l={lch}
Mp_inv out nand_out vdd vdd pmos w={wp} l={lch}
Mn_inv out nand_out vss vss nmos w={wn} l={lch}
.ends FEFET_AND_MC

* FeFET XOR Cell
.subckt FEFET_XOR_MC out b_input vdd vss vt_a=0.12
Mp_sens a_sense vss vdd vdd pmos w={wp} l={lch}
Xfe_s a_sense vdd mid_s vss FEFET_PARAM vt_offset={vt_a}
Rmid mid_s vss 1k
Mp_sinv a_sense_bar a_sense vdd vdd pmos w={wp} l={lch}
Mn_sinv a_sense_bar a_sense vss vss nmos w={wn} l={lch}
Mp_binv b_bar b_input vdd vdd pmos w={wp} l={lch}
Mn_binv b_bar b_input vss vss nmos w={wn} l={lch}
Mn_tg1 out b_input a_sense_bar vss nmos w={wn} l={lch}
Mp_tg1 out b_input a_sense vdd pmos w={wp} l={lch}
Mn_tg2 out b_bar a_sense vss nmos w={wn} l={lch}
Mp_tg2 out b_bar a_sense_bar vdd pmos w={wp} l={lch}
.ends FEFET_XOR_MC

* 2:1 MUX
.subckt MUX2 out in0 in1 sel vdd vss
Mp_sinv sel_bar sel vdd vdd pmos w={wp} l={lch}
Mn_sinv sel_bar sel vss vss nmos w={wn} l={lch}
Mn_m0 out in0 sel_bar vss nmos w={wn} l={lch}
Mp_m0 out in0 sel vdd pmos w={wp} l={lch}
Mn_m1 out in1 sel vss nmos w={wn} l={lch}
Mp_m1 out in1 sel_bar vdd pmos w={wp} l={lch}
.ends MUX2

* Standard Full Adder
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
* HEAA Top-Level with MC parameters
* ============================================================

* Bits [2:0]: FeFET OR (approximate)
Xor0 s0 b0 vdd vss FEFET_OR_MC vt_a={vt_offset_0}
Xor1 s1 b1 vdd vss FEFET_OR_MC vt_a={vt_offset_1}
Xor2 s2 b2 vdd vss FEFET_OR_MC vt_a={vt_offset_2}

* Boundary bit [3]: carry_lower, XOR, MUX
Xand2 carry_lower b2 vdd vss FEFET_AND_MC vt_a={vt_offset_and2}
Xxor3 sum3_exact b3 vdd vss FEFET_XOR_MC vt_a={vt_offset_xor3}
Mp_s3inv sum3_plus1 sum3_exact vdd vdd pmos w={wp} l={lch}
Mn_s3inv sum3_plus1 sum3_exact vss vss nmos w={wn} l={lch}
Xmux3 s3 sum3_exact sum3_plus1 carry_lower vdd vss MUX2

* Carry into exact part
Xand3 carry_gen3 b3 vdd vss FEFET_AND_MC vt_a={vt_offset_and3}
Mp_cp_pu carry_prop3_bar sum3_exact vdd vdd pmos w={wp} l={lch}
Mp_cp_pu2 carry_prop3_bar carry_lower vdd vdd pmos w={wp} l={lch}
Mn_cp_pd1 carry_prop3_bar sum3_exact mid_cp vss nmos w={wn} l={lch}
Mn_cp_pd2 mid_cp carry_lower vss vss nmos w={wn} l={lch}
Mp_cpinv carry_prop3 carry_prop3_bar vdd vdd pmos w={wp} l={lch}
Mn_cpinv carry_prop3 carry_prop3_bar vss vss nmos w={wn} l={lch}

* c4 = carry_gen3 | carry_prop3
Mp_or_pu1 c4_bar carry_gen3 vdd vdd pmos w={wp} l={lch}
Mp_or_pu2 c4_bar carry_prop3 c4_mid vdd pmos w={wp} l={lch}
Rormid c4_mid vdd 100
Mn_or_pd1 c4_bar carry_gen3 vss vss nmos w={wn} l={lch}
Mn_or_pd2 c4_bar carry_prop3 vss vss nmos w={wn} l={lch}
Mp_c4inv c4 c4_bar vdd vdd pmos w={wp} l={lch}
Mn_c4inv c4 c4_bar vss vss nmos w={wn} l={lch}

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
* Set upper A bits
alter Va4 dc = 1.0
alter Va5 dc = 0
alter Va6 dc = 1.0
alter Va7 dc = 0

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

wrdata results/raw/monte_carlo/mc_heaa8_iter.csv v(s0) v(s1) v(s2) v(s3) v(s4) v(s5) v(s6) v(s7) v(cout)

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
echo "MC FeFET-HEAA8 iteration complete"
echo "VT offsets: $&vt_offset_0 $&vt_offset_1 $&vt_offset_2 $&vt_offset_3"
echo "Boundary offsets: and2=$&vt_offset_and2 and3=$&vt_offset_and3 xor3=$&vt_offset_xor3"
echo "======================================"
.endc

.end
