* ============================================================
* CMOS 45nm Inverter — Validation Testbench
* PTM 45nm HP BSIM4 models
* ============================================================

.include '../common/supply.inc'
.include '../../models/cmos45/ptm45_hp.pm'

.param wn = 90n    $ NMOS width (2x Lmin)
.param wp = 180n   $ PMOS width (2x NMOS for balanced)
.param lch = 45n    $ Channel length

* ---- Inverter Subcircuit (2T) ----
.subckt INV in out vdd vss
Mp out in vdd vdd pmos w={wp} l={lch}
Mn out in vss vss nmos w={wn} l={lch}
.ends INV

* ---- Testbench ----
XINV1 in out vdd vss INV

* Input stimulus — pulse
Vin in 0 PULSE(0 {vdd_val} {period} {trise} {tfall} {4*period} {10*period})

* Load capacitance
Cout out 0 {cload}

* Transient analysis
.tran 10p {20*period}

.control
run
wrdata results/raw/cmos_baseline/inverter_cmos45.csv v(in) v(out)
.endc

.end
