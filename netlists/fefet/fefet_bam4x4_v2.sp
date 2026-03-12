* ============================================================
* FeFET-BAM: 4x4 Broken Array Multiplier (v2)
*
* Architecture:
*   Partial products: pp[i][j] = a[i] & b[j]
*   a[i] stored in FeFET VT, b[j] applied as voltage
*   Broken: skip products where (i+j) < 2
*   Kept products (i+j >= 2):
*     pp[0][2], pp[0][3]
*     pp[1][1], pp[1][2], pp[1][3]
*     pp[2][0], pp[2][1], pp[2][2], pp[2][3]
*     pp[3][0], pp[3][1], pp[3][2], pp[3][3]
*   Skipped (approximated as 0):
*     pp[0][0], pp[0][1], pp[1][0]
*
*   Product bits: p[0]=0, p[1]=0 (skipped)
*   Reduced adder tree for remaining partial products
*
* Result: 8-bit product P[7:0]
*   P[0] = 0 (skipped)
*   P[1] = 0 (skipped)
*   P[2..7] computed from remaining PPs
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
* FeFET AND Gate for partial products
* a_stored in FeFET VT, b_input as voltage
* ============================================================
.subckt FEFET_AND_PP out b_input vdd vss vt_a=0.12
* NAND: series pull-down FeFET(A) + NMOS(B)
Xfe_pd nand_out vdd mid_nd vss FEFET_PARAM vt_offset={vt_a}
Mn_b mid_nd b_input vss vss nmos w={2*wn} l={lch}
* NAND pull-up: parallel PMOS
Mp_pk  nand_out vss vdd vdd pmos w={wn}       l={4*lch}  $ weak keeper: drive ratio ~8x vs pull-down
Mp_pu2 nand_out b_input vdd vdd pmos w={2*wp} l={lch}
* Invert -> AND
Mp_inv out nand_out vdd vdd pmos w={wp} l={lch}
Mn_inv out nand_out vss vss nmos w={wn} l={lch}
.ends FEFET_AND_PP

* ============================================================
* Half Adder
* ============================================================
.subckt HA A B Sum Cout vdd vss
* XOR via TG
Mp_ainv Abar A vdd vdd pmos w={wp} l={lch}
Mn_ainv Abar A vss vss nmos w={wn} l={lch}
Mp_binv Bbar B vdd vdd pmos w={wp} l={lch}
Mn_binv Bbar B vss vss nmos w={wn} l={lch}
Mn_tg1 Sum B Abar vss nmos w={wn} l={lch}
Mp_tg1 Sum B A vdd pmos w={wp} l={lch}
Mn_tg2 Sum Bbar A vss nmos w={wn} l={lch}
Mp_tg2 Sum Bbar Abar vdd pmos w={wp} l={lch}
* AND for carry
Mn_c1 Cout_bar A vdd vdd pmos w={wp} l={lch}
Mp_c1 Cout_bar B vdd vdd pmos w={wp} l={lch}
Mn_and1 Cout_bar A mid_and vss nmos w={wn} l={lch}
Mn_and2 mid_and B vss vss nmos w={wn} l={lch}
Mp_cinv Cout Cout_bar vdd vdd pmos w={wp} l={lch}
Mn_cinv Cout Cout_bar vss vss nmos w={wn} l={lch}
.ends HA

* ============================================================
* Full Adder (standard CMOS, for adder tree)
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
* Top-level BAM instantiation
* ============================================================

* VT offsets for stored A[3:0] bits
.param vt_a0 = 0.12   $ default: A[0]=1
.param vt_a1 = 0.12   $ default: A[1]=1
.param vt_a2 = 0.12   $ default: A[2]=1
.param vt_a3 = 0.12   $ default: A[3]=1

* --- Partial Product Generation (FeFET AND gates) ---
* Skip pp where (i+j) < 2, i.e., pp00, pp01, pp10
* P[0] = pp00 = 0 (skipped)
* P[1] = pp01 + pp10 = 0 (skipped)

* Column 2: pp02, pp11, pp20
Xpp02 pp02 b2 vdd vss FEFET_AND_PP vt_a={vt_a0}
Xpp11 pp11 b1 vdd vss FEFET_AND_PP vt_a={vt_a1}
Xpp20 pp20 b0 vdd vss FEFET_AND_PP vt_a={vt_a2}

* Column 3: pp03, pp12, pp21, pp30
Xpp03 pp03 b3 vdd vss FEFET_AND_PP vt_a={vt_a0}
Xpp12 pp12 b2 vdd vss FEFET_AND_PP vt_a={vt_a1}
Xpp21 pp21 b1 vdd vss FEFET_AND_PP vt_a={vt_a2}
Xpp30 pp30 b0 vdd vss FEFET_AND_PP vt_a={vt_a3}

* Column 4: pp13, pp22, pp31
Xpp13 pp13 b3 vdd vss FEFET_AND_PP vt_a={vt_a1}
Xpp22 pp22 b2 vdd vss FEFET_AND_PP vt_a={vt_a2}
Xpp31 pp31 b1 vdd vss FEFET_AND_PP vt_a={vt_a3}

* Column 5: pp23, pp32
Xpp23 pp23 b3 vdd vss FEFET_AND_PP vt_a={vt_a2}
Xpp32 pp32 b2 vdd vss FEFET_AND_PP vt_a={vt_a3}

* Column 6: pp33
Xpp33 pp33 b3 vdd vss FEFET_AND_PP vt_a={vt_a3}

* --- Adder Tree ---
* P[0] = 0 (skipped, tied to ground)
Vp0 p0 0 dc 0
* P[1] = 0 (skipped, tied to ground)
Vp1 p1 0 dc 0

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

* ============================================================
* Testbench
* ============================================================

* B input sources
Vb0 b0 0 dc 0
Vb1 b1 0 dc 0
Vb2 b2 0 dc 0
Vb3 b3 0 dc 0

.tran 10p {period}

.control
* Test with A[3:0] = 1111 (all LVT, decimal 15)
* Sweep B through representative values

let num_tests = 16
let test_b = vector(16)
let test_b[0]  = 0
let test_b[1]  = 1
let test_b[2]  = 2
let test_b[3]  = 3
let test_b[4]  = 4
let test_b[5]  = 5
let test_b[6]  = 6
let test_b[7]  = 7
let test_b[8]  = 8
let test_b[9]  = 9
let test_b[10] = 10
let test_b[11] = 11
let test_b[12] = 12
let test_b[13] = 13
let test_b[14] = 14
let test_b[15] = 15

let idx = 0
dowhile idx < num_tests
  let bval = test_b[idx]

  alter Vb0 dc = (floor(bval) mod 2) * 1.0
  alter Vb1 dc = (floor(bval / 2) mod 2) * 1.0
  alter Vb2 dc = (floor(bval / 4) mod 2) * 1.0
  alter Vb3 dc = (floor(bval / 8) mod 2) * 1.0

  tran 10p {period}
  let idx = idx + 1
end

wrdata results/raw/fefet/fefet_bam4x4_v2.csv v(p0) v(p1) v(p2) v(p3) v(p4) v(p5) v(p6) v(p7)

echo "======================================"
echo "FeFET-BAM 4x4 (v2) simulation complete"
echo "A[3:0] stored = 1111 (all LVT, =15)"
echo "B[3:0] swept 0..15"
echo "Broken: skip pp where (i+j)<2"
echo "Exact: 15*B"
echo "Results in results/raw/fefet/"
echo "======================================"
.endc

.end
