* ============================================================
* FeFET Full Adder — Mirror Adder with FeFET-stored Operand A
* SUM = A XOR B XOR Cin
* COUT = AB + Cin(A XOR B)
*
* Operand A is stored in FeFET VT states (CiM)
* Operand B and Cin are applied as voltage inputs
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

* ============================================================
* FeFET Full Adder Subcircuit
*
* In the mirror adder topology, operand A is encoded in FeFET
* threshold voltages. The NMOS transistors driven by A and Abar
* are replaced with FeFETs whose VT encodes the stored bit.
*
* When A_stored=1: FeFET_A is LVT (ON at read), FeFET_Abar is HVT (OFF)
* When A_stored=0: FeFET_A is HVT (OFF), FeFET_Abar is LVT (ON)
*
* vt_a:    VT offset for FeFET encoding A
* vt_abar: VT offset for FeFET encoding Abar (complement)
* ============================================================
.subckt FEFET_FA B Cin Sum Cout vdd vss vt_a=0.12 vt_abar=-0.93

* --- Generate B complement ---
Mp_binv Bbar B vdd vdd pmos w={wp} l={lch}
Mn_binv Bbar B vss vss nmos w={wn} l={lch}

* --- XOR stage: P = A XOR B ---
* A is stored in FeFET VT, so we use the read voltage (vdd)
* applied to the FeFET gate to sense A.
*
* TG1: passes B when A=0 (Abar=1 -> LVT FeFET Abar ON)
* NMOS path: controlled by Abar (FeFET)
* PMOS path: controlled by A (FeFET, complementary)
*
* For the pass-gate XOR, we apply vdd to the FeFET gates.
* FeFET_A with vt_a drives control signals.
* We use a sense-amp style approach:
*
* Read node: apply vread to FeFET gate -> current indicates stored bit
* Simplified: use FeFET as switch in TG

* FeFET-based sense for A value (read at vdd)
* Node 'a_sense' will be high when A=1(LVT), low when A=0(HVT)
Mp_ard a_sense vss vdd vdd pmos w={wp} l={lch}
Xfe_ard a_sense vdd mid_ard vss FEFET_PARAM vt_offset={vt_a}
Rmid_ard mid_ard vss 1k

* Complement: a_sense_bar
Mp_asinv a_sense_bar a_sense vdd vdd pmos w={wp} l={lch}
Mn_asinv a_sense_bar a_sense vss vss nmos w={wn} l={lch}

* TG1: passes B when A=0 (a_sense_bar=1)
Mn_tg1 P B a_sense_bar vss nmos w={wn} l={lch}
Mp_tg1 P B a_sense vdd pmos w={wp} l={lch}

* TG2: passes Bbar when A=1 (a_sense=1)
Mn_tg2 P Bbar a_sense vss nmos w={wn} l={lch}
Mp_tg2 P Bbar a_sense_bar vdd pmos w={wp} l={lch}

* Pbar (complement of P = A XOR B)
Mp_pinv Pbar P vdd vdd pmos w={wp} l={lch}
Mn_pinv Pbar P vss vss nmos w={wn} l={lch}

* --- SUM stage: Sum = P XOR Cin ---
* Standard TG XOR (no FeFET needed here)
Mn_tg3 Sum Cin Pbar vss nmos w={wn} l={lch}
Mp_tg3 Sum Cin P vdd pmos w={wp} l={lch}

* Cin inverter
Mp_cinv Cinbar Cin vdd vdd pmos w={wp} l={lch}
Mn_cinv Cinbar Cin vss vss nmos w={wn} l={lch}

Mn_tg4 Sum Cinbar P vss nmos w={wn} l={lch}
Mp_tg4 Sum Cinbar Pbar vdd pmos w={wp} l={lch}

* --- COUT stage: Cout = AB + Cin*(A XOR B) ---
* NMOS pull-down: replace A-driven transistors with FeFETs
* a_sense drives the A-dependent paths
Mn_c1 Cout_int a_sense vss vss nmos w={wn} l={lch}
Mn_c2 Cout_int B Cout_int1 vss nmos w={wn} l={lch}
Mn_c3 Cout_int1 Cin vss vss nmos w={wn} l={lch}
Mn_c4 Cout_int P Cout_int1 vss nmos w={wn} l={lch}

* PMOS pull-up
Mp_c1 Cout_int a_sense_bar vdd vdd pmos w={wp} l={lch}
Mp_c2 Cout_int Bbar Cout_int2 vdd pmos w={wp} l={lch}
Mp_c3 Cout_int2 Cinbar vdd vdd pmos w={wp} l={lch}
Mp_c4 Cout_int2 Pbar Cout_int2 vdd pmos w={wp} l={lch}

* Output inverter for Cout
Mp_coutinv Cout Cout_int vdd vdd pmos w={wp} l={lch}
Mn_coutinv Cout Cout_int vss vss nmos w={wn} l={lch}

.ends FEFET_FA

* ============================================================
* Testbench
* ============================================================

* --- FA instance with A=1 (LVT for A, HVT for Abar) ---
XFA_A1 B1 Cin1 Sum_a1 Cout_a1 vdd vss FEFET_FA vt_a={vt_shift_lvt} vt_abar={vt_shift_hvt}

* --- FA instance with A=0 (HVT for A, LVT for Abar) ---
XFA_A0 B0 Cin0 Sum_a0 Cout_a0 vdd vss FEFET_FA vt_a={vt_shift_hvt} vt_abar={vt_shift_lvt}

* Input stimuli: sweep B and Cin through all 4 combinations
* For A=1 instance:
VB1 B1 0 PWL(0 0
+ {period} 0 {period+trise} {vdd_val}
+ {2*period} {vdd_val} {2*period+tfall} 0
+ {3*period} 0 {3*period+trise} {vdd_val})

VCin1 Cin1 0 PWL(0 0
+ {2*period} 0 {2*period+trise} {vdd_val})

* For A=0 instance:
VB0 B0 0 PWL(0 0
+ {period} 0 {period+trise} {vdd_val}
+ {2*period} {vdd_val} {2*period+tfall} 0
+ {3*period} 0 {3*period+trise} {vdd_val})

VCin0 Cin0 0 PWL(0 0
+ {2*period} 0 {2*period+trise} {vdd_val})

* Load capacitances
Cs_a1 Sum_a1  0 {cload}
Cc_a1 Cout_a1 0 {cload}
Cs_a0 Sum_a0  0 {cload}
Cc_a0 Cout_a0 0 {cload}

* Transient analysis
.tran 10p {4*period}

.control
run
wrdata results/raw/fefet/fefet_fa.csv v(B1) v(Cin1) v(Sum_a1) v(Cout_a1) v(B0) v(Cin0) v(Sum_a0) v(Cout_a0)

echo "======================================"
echo "FeFET Full Adder Results"
echo "======================================"
echo "A=1 stored in FeFET (LVT state):"
echo "  B=0,Cin=0 -> Sum,Cout = 1,0 expected"
echo "  B=1,Cin=0 -> Sum,Cout = 0,1 expected"
echo "  B=0,Cin=1 -> Sum,Cout = 0,1 expected"
echo "  B=1,Cin=1 -> Sum,Cout = 1,1 expected"
echo ""
echo "A=0 stored in FeFET (HVT state):"
echo "  B=0,Cin=0 -> Sum,Cout = 0,0 expected"
echo "  B=1,Cin=0 -> Sum,Cout = 1,0 expected"
echo "  B=0,Cin=1 -> Sum,Cout = 1,0 expected"
echo "  B=1,Cin=1 -> Sum,Cout = 0,1 expected"
echo "======================================"
.endc

.end
