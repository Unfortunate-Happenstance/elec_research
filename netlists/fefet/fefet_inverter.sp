* ============================================================
* FeFET Inverter — VTC Validation Testbench
* Standard PMOS + FeFET NMOS (programmable VT)
* Shows different switching thresholds for LVT vs HVT states
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
* FeFET Inverter Subcircuit
* Standard PMOS pull-up + FeFET NMOS pull-down
* vt_off: VT shift applied to the FeFET NMOS
* ============================================================
.subckt FEFET_INV in out vdd vss vt_off=0.12
* Standard PMOS pull-up
Mp out in vdd vdd pmos w={wp} l={lch}
* FeFET NMOS pull-down (VT shifted)
Xfn out in vss vss FEFET_PARAM vt_offset={vt_off}
.ends FEFET_INV

* ============================================================
* Testbench: Two inverters, LVT and HVT
* ============================================================

* --- Inverter with FeFET in LVT state (A stored = "1") ---
XINV_LVT in out_lvt vdd vss FEFET_INV vt_off={vt_shift_lvt}

* --- Inverter with FeFET in HVT state (A stored = "0") ---
XINV_HVT in out_hvt vdd vss FEFET_INV vt_off={vt_shift_hvt}

* --- Reference: standard CMOS inverter ---
Mp_ref out_ref in vdd vdd pmos w={wp} l={lch}
Mn_ref out_ref in vss vss nmos w={wn} l={lch}

* Load capacitances
Clvt  out_lvt 0 {cload}
Chvt  out_hvt 0 {cload}
Cref  out_ref 0 {cload}

* ============================================================
* Analysis 1: VTC (DC sweep)
* Sweep input from 0 to VDD, observe output for each state
* ============================================================
Vin in 0 dc 0

.dc Vin 0 {vdd_val} 0.005

* ============================================================
* Analysis 2: Transient response
* ============================================================
* Uncomment below and comment .dc above for transient
* Vin in 0 PULSE(0 {vdd_val} {period} {trise} {tfall} {4*period} {10*period})
* .tran 10p {20*period}

.control
run

* Plot VTC curves
set hcopydevtype = postscript
set hcopypscolor = 1

* Write VTC data
wrdata results/raw/fefet/fefet_inverter_vtc.csv v(in) v(out_lvt) v(out_hvt) v(out_ref)

* Measure switching thresholds (VM where Vin = Vout)
meas dc vm_lvt WHEN v(out_lvt)=v(in)
meas dc vm_hvt WHEN v(out_hvt)=v(in)
meas dc vm_ref WHEN v(out_ref)=v(in)

echo "=============================="
echo "FeFET Inverter VTC Results"
echo "=============================="
echo "Switching threshold (LVT state): $&vm_lvt V"
echo "Switching threshold (HVT state): $&vm_hvt V"
echo "Switching threshold (CMOS ref) : $&vm_ref V"
echo "=============================="

.endc

.end
