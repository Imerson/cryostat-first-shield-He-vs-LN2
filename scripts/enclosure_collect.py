#!/usr/bin/env python3
"""enclosure_collect.py -- gather the enclosure baseline + variant heat loads into
data/enclosure_loads.csv and regenerate Fig. 2 (loads by mechanism with emissivity bands and
MLI variant) and Fig. 3 (view-factor agglomeration refinement with closure).
Inputs: cfd_campaign/enclosure_variants/<case>/postProcessing/heatLoadSummary/heat_load_summary.dat
        cfd_campaign/enclosure_variants/<case>/GATE_CHECK_vacuum.txt   (VF closure line)
"""
import os, re, glob, numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..')
VAR = os.path.join(ROOT, 'cfd_campaign', 'enclosure_variants'); DATA = os.path.join(ROOT, 'data'); FIG = os.path.join(ROOT, 'figures')
plt.rcParams.update({'font.size': 9, 'font.family': 'DejaVu Serif', 'axes.grid': True, 'grid.alpha': 0.3, 'figure.dpi': 300, 'savefig.bbox': 'tight'})
C_RAD, C_CON = '#E8A87C', '#1E2761'
SIG = 5.670374e-8
BASE = {  # production baseline (validated 2026-06-21)
    's1_50K_base': (8.411264, 1.029089, 300, 50), 's1_77K_base': (8.383, 0.962, 300, 77),
    's2_from50K_base': (0.005287, 0.070294, 50, 4), 's2_from77K_base': (0.02974, 0.1621, 77, 4)}
AREA_EQ = 7.073 / (SIG * (300 ** 4 - 50 ** 4) / (1 / 0.04 + 1 / 0.02 - 1))   # equivalent exchange area from the anchor

def analytic_rad(Th, Tc, ew, ec): return AREA_EQ * SIG * (Th ** 4 - Tc ** 4) / (1 / ew + 1 / ec - 1)

def read_case(d):
    f = os.path.join(d, 'postProcessing', 'heatLoadSummary', 'heat_load_summary.dat')
    if not os.path.isfile(f): return None
    v = {}
    for ln in open(f):
        if ln.startswith('#'): continue
        k, x = ln.split()[:2]; v[k] = float(x)
    clos = np.nan
    g = os.path.join(d, 'GATE_CHECK_vacuum.txt')
    if os.path.isfile(g):
        m = re.search(r'closure[^0-9]*([0-9.]+)\s*%', open(g).read(), re.I)
        if m: clos = float(m.group(1))
    return dict(radiation_W=v['radiation_on_cold'], conduction_W=v['conduction_coax_CFD'], total_W=v['TOTAL'], vf_closure_pct=clos)

def main():
    rows = []
    for k, (r, c, Th, Tc) in BASE.items():
        rows.append(dict(case=k, Th=Th, Tc=Tc, radiation_W=r, conduction_W=c, total_W=r + c, vf_closure_pct=np.nan))
    for d in sorted(glob.glob(os.path.join(VAR, 's*_*'))):
        v = read_case(d)
        if v is None: continue
        name = os.path.basename(d)
        if name.startswith('s2'): Th, Tc = (50 if '50K' in name else 77), 4
        else: Th, Tc = 300, (50 if '50K' in name else 77)
        # closure from the normalisation log (mean row sum before normalisation) if present
        nl = os.path.join(d, 'log.normalise')
        if os.path.isfile(nl):
            mm = re.findall(r'row-sum mean ([0-9.]+)', open(nl).read())
            if mm: v['vf_closure_pct'] = 100 * float(np.mean([float(x) for x in mm]))
        rows.append(dict(case=name, Th=Th, Tc=Tc, **v))
    df = pd.DataFrame(rows); df.to_csv(os.path.join(DATA, 'enclosure_loads.csv'), index=False); print(df.to_string())
    # ---- Fig 2 ----
    order = ['s1_50K_base', 's1_77K_base', 's2_from50K_base', 's2_from77K_base', 's1_50K_mli', 's1_77K_mli']
    labs = ['300$\\to$50 K', '300$\\to$77 K', '50$\\to$4 K', '77$\\to$4 K', '300$\\to$50 K\nMLI-eq.', '300$\\to$77 K\nMLI-eq.']
    d = df.set_index('case'); keep = [(o, l) for o, l in zip(order, labs) if o in d.index]
    fig, ax = plt.subplots(figsize=(6.0, 3.6)); x = np.arange(len(keep))
    rad = np.array([d.loc[o, 'radiation_W'] for o, _ in keep]); con = np.array([d.loc[o, 'conduction_W'] for o, _ in keep])
    ax.bar(x, rad, 0.55, color=C_RAD, label='radiation'); ax.bar(x, con, 0.55, bottom=rad, color=C_CON, label='harness conduction')
    for i, (o, _) in enumerate(keep):
        t = rad[i] + con[i]; ax.text(i, t * 1.3, f'{t:.2f} W' if t > 1 else f'{t*1e3:.0f} mW', ha='center', fontsize=8)
        lo, hi = o.replace('base', 'epsLo'), o.replace('base', 'epsHi')
        if lo != o and lo in d.index and hi in d.index:
            ax.errorbar(i, t, yerr=[[max(0.0, t - d.loc[lo, 'total_W'])], [max(0.0, d.loc[hi, 'total_W'] - t)]], fmt='none', ecolor='k', capsize=4, lw=0.9)
    ax.set_yscale('log'); ax.set_ylim(1e-3, 80); ax.set_xticks(x); ax.set_xticklabels([l for _, l in keep], fontsize=8)
    ax.set_ylabel('stage heat load [W]'); ax.legend(fontsize=8, loc='upper right')
    ax.text(0.5, 30, 'error bars: emissivity $\\pm$50 %', fontsize=7.5, color='k')
    fig.savefig(os.path.join(FIG, 'fig2_cascade_loads.png')); fig.savefig(os.path.join(FIG, 'fig2_cascade_loads.pdf')); plt.close(fig)
    # ---- Fig 3: agglomeration ----
    lv = [(60, 9.455681, np.nan), (250, 8.411264, 98.3)]
    for n, cl in ((400, 98.3), (800, np.nan)):
        k = f's1_50K_agg{n}'
        if k in d.index: lv.append((n, d.loc[k, 'radiation_W'], cl))
    lv.sort(); n_, q_, c_ = zip(*lv)
    fig, ax = plt.subplots(figsize=(4.8, 3.3))
    ax.plot(n_, q_, 'o-', color=C_CON, ms=6); ax.axhline(7.073, ls='--', color='#B85042'); ax.text(65, 6.75, 'closed-form grey-body value 7.07 W', color='#B85042', fontsize=8)
    for n, q, c in lv:
        ax.annotate(f'{q:.2f} W', (n, q), textcoords='offset points', xytext=(5, 6), fontsize=7)
    if 's1_50K_norm250' in d.index:
        ax.plot([250], [d.loc['s1_50K_norm250', 'radiation_W']], 's', color='#50708E', ms=7, label='250 faces, rows of $F$ normalised')
        ax.annotate('row-normalised $F$', (250, d.loc['s1_50K_norm250', 'radiation_W']), textcoords='offset points', xytext=(10, 4), fontsize=7.5, color='#50708E')
    ax.plot([], [], 'o-', color=C_CON, label='as generated (agglomeration sweep)'); ax.legend(fontsize=7.5, loc='lower left')
    ax.set_xscale('log'); ax.set_xlabel('coarsest-level faces per patch (view-factor agglomeration)'); ax.set_ylabel('first-stage radiative load [W]')
    fig.savefig(os.path.join(FIG, 'fig3_radiation_sweep.png')); fig.savefig(os.path.join(FIG, 'fig3_radiation_sweep.pdf')); plt.close(fig)

if __name__ == '__main__': main()
