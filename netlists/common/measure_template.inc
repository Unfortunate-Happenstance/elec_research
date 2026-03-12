* ============================================================
* Measurement templates for circuit characterization
* ============================================================

* Propagation delay: 50% input to 50% output
.measure tran tpd_rise TRIG v(in) VAL='vdd_val/2' RISE=1
+                      TARG v(out) VAL='vdd_val/2' RISE=1

.measure tran tpd_fall TRIG v(in) VAL='vdd_val/2' FALL=1
+                      TARG v(out) VAL='vdd_val/2' FALL=1

* Average power
.measure tran avg_power AVG power FROM='2*period' TO='10*period'

* Static (leakage) power — measure during stable state
.measure tran leak_power AVG power FROM='4.5*period' TO='5*period'
