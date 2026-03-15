* ============================================================
* CMOS 45nm Full Adder — Mirror Adder (28T)
* SUM = A XOR B XOR Cin
* COUT = AB + Cin(A XOR B)
* PTM 45nm HP BSIM4 models
* ============================================================

.include '../common/supply.inc'
.include '../../models/cmos45/ptm45_hp.pm'

.param wn = 90n    $ NMOS width (2x Lmin)
.param wp = 180n   $ PMOS width (2x NMOS for balanced)
.param lch = 45n    $ Channel length

* ---- Full Adder Subcircuit ----
.subckt FA A B Cin Sum Cout vdd vss

* --- XOR stage: P = A XOR B ---
* Transmission-gate XOR
* When A=0: pass B through TG1
* When A=1: pass Bbar through TG2

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
* Complementary pass-transistor carry
* COUT mirror: PMOS pull-up, NMOS pull-down

* Cout — corrected topology: (A·B) + (Cin·P)
* NMOS pull-down: (A series B) | (Cin series P)
Mn_ca Cout_int A   Cout_ab  vss nmos w={wn} l={lch}
Mn_cb Cout_ab  B   vss      vss nmos w={wn} l={lch}
Mn_cc Cout_int Cin Cout_cp  vss nmos w={wn} l={lch}
Mn_cp Cout_cp  P   vss      vss nmos w={wn} l={lch}
* PMOS pull-up: (A||B) series (Cin||P)  [PMOS ON when gate=LOW — correct dual]
Mp_pa Cout_top A   vdd      vdd pmos w={wp} l={lch}
Mp_pb Cout_top B   vdd      vdd pmos w={wp} l={lch}
Mp_pc Cout_int Cin Cout_top vdd pmos w={wp} l={lch}
Mp_pp Cout_int P   Cout_top vdd pmos w={wp} l={lch}

* Output inverter for Cout
Mp_coutinv Cout Cout_int vdd vdd pmos w={wp} l={lch}
Mn_coutinv Cout Cout_int vss vss nmos w={wn} l={lch}

.ends FA

* ---- Testbench ----
XFA1 A B Cin Sum Cout vdd vss FA

* Input stimuli — sweep through all 8 combinations
VA A 0 PWL(0 0 {period} 0 {period+trise} {vdd_val}
+ {2*period} {vdd_val} {2*period+tfall} 0
+ {3*period} 0 {3*period+trise} {vdd_val}
+ {4*period} {vdd_val} {4*period+tfall} 0
+ {5*period} 0 {5*period+trise} {vdd_val}
+ {6*period} {vdd_val} {6*period+tfall} 0
+ {7*period} 0 {7*period+trise} {vdd_val})

VB B 0 PWL(0 0 {2*period} 0 {2*period+trise} {vdd_val}
+ {4*period} {vdd_val} {4*period+tfall} 0
+ {6*period} 0 {6*period+trise} {vdd_val})

VCin Cin 0 PWL(0 0 {4*period} 0 {4*period+trise} {vdd_val})

* Load capacitances
Csum Sum 0 {cload}
Ccout Cout 0 {cload}

* Analysis
.tran 10p {8*period}

.control
run
wrdata results/raw/cmos_baseline/fa_cmos45.csv v(A) v(B) v(Cin) v(Sum) v(Cout)
.endc

.end
