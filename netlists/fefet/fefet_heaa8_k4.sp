* ============================================================
* FeFET-HEAA: 8-bit Hybrid Error-tolerant Approximate Adder
* with Boundary Correction (k=4)
*
* Architecture:
*   Bits [2:0] — Approximate part (FeFET OR gates)
*     s[i] = a_stored[i] | b_input[i]  for i=0..2
*   Bit [3]   — Boundary correction
*     carry_approx = a_stored[3] & b_input[3]
*     sum3_exact   = a_stored[3] XOR b_input[3]
*     sum3_plus1   = NOT(a_stored[3] XOR b_input[3])
*     MUX: s[3] = carry_lower ? sum3_plus1 : sum3_exact
*     carry_lower  = a_stored[2] & b_input[2]
*     c4 = carry_approx | (sum3_exact & carry_lower)
*   Bits [7:4] — Exact part (standard CMOS RCA)
*     4-bit ripple carry adder with c4 as carry-in
*
* Operand A[7:0] stored in FeFET VT states
* Operand B[7:0] applied as voltage inputs
*
* PTM 45nm HP BSIM4 models
* FeFET Approximate CiM — IEEE-NANO 2026
* ============================================================

.include '../common/supply.inc'
.include '../../models/cmos45/ptm45_hp.pm'
.include 'fefet_subckt.inc'

.param wn = 90n    $ NMOS width
.param wp = 180n   $ PMOS width
.param lch = 45n    $ Channel length

* Convergence options — ratioed pseudo-nMOS FeFET AND cell
.options RELTOL=1e-3 VNTOL=1e-3 ABSTOL=1e-12 GMIN=1e-9 ITL1=500 ITL4=500

* ============================================================
* FeFET OR Cell (same as LOA)
* ============================================================
.subckt FEFET_OR_CELL out b_input vdd vss vt_a=0.12
* Parallel pull-down: FeFET(A) || NMOS(B)
Xfe_pd nor_out vdd vss vss FEFET_PARAM vt_offset={vt_a}
Mn_b nor_out b_input vss vss nmos w={wn} l={lch}
* Series pull-up: PMOS(A_sense) + PMOS(B)
* Simplified: use complementary structure
Mp_a nor_mid vdd vdd vdd pmos w={wp} l={lch}
Mp_b nor_out b_input nor_mid vdd pmos w={wp} l={lch}
* OR = NOT(NOR)
Mp_inv out nor_out vdd vdd pmos w={wp} l={lch}
Mn_inv out nor_out vss vss nmos w={wn} l={lch}
.ends FEFET_OR_CELL

* ============================================================
* FeFET AND Cell
* ============================================================
.subckt FEFET_AND_CELL out b_input vdd vss vt_a=0.12
* Series pull-down: FeFET(A) + NMOS(B)
Xfe_pd nand_out vdd mid_nd vss FEFET_PARAM vt_offset={vt_a}
Mn_b mid_nd b_input vss vss nmos w={2*wn} l={lch}
* Parallel pull-up
Mp_pk  nand_out vss vdd vdd pmos w={wn}       l={4*lch}  $ weak keeper: drive ratio ~8x vs pull-down
Mp_pu2 nand_out b_input vdd vdd pmos w={2*wp} l={lch}
* AND = NOT(NAND)
Mp_inv out nand_out vdd vdd pmos w={wp} l={lch}
Mn_inv out nand_out vss vss nmos w={wn} l={lch}
.ends FEFET_AND_CELL

* ============================================================
* FeFET XOR Cell (for boundary bit)
* Uses TG approach: sense A from FeFET, XOR with B
* ============================================================
.subckt FEFET_XOR_CELL out b_input vdd vss vt_a=0.12
* Sense stored A: FeFET with vdd at gate
* a_sense is high when A=1(LVT), low when A=0(HVT)
Mp_sens a_sense vss vdd vdd pmos w={wp} l={lch}
Xfe_s a_sense vdd mid_s vss FEFET_PARAM vt_offset={vt_a}
Rmid mid_s vss 1k
Mp_sinv a_sense_bar a_sense vdd vdd pmos w={wp} l={lch}
Mn_sinv a_sense_bar a_sense vss vss nmos w={wn} l={lch}

* B complement
Mp_binv b_bar b_input vdd vdd pmos w={wp} l={lch}
Mn_binv b_bar b_input vss vss nmos w={wn} l={lch}

* TG XOR: pass B when A=0, pass Bbar when A=1
Mn_tg1 out a_sense_bar b_input vss nmos w={wn} l={lch}
Mp_tg1 out a_sense b_input vdd pmos w={wp} l={lch}
Mn_tg2 out a_sense b_bar vss nmos w={wn} l={lch}
Mp_tg2 out a_sense_bar b_bar vdd pmos w={wp} l={lch}
.ends FEFET_XOR_CELL

* ============================================================
* 2:1 MUX
* out = sel ? in1 : in0
* ============================================================
.subckt MUX2 out in0 in1 sel vdd vss
Mp_sinv sel_bar sel vdd vdd pmos w={wp} l={lch}
Mn_sinv sel_bar sel vss vss nmos w={wn} l={lch}
* TG0: pass in0 when sel=0 (sel_bar=1)
Mn_m0 out in0 sel_bar vss nmos w={wn} l={lch}
Mp_m0 out in0 sel vdd pmos w={wp} l={lch}
* TG1: pass in1 when sel=1
Mn_m1 out in1 sel vss nmos w={wn} l={lch}
Mp_m1 out in1 sel_bar vdd pmos w={wp} l={lch}
.ends MUX2

* ============================================================
* Standard CMOS Full Adder (for exact upper bits)
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
* Cout — corrected topology: (A·B) + (Cin·P)
* NMOS pull-down: (A series B) | (Cin series P)
Mn_ca Cout_int A   Cout_ab  vss nmos w={wn} l={lch}
Mn_cb Cout_ab  B   vss      vss nmos w={wn} l={lch}
Mn_cc Cout_int Cin Cout_cp  vss nmos w={wn} l={lch}
Mn_cp Cout_cp  P   vss      vss nmos w={wn} l={lch}
* PMOS pull-up: (A||B) series (Cin||P)  [non-inverted gates — PMOS ON when signal LOW]
Mp_pa Cout_top A   vdd      vdd pmos w={wp} l={lch}
Mp_pb Cout_top B   vdd      vdd pmos w={wp} l={lch}
Mp_pc Cout_int Cin Cout_top vdd pmos w={wp} l={lch}
Mp_pp Cout_int P   Cout_top vdd pmos w={wp} l={lch}
Mp_coutinv Cout Cout_int vdd vdd pmos w={wp} l={lch}
Mn_coutinv Cout Cout_int vss vss nmos w={wn} l={lch}
.ends FA

* ============================================================
* Top-level HEAA instantiation
* ============================================================

* Parameterized VT offsets for stored A bits (lower 4)
.param vt_a0 = 0.12   $ default: A[0]=1
.param vt_a1 = 0.12   $ default: A[1]=1
.param vt_a2 = 0.12   $ default: A[2]=1
.param vt_a3 = 0.12   $ default: A[3]=1

* --- Bits [2:0]: FeFET OR gates (approximate) ---
Xor0 s0 b0 vdd vss FEFET_OR_CELL vt_a={vt_a0}
Xor1 s1 b1 vdd vss FEFET_OR_CELL vt_a={vt_a1}
Xor2 s2 b2 vdd vss FEFET_OR_CELL vt_a={vt_a2}

* --- Bit [3]: Boundary correction ---
* Carry from bit 2: carry_lower = a[2] & b[2]
Xand2 carry_lower b2 vdd vss FEFET_AND_CELL vt_a={vt_a2}

* XOR for bit 3: sum3_exact = a[3] XOR b[3]
Xxor3 sum3_exact b3 vdd vss FEFET_XOR_CELL vt_a={vt_a3}

* Complement: sum3_plus1 = NOT(sum3_exact)
Mp_s3inv sum3_plus1 sum3_exact vdd vdd pmos w={wp} l={lch}
Mn_s3inv sum3_plus1 sum3_exact vss vss nmos w={wn} l={lch}

* MUX: s3 = carry_lower ? sum3_plus1 : sum3_exact
Xmux3 s3 sum3_exact sum3_plus1 carry_lower vdd vss MUX2

* Carry out of boundary: c4 = (a3 & b3) | (sum3_exact & carry_lower)
Xand3 carry_gen3 b3 vdd vss FEFET_AND_CELL vt_a={vt_a3}

* carry_prop3 = sum3_exact & carry_lower
Mp_cp_pu carry_prop3_bar sum3_exact vdd vdd pmos w={wp} l={lch}
Mp_cp_pu2 carry_prop3_bar carry_lower vdd vdd pmos w={wp} l={lch}
Mn_cp_pd1 carry_prop3_bar sum3_exact mid_cp vss nmos w={wn} l={lch}
Mn_cp_pd2 mid_cp carry_lower vss vss nmos w={wn} l={lch}
Mp_cpinv carry_prop3 carry_prop3_bar vdd vdd pmos w={wp} l={lch}
Mn_cpinv carry_prop3 carry_prop3_bar vss vss nmos w={wn} l={lch}

* c4 = carry_gen3 | carry_prop3  (OR gate)
Mp_or_pu1 c4_bar carry_gen3 vdd vdd pmos w={wp} l={lch}
Mp_or_pu2 c4_bar carry_prop3 c4_mid vdd pmos w={wp} l={lch}
Rormid c4_mid vdd 100
Mn_or_pd1 c4_bar carry_gen3 vss vss nmos w={wn} l={lch}
Mn_or_pd2 c4_bar carry_prop3 vss vss nmos w={wn} l={lch}
Mp_c4inv c4 c4_bar vdd vdd pmos w={wp} l={lch}
Mn_c4inv c4 c4_bar vss vss nmos w={wn} l={lch}

* --- Upper 4 bits: Standard CMOS RCA ---
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

* ============================================================
* Testbench
* ============================================================

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
* Test with default A[3:0]=1111 (all LVT), A[7:4]=0101
alter Va4 dc = 1.0
alter Va5 dc = 0
alter Va6 dc = 1.0
alter Va7 dc = 0

let num_tests = 10
let test_b = vector(10)
let test_b[0] = 0
let test_b[1] = 15
let test_b[2] = 170
let test_b[3] = 85
let test_b[4] = 255
let test_b[5] = 128
let test_b[6] = 1
let test_b[7] = 127
let test_b[8] = 240
let test_b[9] = 100

let idx = 0
dowhile idx < num_tests
  let bval = test_b[idx]

  alter Vb0 dc = (floor(bval) mod 2) * 1.0
  alter Vb1 dc = (floor(bval / 2) mod 2) * 1.0
  alter Vb2 dc = (floor(bval / 4) mod 2) * 1.0
  alter Vb3 dc = (floor(bval / 8) mod 2) * 1.0
  alter Vb4 dc = (floor(bval / 16) mod 2) * 1.0
  alter Vb5 dc = (floor(bval / 32) mod 2) * 1.0
  alter Vb6 dc = (floor(bval / 64) mod 2) * 1.0
  alter Vb7 dc = (floor(bval / 128) mod 2) * 1.0

  tran 10p {period}
  let idx = idx + 1
end

wrdata results/raw/fefet/fefet_heaa8_k4.csv v(s0) v(s1) v(s2) v(s3) v(s4) v(s5) v(s6) v(s7) v(cout)

echo "======================================"
echo "FeFET-HEAA8 (k=4) simulation complete"
echo "A[3:0] stored = 1111 (all LVT)"
echo "A[7:4] applied = 0101"
echo "Boundary correction at bit 3"
echo "Results in results/raw/fefet/"
echo "======================================"
.endc

.end
