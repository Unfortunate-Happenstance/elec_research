* ============================================================
* Common supply and parameter definitions
* FeFET Approximate CiM — IEEE-NANO 2026
* ============================================================

.param vdd_val = 1.0        $ Logic supply voltage (V)
.param vread   = 0.8        $ FeFET read voltage (V)
.param vprog   = 4.5        $ FeFET program voltage (V)
.param tprog   = 500n       $ FeFET program pulse width (s)
.param cload   = 1f         $ Output load capacitance (F)
.param trise   = 50p        $ Input rise time (s)
.param tfall   = 50p        $ Input fall time (s)
.param period  = 10n        $ Clock period (s) — 100 MHz equivalent
.param temp_val = 27        $ Temperature (C)

* Supply rails
Vdd vdd 0 dc {vdd_val}
Vss vss 0 dc 0
