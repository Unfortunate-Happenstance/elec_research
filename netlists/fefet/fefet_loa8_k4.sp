* ============================================================
* FeFET-LOA: 8-bit Lower-Order Approximate Adder (k=4)
*
* Architecture:
*   Bits [3:0] — Approximate part (FeFET OR gates)
*     s[i] = a_stored[i] | b_input[i]  for i=0..3
*     No carry propagation in approximate part
*   Carry into exact part:
*     c4 = a_stored[3] & b_input[3]  (FeFET AND gate)
*   Bits [7:4] — Exact part (standard CMOS RCA)
*     4-bit ripple carry adder with c4 as carry-in
*
* Operand A[7:0] is stored in FeFET VT states
* Operand B[7:0] and Cin are applied as voltage inputs
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
* FeFET OR Gate for approximate bits
* a_stored is encoded in FeFET VT:
*   A=1 -> LVT (vt_a = vt_shift_lvt)
*   A=0 -> HVT (vt_a = vt_shift_hvt)
* b_input is a voltage signal
* out = a_stored OR b_input
*
* Implementation: NOR + inverter
*   NOR: PMOS series (A,B) pull-up + NMOS parallel pull-down
*   FeFET replaces the A-driven NMOS/PMOS
* ============================================================
.subckt FEFET_OR_CELL out b_input vdd vss vt_a=0.12
* NOR pull-down: FeFET(A) || NMOS(B) — parallel, same as FEFET_OR_MC
* FeFET NMOS: ON when A=1 (LVT, gate_shifted=VDD-vt_a=0.88V > Vth)
*             OFF when A=0 (HVT, gate_shifted=VDD-1.20=-0.20V < Vth)
Xfe_pd nor_out vdd vss vss FEFET_PARAM vt_offset={vt_a}
Mn_b nor_out b_input vss vss nmos w={wn} l={lch}
* NOR pull-up: PMOS for B + weak PMOS keeper (no 100 Ohm resistor)
* Mp_b: pulls nor_out HIGH when B=0 (Vgs = b_input - VDD < Vtp)
* Mp_keep: weak always-ON keeper to define static HIGH when both pull-downs OFF
Mp_b    nor_out b_input  vdd vdd pmos w={wp}        l={lch}
Mp_keep nor_out nor_out  vdd vdd pmos w={wn}        l={4*lch}
* Inverter: NOR -> OR
Mp_inv out nor_out vdd vdd pmos w={wp} l={lch}
Mn_inv out nor_out vss vss nmos w={wn} l={lch}
.ends FEFET_OR_CELL

* ============================================================
* FeFET AND Gate for carry generation
* c4 = a_stored[3] & b_input[3]
* ============================================================
.subckt FEFET_AND_CELL out b_input vdd vss vt_a=0.12
* NAND pull-up: B pull-up (Mp_pu2) + weak always-ON keeper (Mp_pk)
* Mp_pk: gate=VSS → always ON but weak (w=wn, l=4*lch).
*   Drive ratio pull-down:pull-up ≈ 8x (NMOS series FeFET wins when A=1,B=1).
* Mp_pu2: gate=b_input → ON when B=0 (correct static pull-up for A=x,B=0)
Mp_pk  nand_out vss vdd vdd pmos w={wn}       l={4*lch}
Mp_pu2 nand_out b_input vdd vdd pmos w={2*wp} l={lch}

* NAND pull-down: series FeFET(A) + NMOS(B)
* FeFET ON when A=stored-1 (LVT, vt_a=0.12): gate_shifted=0.88V > Vth
* FeFET OFF when A=stored-0 (HVT, vt_a=1.20): gate_shifted=-0.20V < Vth
Xfe_pd nand_out vdd mid_pd vss FEFET_PARAM vt_offset={vt_a}
Mn_b mid_pd b_input vss vss nmos w={2*wn} l={lch}

* Invert NAND -> AND
Mp_inv out nand_out vdd vdd pmos w={wp} l={lch}
Mn_inv out nand_out vss vss nmos w={wn} l={lch}
.ends FEFET_AND_CELL

* ============================================================
* Standard CMOS Full Adder (for exact upper bits)
* Identical to baseline — 28T TG mirror adder
* ============================================================
.subckt FA A B Cin Sum Cout vdd vss
* Inverters
Mp_ainv Abar A vdd vdd pmos w={wp} l={lch}
Mn_ainv Abar A vss vss nmos w={wn} l={lch}
Mp_binv Bbar B vdd vdd pmos w={wp} l={lch}
Mn_binv Bbar B vss vss nmos w={wn} l={lch}

* P = A XOR B (TG)
Mn_tg1 P B Abar vss nmos w={wn} l={lch}
Mp_tg1 P B A vdd pmos w={wp} l={lch}
Mn_tg2 P Bbar A vss nmos w={wn} l={lch}
Mp_tg2 P Bbar Abar vdd pmos w={wp} l={lch}

Mp_pinv Pbar P vdd vdd pmos w={wp} l={lch}
Mn_pinv Pbar P vss vss nmos w={wn} l={lch}

* Sum = P XOR Cin (TG)
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
* Top-level LOA instantiation
* ============================================================

* --- Lower 4 bits: FeFET OR gates (approximate) ---
* a[i] stored in FeFET VT, b[i] as voltage input
* Each OR cell gets a vt_a parameter based on stored A bit

* Parameterized VT offsets for stored A bits
* These will be set per test vector in the control block
.param vt_a0 = 0.12   $ default: A[0]=1 (LVT)
.param vt_a1 = 0.12   $ default: A[1]=1 (LVT)
.param vt_a2 = 0.12   $ default: A[2]=1 (LVT)
.param vt_a3 = 0.12   $ default: A[3]=1 (LVT)

* Approximate OR gates
Xor0 s0 b0 vdd vss FEFET_OR_CELL vt_a={vt_a0}
Xor1 s1 b1 vdd vss FEFET_OR_CELL vt_a={vt_a1}
Xor2 s2 b2 vdd vss FEFET_OR_CELL vt_a={vt_a2}
Xor3 s3 b3 vdd vss FEFET_OR_CELL vt_a={vt_a3}

* --- Carry generation: c4 = a[3] & b[3] ---
Xand3 c4 b3 vdd vss FEFET_AND_CELL vt_a={vt_a3}

* --- Upper 4 bits: Standard CMOS RCA ---
* A[7:4] applied as voltage inputs (not stored in FeFET for upper part)
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
* Testbench: Representative test vectors
* ============================================================

* B input sources
Vb0 b0 0 dc 0
Vb1 b1 0 dc 0
Vb2 b2 0 dc 0
Vb3 b3 0 dc 0
Vb4 b4 0 dc 0
Vb5 b5 0 dc 0
Vb6 b6 0 dc 0
Vb7 b7 0 dc 0

* Upper A input sources (exact part, standard voltage)
Va4 a4 0 dc 0
Va5 a5 0 dc 0
Va6 a6 0 dc 0
Va7 a7 0 dc 0

.tran 10p {period}

.control
* ============================================================
* Test vectors for FeFET-LOA8 (k=4)
* A is stored in FeFET VT, B is applied as voltage
*
* NOTE: For the approximate lower bits, A is encoded in the
* FeFET VT offset. We cannot dynamically alter subcircuit
* parameters in ngspice, so we test with the default A
* configuration (A[3:0] = 1111 = 0xF, all LVT).
*
* For full A-sweep testing, use the Monte Carlo template
* or run multiple netlists with different .param values.
* ============================================================

* With default A[3:0]=1111 (all LVT) and A[7:4]=0000:
* LOA result s[3:0] = A[3:0] | B[3:0]
*   = 1111 | B[3:0] = 1111 for any B[3:0]
* c4 = A[3] & B[3] = 1 & B[3]

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

* Upper A bits: set to known pattern (A[7:4] = 0101 = 5)
alter Va4 dc = 1.0
alter Va5 dc = 0
alter Va6 dc = 1.0
alter Va7 dc = 0

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

wrdata results/raw/fefet/fefet_loa8_k4.csv v(s0) v(s1) v(s2) v(s3) v(s4) v(s5) v(s6) v(s7) v(cout)

echo "======================================"
echo "FeFET-LOA8 (k=4) simulation complete"
echo "A[3:0] stored = 1111 (all LVT)"
echo "A[7:4] applied = 0101"
echo "Results in results/raw/fefet/"
echo "======================================"
.endc

.end
