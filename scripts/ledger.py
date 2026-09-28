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
ETA_PT415_alloc = eta_common
print(f"PT415 combined fraction of Carnot = {eta_common:.3f}  (Carnot work 4.2K {W_c2:.0f} W, 45K {W_c1:.0f} W, input {W_in:.0f} W)")

def carnot(T): return (T0 - T) / T

def ledger_row(label, Q1, Q2, T1, route):
    ideal = Q1 * carnot(T1) + Q2 * carnot(4.0)
    e1 = ETA['He_stage1'] if route == 'He' else ETA['LN2']; e2 = ETA['4K']
    real_lo = Q1 * carnot(T1) / e1[1] + Q2 * carnot(4.0) / e2[1]
    real_hi = Q1 * carnot(T1) / e1[0] + Q2 * carnot(4.0) / e2[0]
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
            c1 = f'{s1}_norm250' if (shield == 'base' and f'{s1}_norm250' in L.index) else f'{s1}_{shield}'
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
    fig, axes = plt.subplots(1, 2, figsize=(6.5, 3.4))
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
    axes[0].legend(fontsize=7, loc='upper left')
    fig.tight_layout(); fig.savefig(os.path.join(FIG, 'fig8_ledger.png')); fig.savefig(os.path.join(FIG, 'fig8_ledger.pdf')); plt.close(fig)

if __name__ == '__main__': main()
