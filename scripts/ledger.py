#!/usr/bin/env python3
"""ledger.py -- Q3 work ledger: ideal (Carnot) and real (hardware-efficiency) room-temperature
power for the He (50 K) and LN2 (77 K) first-shield routes, bare and MLI-equivalent shields,
with emissivity +-50% bands. Reads data/enclosure_loads.csv (written by enclosure_collect.py);
falls back to the baseline production values if variants are missing.
Outputs data/ledger.csv and figures/fig8_ledger.png.
"""
import os, sys, numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..')
DATA = os.path.join(ROOT, 'data'); FIG = os.path.join(ROOT, 'figures')
plt.rcParams.update({'font.size': 9, 'font.family': 'DejaVu Serif', 'axes.grid': True, 'grid.alpha': 0.3, 'figure.dpi': 300, 'savefig.bbox': 'tight'})
T0 = 300.0
# --- stage efficiencies (fraction of Carnot) ---
# PT415: 1.5 W @ 4.2 K + 40 W @ 45 K for 10.7 kW.  Carnot work: 1.5*(300-4.2)/4.2 = 105.6 W ; 40*(300-45)/45 = 226.7 W
W_c2, W_c1 = 1.5 * (T0 - 4.2) / 4.2, 40 * (T0 - 45) / 45
W_in = 10700.0
# allocate input in proportion to Carnot work (same eta for both stages), then use Radebaugh bands
eta_common = (W_c1 + W_c2) / W_in
ETA = {'He_stage1': (0.10, 0.15), '4K': (0.008, 0.015), 'LN2': (0.30, 0.40)}   # (low, high) fraction of Carnot
# LN2 route, supply-energy basis: the first-stage heat is rejected by evaporating liquid that an industrial
# plant produced at 0.5-0.7 kWh per kg (Karabuga 2018); latent heat 199 kJ/kg at 1 bar.  Multiplier W/W:
LN2_SUPPLY = (0.5 * 3.6e6 / 199e3, 0.7 * 3.6e6 / 199e3)      # 9.05 .. 12.66 W of plant input per W intercepted
LN2_BASIS = os.environ.get('LN2_BASIS', 'supply')              # 'supply' (default) or 'eta' (fraction-of-Carnot)
ETA_PT415_alloc = eta_common
print(f"PT415 combined fraction of Carnot = {eta_common:.3f}  (Carnot work 4.2K {W_c2:.0f} W, 45K {W_c1:.0f} W, input {W_in:.0f} W)")

def carnot(T): return (T0 - T) / T

def ledger_row(label, Q1, Q2, T1, route):
    ideal = Q1 * carnot(T1) + Q2 * carnot(4.0)
    e2 = ETA['4K']
    if route == 'LN2' and LN2_BASIS == 'supply':
        m1_lo, m1_hi = LN2_SUPPLY                                 # W per W, independent of T1
    else:
        e1 = ETA['He_stage1'] if route == 'He' else ETA['LN2']; m1_lo, m1_hi = carnot(T1) / e1[1], carnot(T1) / e1[0]
    real_lo = Q1 * m1_lo + Q2 * carnot(4.0) / e2[1]
    real_hi = Q1 * m1_hi + Q2 * carnot(4.0) / e2[0]
    return dict(case=label, route=route, T1=T1, Q1_W=Q1, Q2_W=Q2, W_ideal_W=ideal, W_ideal_S1=Q1 * carnot(T1), W_ideal_S2=Q2 * carnot(4.0),
                W_real_lo_W=real_lo, W_real_hi_W=real_hi, W_real_mid_W=np.sqrt(real_lo * real_hi))

def main():
    f = os.path.join(DATA, 'enclosure_loads.csv')
    if os.path.isfile(f): L = pd.read_csv(f).set_index('case')
    else:
        print('WARNING: enclosure_loads.csv missing, using baseline production values')
        L = pd.DataFrame({'radiation_W': [8.411, 8.383, 0.005287, 0.02974], 'conduction_W': [1.029, 0.962, 0.07029, 0.1621]},
                         index=['s1_50K_base', 's1_77K_base', 's2_from50K_base', 's2_from77K_base'])
    def tot(c): return L.loc[c, 'radiation_W'] + L.loc[c, 'conduction_W']
    rows = []
    for shield in ('base', 'mli'):
        for route, T1, s1, s2 in (('He', 50.0, 's1_50K', 's2_from50K'), ('LN2', 77.0, 's1_77K', 's2_from77K')):
            # central values: row-normalised view factors (best CFD); 'base' production kept as the upper band
            # row-normalised matrix is the central value for BOTH shields when available
            if shield == 'base':
                c1 = f'{s1}_norm250' if f'{s1}_norm250' in L.index else f'{s1}_base'
            else:
                c1 = f'{s1}_mli_norm250' if f'{s1}_mli_norm250' in L.index else f'{s1}_mli'
            c2 = f'{s2}_norm250' if f'{s2}_norm250' in L.index else f'{s2}_base'
            if c1 not in L.index: continue
            r = ledger_row(f'{route}_{shield}', tot(c1), tot(c2), T1, route)
            for band in ('epsLo', 'epsHi', 'base'):
                cb = f'{s1}_{band}'
                if cb in L.index and shield == 'base':
                    r[f'W_ideal_{band}'] = ledger_row('', tot(cb), tot(c2), T1, route)['W_ideal_W']
                    r[f'W_real_mid_{band}'] = ledger_row('', tot(cb), tot(c2), T1, route)['W_real_mid_W']
            rows.append(r)
    df = pd.DataFrame(rows); df.to_csv(os.path.join(DATA, 'ledger.csv'), index=False); print(df.to_string())
    # ---- figure: grouped bars, ideal and real, bare and MLI ----
    fig, axes = plt.subplots(1, 2, figsize=(5.4, 3.15))   # a little extra height for the shared legend below
    for ax, shield, ttl in zip(axes, ('base', 'mli'), ('(a) bare polished shield', '(b) MLI-equivalent shield ($\\varepsilon$ = 0.003)')):
        d = df[df.case.str.endswith(shield)]
        if d.empty: ax.set_title(ttl + ' [pending]'); continue
        x = np.arange(len(d)); w = 0.36
        cols = ['#B85042' if r == 'He' else '#50708E' for r in d.route]
        ax.bar(x - w / 2, d.W_ideal_S1, w, color=cols, alpha=0.55, label='ideal: stage 1')
        ax.bar(x - w / 2, d.W_ideal_S2, w, bottom=d.W_ideal_S1, color=cols, alpha=1.0, label='ideal: 4 K stage')
        ax.bar(x + w / 2, d.W_real_mid_W, w, color=cols, hatch='//', alpha=0.6, label='real (hardware $\\eta$)')
        ax.errorbar(x + w / 2, d.W_real_mid_W, yerr=[d.W_real_mid_W - d.W_real_lo_W, d.W_real_hi_W - d.W_real_mid_W], fmt='none', ecolor='k', capsize=3, lw=0.8)
        if 'W_ideal_epsLo' in d and shield == 'base':
            ax.errorbar(x - w / 2, d.W_ideal_W, yerr=[d.W_ideal_W - d.W_ideal_epsLo, d.W_ideal_epsHi - d.W_ideal_W], fmt='none', ecolor='k', capsize=3, lw=0.8)
        ax.set_xticks(x); ax.set_xticklabels([f'{r} route\n$T_1$ = {int(t)} K' for r, t in zip(d.route, d.T1)])
        ax.set_yscale('log'); ax.set_ylabel('room-temperature power [W]'); ax.set_title(ttl, fontsize=9)
        for xi, (wi, wr) in enumerate(zip(d.W_ideal_W, d.W_real_mid_W)):
            ax.text(xi - w / 2 - 0.12, wi * 1.05, f'{wi:.0f} W', ha='right', fontsize=7); ax.text(xi + w / 2 + 0.12, wr * 1.05, f'{wr:.0f} W', ha='left', fontsize=7)
        # headroom so the top error bar and its label never touch the frame; room on the left for the ideal labels
        ax.set_ylim(top=float(d.W_real_hi_W.max()) * 1.8); ax.set_xlim(-0.72, len(d) - 0.28)
    # one shared legend below both panels (nothing drawn over the data)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', ncol=3, fontsize=7, frameon=False, bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=[0, 0.085, 1, 1]); fig.savefig(os.path.join(FIG, 'fig8_ledger.png')); fig.savefig(os.path.join(FIG, 'fig8_ledger.pdf')); plt.close(fig)

if __name__ == '__main__': main()


# ----------------------------------------------------------------------------------------------
# Coupled operating points: the 4 K-stage load evaluated at the first-stage plate temperature that
# each route's cold plate actually reaches (hx_sweep area-mean wall temperature), instead of the
# nominal 50 / 77 K.  Harness conduction from the NIST conductivity fits (304 SS, PTFE) with the
# cable areas and lengths of the enclosure model (reproduces 70.3 / 162.0 mW and 1029 / 962 mW);
# residual radiation scaled from the row-normalised 50 K value with (T1^4 - 4^4).
# ----------------------------------------------------------------------------------------------
NIST_SS304 = [-1.4087, 1.3982, 0.2543, -0.6260, 0.2334, 0.4256, -0.4658, 0.1650, -0.0199]
NIST_PTFE = [2.7380, -30.677, 89.430, -136.99, 124.69, -69.556, 23.320, -4.3135, 0.33829]
A_SS, A_PTFE, N_LINES, L_S1, L_S2 = 1.790e-6, 2.001e-6, 65, 0.335, 0.245
RAD2_50K, RAD1_50K, RAD1_77K, RAD1_50K_MLI, RAD1_77K_MLI = 3.162e-3, 7.3637, 7.3374, 1.6908, 1.6848

def _k(c, T):
    l = np.log10(T); return 10 ** sum(a * l ** i for i, a in enumerate(c))
def _integ(c, a, b):
    T = np.linspace(a, b, 4000); return np.trapezoid(_k(c, T), T) if hasattr(np, 'trapezoid') else np.trapz(_k(c, T), T)
def harness_conduction(Ta, Tb, L): return N_LINES / L * (A_SS * _integ(NIST_SS304, Ta, Tb) + A_PTFE * _integ(NIST_PTFE, Ta, Tb))
def loads_at(route, T1, mli):
    base, Tb = (RAD1_50K_MLI if mli else RAD1_50K, 50) if route == 'He' else (RAD1_77K_MLI if mli else RAD1_77K, 77)
    Q1 = base * (300 ** 4 - T1 ** 4) / (300 ** 4 - Tb ** 4) + harness_conduction(T1, 300, L_S1)
    Q2 = harness_conduction(4.0, T1, L_S2) + RAD2_50K * (T1 ** 4 - 4 ** 4) / (50 ** 4 - 4 ** 4)
    return Q1, Q2
SCENARIOS = [  # (label, He plate T [K], LN2 plate T [K], He pumping power [W] charged at a 50 % circulator efficiency)
    ('nominal 50 / 77 K (decoupled)', 50.0, 77.0, 0.0),
    ('matched Re = 2300 (He 1 bar laminar, LN2 laminar)', 67.05, 81.24, 1.39e-3),
    ('own design points (He Re = 1e4, LN2 Re = 2300)', 50.28, 81.24, 65.1e-3),
    ('both turbulent, Re = 1e4', 50.28, 77.84, 65.1e-3)]
def coupled_ledger():
    rows = []
    for mli in (False, True):
        for lab, Th, Tn, Wp in SCENARIOS:
            for route, T1 in (('He', Th), ('LN2', Tn)):
                Q1, Q2 = loads_at(route, T1, mli); Tm = 50.0 if route == 'He' else 77.0
                r = ledger_row(f'{route}_{"mli" if mli else "base"}_{lab}', Q1, Q2, Tm, route)
                if route == 'He':
                    for k in ('W_real_lo_W', 'W_real_hi_W', 'W_real_mid_W'): r[k] += Wp / 0.5
                r.update(scenario=lab, shield='mli' if mli else 'base', T_plate_K=T1); rows.append(r)
    df = pd.DataFrame(rows); df.to_csv(os.path.join(DATA, 'ledger_coupled.csv'), index=False)
    for (sh, lab), g in df.groupby(['shield', 'scenario'], sort=False):
        he, n2 = g[g.route == 'He'].iloc[0], g[g.route == 'LN2'].iloc[0]
        print(f"[{sh}] {lab:50s} He {he.T_plate_K:5.1f} K: Q2={he.Q2_W*1e3:5.1f} mW ideal={he.W_ideal_W:5.1f} real={he.W_real_mid_W:5.0f} | "
              f"LN2 {n2.T_plate_K:5.1f} K: Q2={n2.Q2_W*1e3:5.1f} mW ideal={n2.W_ideal_W:5.1f} real={n2.W_real_mid_W:5.0f} | "
              f"ideal LN2 by {100*(1-n2.W_ideal_W/he.W_ideal_W):+.0f} %, real He by {100*(1-he.W_real_mid_W/n2.W_real_mid_W):.0f} % ({100*(1-he.W_real_lo_W/n2.W_real_lo_W):.0f}-{100*(1-he.W_real_hi_W/n2.W_real_hi_W):.0f})")
    return df

if __name__ == '__main__': coupled_ledger()
