* ============================================================
* FeFET Subcircuit Definitions — Voltage-Shifted MOSFET Model
* FeFET Approximate CiM — IEEE-NANO 2026
* ============================================================
*
* Simplified FeFET model using VT-shifted BSIM4 MOSFETs.
* The ferroelectric polarization state is emulated by a DC
* voltage source in series with the gate, shifting the
* effective threshold voltage of the underlying MOSFET.
*
* Two variants:
*   FEFET_LVT — programmed "1" state (low VT ~ 0.3-0.4V)
*   FEFET_HVT — erased  "0" state  (high VT ~ 1.3-1.6V)
*
* When the HERACLES OSDI model is validated, replace this
* simplified subcircuit with:
*   FeCap(gate_ext, gate_int) + MOSFET(gate_int, D, S, B)
*
* HERACLES integration (future):
*   .control
*   pre_osdi ../../models/fefet/heracles/heracles.osdi
*   .endc
*   Cfe gate_ext gate_int fecap heracles area=625e-12
*       + t_fe=9.8e-9 t_int=1.5e-9 eps_fe=70 p_s=27e-2
*
* ============================================================

* ---- FeFET sizing parameters ----
.param wn_fe  = 90n      $ FeFET NMOS width
.param wp_fe  = 180n     $ FeFET PMOS width (if used)
.param lch_fe  = 45n      $ FeFET channel length

* ---- VT shift parameters ----
* Nominal NMOS VT ~ 0.47V (PTM45 HP)
* FeFET LVT: shift gate UP so effective VT drops
* FeFET HVT: shift gate DOWN so effective VT rises
*
* Memory window ~ 1.0-1.2V
* VT_low  = VT0 - vt_shift_lvt ~ 0.47 - 0.12 = 0.35V
* VT_high = VT0 + vt_shift_hvt ~ 0.47 + 0.93 = 1.40V
.param vt_shift_lvt = 0.12   $ Gate voltage boost for LVT state (V)
.param vt_shift_hvt = -0.93  $ Gate voltage drop for HVT state (V)

* ============================================================
* FEFET_LVT — Low-VT state (stores logic "1")
* Programmed state: ferroelectric polarization lowers VT
* Effective VT ~ 0.35V
* ============================================================
.subckt FEFET_LVT drain gate_ext source bulk
* VT shift: positive offset raises gate voltage -> lowers effective VT
Vshift gate_ext gate_shifted dc {vt_shift_lvt}
Mn1 drain gate_shifted source bulk nmos w={wn_fe} l={lch_fe}
.ends FEFET_LVT

* ============================================================
* FEFET_HVT — High-VT state (stores logic "0")
* Erased state: ferroelectric polarization raises VT
* Effective VT ~ 1.40V
* ============================================================
.subckt FEFET_HVT drain gate_ext source bulk
* VT shift: negative offset lowers gate voltage -> raises effective VT
Vshift gate_ext gate_shifted dc {vt_shift_hvt}
Mn1 drain gate_shifted source bulk nmos w={wn_fe} l={lch_fe}
.ends FEFET_HVT

* ============================================================
* FEFET_PARAM — Parameterized FeFET with arbitrary VT offset
* Use for Monte Carlo: each instance gets a unique vt_offset
* ============================================================
.subckt FEFET_PARAM drain gate_ext source bulk vt_offset=0.12
Vshift gate_ext gate_shifted dc {vt_offset}
Mn1 drain gate_shifted source bulk nmos w={wn_fe} l={lch_fe}
.ends FEFET_PARAM

* ============================================================
* FEFET_PMOS_LVT — PMOS variant, low |VT| (stores "1")
* For complementary FeFET logic if needed
* ============================================================
.subckt FEFET_PMOS_LVT drain gate_ext source bulk
Vshift gate_ext gate_shifted dc {-vt_shift_lvt}
Mp1 drain gate_shifted source bulk pmos w={wp_fe} l={lch_fe}
.ends FEFET_PMOS_LVT

* ============================================================
* FEFET_PMOS_HVT — PMOS variant, high |VT| (stores "0")
* ============================================================
.subckt FEFET_PMOS_HVT drain gate_ext source bulk
Vshift gate_ext gate_shifted dc {-vt_shift_hvt}
Mp1 drain gate_shifted source bulk pmos w={wp_fe} l={lch_fe}
.ends FEFET_PMOS_HVT

* ============================================================
* FeFET-based OR gate (CiM primitive)
* a_stored: FeFET VT encodes operand A
* b_input:  voltage input for operand B
* Output:   a_stored OR b_input
*
* Implementation: parallel NMOS pull-down
*   FeFET(A=1,LVT) in parallel with NMOS(B)
*   If A=1(LVT): FeFET ON at read voltage -> out=0 pulled (inverted)
*   If B=1: NMOS ON -> out=0 pulled
*   -> Inverted OR at pull-down, invert again for OR
* ============================================================
.subckt FEFET_OR out a_stored b_input vdd vss
* Pull-up PMOS (always available)
Mp_pu out_bar a_stored vdd vdd pmos w={wp_fe} l={lch_fe}
Mp_pu2 out_bar b_input vdd vdd pmos w={wp_fe} l={lch_fe}
* Pull-down: FeFET for stored A + NMOS for input B
* When A=1 (LVT), FeFET turns ON at read voltage -> pulls down
* When A=0 (HVT), FeFET stays OFF at read voltage
* b_input drives standard NMOS
Xfe_a out_bar a_stored vss vss FEFET_PARAM vt_offset={vt_shift_lvt}
Mn_b out_bar b_input vss vss nmos w={wn_fe} l={lch_fe}
* Output buffer inverter
Mp_inv out out_bar vdd vdd pmos w={wp_fe} l={lch_fe}
Mn_inv out out_bar vss vss nmos w={wn_fe} l={lch_fe}
.ends FEFET_OR

* ============================================================
* FeFET-based AND gate (CiM primitive)
* a_stored: FeFET VT encodes operand A
* b_input:  voltage input for operand B
* Output:   a_stored AND b_input
*
* Implementation: series NMOS pull-down (NAND -> invert)
*   FeFET(A) in series with NMOS(B) in pull-down
*   Both must be ON for pull-down -> NAND
*   Invert for AND
* ============================================================
.subckt FEFET_AND out a_stored b_input vdd vss
* NAND pull-up: parallel PMOS
Mp_pu1 out_bar a_stored vdd vdd pmos w={wp_fe} l={lch_fe}
Mp_pu2 out_bar b_input vdd vdd pmos w={wp_fe} l={lch_fe}
* NAND pull-down: series FeFET + NMOS
Xfe_a out_bar a_stored mid vss FEFET_PARAM vt_offset={vt_shift_lvt}
Mn_b mid b_input vss vss nmos w={wn_fe} l={lch_fe}
* Output buffer inverter (NAND -> AND)
Mp_inv out out_bar vdd vdd pmos w={wp_fe} l={lch_fe}
Mn_inv out out_bar vss vss nmos w={wn_fe} l={lch_fe}
.ends FEFET_AND
