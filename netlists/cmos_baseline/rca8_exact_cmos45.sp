* ============================================================
* 8-bit Ripple Carry Adder — Exact (CMOS 45nm)
* Uses 8 cascaded 28T Mirror Full Adder cells
* PTM 45nm HP BSIM4 models
* ============================================================

.include '../common/supply.inc'
.include '../../models/cmos45/ptm45_hp.pm'

.param wn = 90n    $ NMOS width (2x Lmin)
.param wp = 180n   $ PMOS width (2x NMOS for balanced)
.param lch = 45n    $ Channel length

* ---- Full Adder Subcircuit (28T Mirror) ----
.subckt FA A B Cin Sum Cout vdd vss

* --- XOR stage: P = A XOR B ---
* Inverters for complements
Mp_ainv Abar A vdd vdd pmos w={wp} l={lch}
Mn_ainv Abar A vss vss nmos w={wn} l={lch}

Mp_binv Bbar B vdd vdd pmos w={wp} l={lch}
Mn_binv Bbar B vss vss nmos w={wn} l={lch}

* TG1: passes B when A=0 (Abar=1)
Mn_tg1 P B Abar vss nmos w={wn} l={lch}
Mp_tg1 P B A vdd pmos w={wp} l={lch}

* TG2: passes Bbar when A=1
Mn_tg2 P Bbar A vss nmos w={wn} l={lch}
Mp_tg2 P Bbar Abar vdd pmos w={wp} l={lch}

* Pbar (complement of P = A XOR B)
Mp_pinv Pbar P vdd vdd pmos w={wp} l={lch}
Mn_pinv Pbar P vss vss nmos w={wn} l={lch}

* --- SUM stage: Sum = P XOR Cin ---
* TG3: passes Cin when P=0
Mn_tg3 Sum Cin Pbar vss nmos w={wn} l={lch}
Mp_tg3 Sum Cin P vdd pmos w={wp} l={lch}

* Cin inverter
Mp_cinv Cinbar Cin vdd vdd pmos w={wp} l={lch}
Mn_cinv Cinbar Cin vss vss nmos w={wn} l={lch}

* TG4: passes Cinbar when P=1
Mn_tg4 Sum Cinbar P vss nmos w={wn} l={lch}
Mp_tg4 Sum Cinbar Pbar vdd pmos w={wp} l={lch}

* --- COUT stage: Cout = AB + Cin*P ---
* NMOS pull-down: (A series B) | (Cin series P)
Mn_ca Cout_int A   Cout_ab  vss nmos w={wn} l={lch}
Mn_cb Cout_ab  B   vss      vss nmos w={wn} l={lch}
Mn_cc Cout_int Cin Cout_cp  vss nmos w={wn} l={lch}
Mn_cp Cout_cp  P   vss      vss nmos w={wn} l={lch}

* PMOS pull-up dual: (A||B) series (Cin||P)
Mp_pa Cout_top A   vdd      vdd pmos w={wp} l={lch}
Mp_pb Cout_top B   vdd      vdd pmos w={wp} l={lch}
Mp_pc Cout_int Cin Cout_top vdd pmos w={wp} l={lch}
Mp_pp Cout_int P   Cout_top vdd pmos w={wp} l={lch}

* Output inverter for Cout
Mp_coutinv Cout Cout_int vdd vdd pmos w={wp} l={lch}
Mn_coutinv Cout Cout_int vss vss nmos w={wn} l={lch}

.ends FA

* ---- 8-bit RCA: chain 8 FA cells ----
* Inputs: a[0:7], b[0:7], cin=0
* Outputs: s[0:7], cout

XFA0 a0 b0 cin  s0 c1 vdd vss FA
XFA1 a1 b1 c1   s1 c2 vdd vss FA
XFA2 a2 b2 c2   s2 c3 vdd vss FA
XFA3 a3 b3 c3   s3 c4 vdd vss FA
XFA4 a4 b4 c4   s4 c5 vdd vss FA
XFA5 a5 b5 c5   s5 c6 vdd vss FA
XFA6 a6 b6 c6   s6 c7 vdd vss FA
XFA7 a7 b7 c7   s7 cout vdd vss FA

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

* Carry-in tied to ground
Vcin cin 0 dc 0

* ---- Testbench: Parametric sweep via .control block ----
* Use voltage sources with dc value controlled by alter
Va0 a0 0 dc 0
Va1 a1 0 dc 0
Va2 a2 0 dc 0
Va3 a3 0 dc 0
Va4 a4 0 dc 0
Va5 a5 0 dc 0
Va6 a6 0 dc 0
Va7 a7 0 dc 0

Vb0 b0 0 dc 0
Vb1 b1 0 dc 0
Vb2 b2 0 dc 0
Vb3 b3 0 dc 0
Vb4 b4 0 dc 0
Vb5 b5 0 dc 0
Vb6 b6 0 dc 0
Vb7 b7 0 dc 0

* Transient analysis — single period per vector
.tran 10p {period}

.control
* Representative test vectors for 8-bit RCA
* Format: A[7:0], B[7:0] as decimal values
* We test key corner cases and representative values

let num_tests = 20
let test_a = vector(20)
let test_b = vector(20)

* Corner cases
let test_a[0] = 0
let test_b[0] = 0
let test_a[1] = 0
let test_b[1] = 255
let test_a[2] = 255
let test_b[2] = 0
let test_a[3] = 255
let test_b[3] = 255
let test_a[4] = 255
let test_b[4] = 1
let test_a[5] = 1
let test_b[5] = 255
let test_a[6] = 128
let test_b[6] = 128
let test_a[7] = 127
let test_b[7] = 127

* Representative values
let test_a[8]  = 170
let test_b[8]  = 85
let test_a[9]  = 85
let test_b[9]  = 170
let test_a[10] = 15
let test_b[10] = 15
let test_a[11] = 240
let test_b[11] = 15
let test_a[12] = 100
let test_b[12] = 155
let test_a[13] = 200
let test_b[13] = 100
let test_a[14] = 50
let test_b[14] = 205
let test_a[15] = 1
let test_b[15] = 1
let test_a[16] = 64
let test_b[16] = 64
let test_a[17] = 33
let test_b[17] = 66
let test_a[18] = 123
let test_b[18] = 45
let test_a[19] = 254
let test_b[19] = 254

let idx = 0
dowhile idx < num_tests
  let aval = test_a[idx]
  let bval = test_b[idx]

  * Set A bits
  alter Va0 dc = (floor(aval) mod 2) * 1.0
  alter Va1 dc = (floor(aval / 2) mod 2) * 1.0
  alter Va2 dc = (floor(aval / 4) mod 2) * 1.0
  alter Va3 dc = (floor(aval / 8) mod 2) * 1.0
  alter Va4 dc = (floor(aval / 16) mod 2) * 1.0
  alter Va5 dc = (floor(aval / 32) mod 2) * 1.0
  alter Va6 dc = (floor(aval / 64) mod 2) * 1.0
  alter Va7 dc = (floor(aval / 128) mod 2) * 1.0

  * Set B bits
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

* ---- Phase 3: Worst-case timing + power characterization ----
* Step 1: settle with A=0xFF, B=0x00 (cout=0)
alter Va0 dc = 1
alter Va1 dc = 1
alter Va2 dc = 1
alter Va3 dc = 1
alter Va4 dc = 1
alter Va5 dc = 1
alter Va6 dc = 1
alter Va7 dc = 1
alter Vb0 dc = 0
alter Vb1 dc = 0
alter Vb2 dc = 0
alter Vb3 dc = 0
alter Vb4 dc = 0
alter Vb5 dc = 0
alter Vb6 dc = 0
alter Vb7 dc = 0
tran 10p 5n

* Step 2: trigger carry ripple — B switches 0x00→0xFF (cout: 0→1)
alter Vb0 dc = 1
alter Vb1 dc = 1
alter Vb2 dc = 1
alter Vb3 dc = 1
alter Vb4 dc = 1
alter Vb5 dc = 1
alter Vb6 dc = 1
alter Vb7 dc = 1
tran 10p 5n
meas tran tpd_rise WHEN v(cout)=0.5 RISE=1
meas tran tpd_fall WHEN v(cout)=0.5 FALL=1
meas tran avg_power AVG power FROM=0 TO=5n
echo "TPD_RISE = $&tpd_rise"
echo "TPD_FALL = $&tpd_fall"
echo "AVG_POWER = $&avg_power"

wrdata results/raw/cmos_baseline/rca8_exact_cmos45.csv v(s0) v(s1) v(s2) v(s3) v(s4) v(s5) v(s6) v(s7) v(cout)
.endc

.end
