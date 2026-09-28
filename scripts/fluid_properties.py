#!/usr/bin/env python3
"""Temperature-dependent coolant properties from CoolProp (NIST REFPROP-equivalent HEOS).
Writes data/fluid_properties.csv and prints the design-point summary used in the paper."""
import CoolProp.CoolProp as CP, csv, os, math
out = os.path.join(os.path.dirname(__file__), '..', 'data', 'fluid_properties.csv')
rows = []
def props(fluid, T, P):
    d = dict(fluid=fluid, T_K=T, P_Pa=P)
    for key, sym in (('D','rho'),('C','cp'),('V','mu'),('L','k')):
        d[sym] = CP.PropsSI(key, 'T', T, 'P', P, fluid)
    d['Pr'] = d['cp']*d['mu']/d['k']
    d['beta'] = CP.PropsSI('isobaric_expansion_coefficient','T',T,'P',P,fluid)
    d['Mo'] = d['k']**0.6*d['rho']**0.8*d['cp']**0.4*d['mu']**-0.4
    return d
for T in range(40, 101, 5):
    for P in (1e5, 5e5, 10e5):
        rows.append(props('Helium', T, P))
for T in range(65, 90, 1):
    for P in (1e5, 3e5, 5e5):
        try: rows.append(props('Nitrogen', T, P))
        except Exception as e: pass
with open(out, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print("wrote", out, len(rows), "rows")
print("\n== design points ==")
for fl, T, P in (('Helium',50,1e5),('Helium',50,10e5),('Nitrogen',77,1e5),('Nitrogen',77,3e5)):
    d = props(fl, T, P); print(f"{fl:9s} T={T} K P={P/1e5:.0f} bar: rho={d['rho']:.4g} cp={d['cp']:.4g} mu={d['mu']:.4g} k={d['k']:.4g} Pr={d['Pr']:.3f} beta={d['beta']:.4g} Mo={d['Mo']:.4g}")
print("\n== old-model values used (He_graded metricConstants): mu=2.73e-6 k=0.01851 Pr=0.766 ==")
print("He mu at which T gives 2.73e-6?", [ (T, round(CP.PropsSI('V','T',T,'P',1e5,'Helium')*1e6,2)) for T in (10,15,20,25,30)])
print("\n== N2 saturation ==")
for P in (1e5,2e5,3e5,4e5,5e5): print(f"  P={P/1e5:.0f} bar Tsat={CP.PropsSI('T','P',P,'Q',0,'Nitrogen'):.2f} K  hfg={CP.PropsSI('H','P',P,'Q',1,'Nitrogen')-CP.PropsSI('H','P',P,'Q',0,'Nitrogen'):.0f} J/kg")
print("\n== Mouromtseff ratio N2(77K,3bar)/He(50K,1bar) laminar-relevant k ratio ==")
kN=CP.PropsSI('L','T',77,'P',3e5,'Nitrogen'); kH=CP.PropsSI('L','T',50,'P',1e5,'Helium'); print("k_N2/k_He =", round(kN/kH,3))
