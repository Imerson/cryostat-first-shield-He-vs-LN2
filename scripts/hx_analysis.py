#!/usr/bin/env python3
"""hx_analysis.py -- collect the cold-plate sweep (metrics.csv + wall profiles), build
Table 4 / Table S6, the operating maps (Fig. 5), wall-T profiles (Fig. 6), the Pareto /
matched-pumping-power comparison (Fig. 7) and the He GCI table.

Input : cfd_campaign/hx_sweep/<case>/{metrics.csv, postProcessing/sampleWall/<t>/*.xy, yplus_summary.txt}
Output: data/hx_sweep_all.csv, data/hx_design_point.csv, data/hx_gci_He.txt, figures/fig5_*.png ...
"""
import os, glob, math, json, sys
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..'); CAMP = os.path.join(ROOT, 'cfd_campaign', 'hx_sweep')
DATA = os.path.join(ROOT, 'data'); FIG = os.path.join(ROOT, 'figures')
plt.rcParams.update({'font.size': 9, 'font.family': 'DejaVu Serif', 'axes.grid': True,
                     'grid.alpha': 0.3, 'figure.dpi': 300, 'savefig.bbox': 'tight'})
C_HE, C_N2 = '#B85042', '#50708E'
TSAT_N2_3BAR = 87.91
Q_W, A_HEAT, DH, L = 9.4, 0.015, 0.01, 0.30

def gnielinski(Re, Pr, f):
    return (f / 8) * (Re - 1000) * Pr / (1 + 12.7 * math.sqrt(f / 8) * (Pr ** (2 / 3) - 1))

def load():
    rows = []
    for d in sorted(glob.glob(os.path.join(CAMP, '*'))):
        m = os.path.join(d, 'metrics.csv')
        if not os.path.isfile(m): continue
        r = pd.read_csv(m).iloc[0].to_dict()
        name = os.path.basename(d)
        r['gON'] = name.endswith('_gON'); name_core = name.replace('_gON', '')
        if 'gci' in name_core: r['gci'] = name_core.split('_')[-1]
        else: r['gci'] = 'production' if not r['gON'] else 'gON'
        parts = name_core.split('_'); r['fluid'] = parts[0]; r['P_bar'] = int(parts[1].replace('bar', ''))
        r['Re_target'] = int(parts[2].replace('Re', ''))
        mc = dict(l.strip().split('=', 1) for l in open(os.path.join(d, 'system', 'metricConstants')) if '=' in l)
        r['turbulent'] = mc.get('TURBULENT', '0') == '1'
        r['Tin'] = float(mc['Tin_K']) if 'Tin_K' in mc else (45.0 if r['fluid'] == 'He' else 77.0)
        yp = os.path.join(d, 'yplus_summary.txt')
        r['yplus_max'] = np.nan
        if os.path.isfile(yp):
            for ln in open(yp):
                if 'max' in ln:
                    try: r['yplus_max'] = float(ln.split('=')[-1].split()[0])
                    except: pass
        # wall-T profile max (heated-wall centreline) for saturation margin
        prof = sorted(glob.glob(os.path.join(d, 'postProcessing', 'sampleWall', '*', 'wallCentre_T.xy')))
        r['Tw_max'] = np.nan
        if prof:
            a = np.loadtxt(prof[-1]); r['Tw_max'] = a[:, 1].max()
        r['Tw_mean'] = r['Tw_K']; r['dT_super'] = r['Tw_K'] - r['Tb_K']
        r['sat_margin'] = (TSAT_N2_3BAR - r['Tw_max']) if r['fluid'] == 'LN2' else np.nan
        r['Qvol_m3_s'] = r['mdot_kg_s'] / (r['dP_Pa'] * 0 + (r['mdot_kg_s'] / (r['Wpump_W'] / r['dP_Pa']))) if r['dP_Pa'] > 0 else np.nan
        rows.append(r)
    df = pd.DataFrame(rows)
    df = df.sort_values(['fluid', 'P_bar', 'Re_target']).reset_index(drop=True)
    df.to_csv(os.path.join(DATA, 'hx_sweep_all.csv'), index=False)
    return df

def fig_maps(df):
    p = df[df.gci == 'production']
    fig, ax = plt.subplots(2, 2, figsize=(5.4, 5.3)); ax = ax.ravel()
    for fl, col, lab in (('He', C_HE, 'He gas, 1 bar'), ('LN2', C_N2, 'LN$_2$, 3 bar')):
        s = p[(p.fluid == fl) & (p.P_bar.isin([1, 3]))].sort_values('Re_target')
        lam, tur = s[~s.turbulent], s[s.turbulent]
        for sub, mk in ((lam, 'o'), (tur, 's')):
            if sub.empty: continue
            ax[0].plot(sub.Re, sub.h_W_m2K, mk + '-', color=col, ms=5, label=f'{lab} ({"SST" if mk=="s" else "laminar"})')
            ax[1].plot(sub.Re, sub.dT_super, mk + '-', color=col, ms=5)
            ax[2].plot(sub.Re, sub.Wpump_W * 1e3, mk + '-', color=col, ms=5)
        ax[3].plot(s.Re, s.Tw_max, 'o-', color=col, ms=5)
    # He pressure series
    hp = p[(p.fluid == 'He') & (p.Re_target == 2300)].sort_values('P_bar')
    ax[2].plot(hp.Re, hp.Wpump_W * 1e3, 'v', color=C_HE, ms=6, mfc='none', label='He at 5, 18 bar')
    for _, r in hp.iterrows(): ax[2].annotate(f'{r.P_bar} bar', (r.Re, r.Wpump_W * 1e3), textcoords='offset points', xytext=(6, -3), fontsize=7)
    ax[3].axhline(TSAT_N2_3BAR, color=C_N2, ls='--', lw=1); ax[3].text(9800, TSAT_N2_3BAR + 0.7, 'N$_2$ saturation, 3 bar (87.9 K)', color=C_N2, fontsize=7, ha='right', va='bottom')
    ax[3].axhline(77.36, color='grey', ls=':', lw=1); ax[3].text(9800, 75.9, 'N$_2$ saturation, 1 bar (77.4 K)', color='grey', fontsize=7, ha='right', va='top')
    ax[3].set_ylim(44, 102)
    for a in ax: a.set_xscale('log'); a.set_xlabel('$Re$')
    ax[0].set_yscale('log'); ax[0].set_ylabel('$h$ [W m$^{-2}$ K$^{-1}$]')
    ax[1].set_yscale('log'); ax[1].set_ylabel('wall superheat $T_w-T_b$ [K]')
    ax[2].set_yscale('log'); ax[2].set_ylabel('pumping power [mW]')
    ax[3].set_ylabel('maximum wall temperature [K]')
    for a, t in zip(ax, 'abcd'): a.set_title(f'({t})', loc='left', fontsize=9)
    h0, l0 = ax[0].get_legend_handles_labels(); h2, l2 = ax[2].get_legend_handles_labels()
    fig.legend(h0 + h2, l0 + l2, loc='lower center', ncol=3, fontsize=9, frameon=False, bbox_to_anchor=(0.5, 0.0), handlelength=2.2, columnspacing=1.2)
    fig.tight_layout(rect=[0, 0.09, 1, 1]); fig.savefig(os.path.join(FIG, 'fig5_operating_maps.png')); fig.savefig(os.path.join(FIG, 'fig5_operating_maps.pdf')); plt.close(fig)

def fig_profiles(df):
    fig, ax = plt.subplots(1, 2, figsize=(5.4, 3.3))
    for fl, col in (('He', C_HE), ('LN2', C_N2)):
        for Re, ls in ((500, ':'), (2300, '-'), (10000, '--')):
            P = 1 if fl == 'He' else 3
            d = os.path.join(CAMP, f'{fl}_{P}bar_Re{Re}')
            prof = sorted(glob.glob(os.path.join(d, 'postProcessing', 'sampleWall', '*', 'wallCentre_T.xy')))
            if not prof: continue
            a = np.loadtxt(prof[-1]); Tin = 45.0 if fl == 'He' else 77.0
            ax[0].plot(a[:, 0] / L, a[:, 1] - Tin, ls, color=col, lw=1.3, label=f'{"He" if fl == "He" else "LN$_2$"}, $Re$ = {Re}')
            prof2 = sorted(glob.glob(os.path.join(d, 'postProcessing', 'sampleWall', '*', 'profileZ_T.xy')))
            if prof2:
                b = np.loadtxt(prof2[-1]); ax[1].plot(b[:, 1] - Tin, b[:, 0] / DH, ls, color=col, lw=1.3)
    ax[0].set_xlabel('$x/L$ along heated-wall centreline'); ax[0].set_ylabel('$T_w - T_{in}$ [K]'); ax[0].set_yscale('log'); ax[0].set_ylim(1e-2, 80)
    ax[1].set_xlabel('$T - T_{in}$ [K] at $x/L=0.5$'); ax[1].set_ylabel('$z/D_h$ (0 = heated wall)')
    for a, t in zip(ax, 'ab'): a.set_title(f'({t})', loc='left', fontsize=9)
    h, l = ax[0].get_legend_handles_labels()
    fig.legend(h, l, loc='lower center', ncol=3, fontsize=9, frameon=False, bbox_to_anchor=(0.5, 0.0), handlelength=2.2, columnspacing=1.2)
    fig.tight_layout(rect=[0, 0.15, 1, 1]); fig.savefig(os.path.join(FIG, 'fig6_wall_profiles.png')); fig.savefig(os.path.join(FIG, 'fig6_wall_profiles.pdf')); plt.close(fig)

def fig_pareto(df):
    p = df[df.gci == 'production']
    fig, ax = plt.subplots(figsize=(4.6, 3.3))
    for fl, col, lab in (('He', C_HE, 'He 1 bar'), ('LN2', C_N2, 'LN$_2$ 3 bar')):
        s = p[(p.fluid == fl) & (p.P_bar.isin([1, 3]))].sort_values('Re_target')
        ax.plot(s.Wpump_W * 1e3, s.dT_super, 'o-', color=col, ms=5, label=lab)
        for _, r in s.iterrows(): ax.annotate(f'{int(r.Re_target)}', (r.Wpump_W * 1e3, r.dT_super), textcoords='offset points', xytext=(4, 3), fontsize=6.5, color=col)
    for P, mk in ((5, '^'), (18, 'v')):
        s = p[(p.fluid == 'He') & (p.P_bar == P)]
        ax.plot(s.Wpump_W * 1e3, s.dT_super, mk, color=C_HE, ms=7, mfc='none', label=f'He {P} bar, $Re$=2300')
    ax.set_xscale('log'); ax.set_yscale('log')
    ax.set_xlabel('pumping power [mW]'); ax.set_ylabel('wall superheat $T_w-T_b$ [K]')
    ax.legend(fontsize=7.5); fig.savefig(os.path.join(FIG, 'fig7_pareto.png')); fig.savefig(os.path.join(FIG, 'fig7_pareto.pdf')); plt.close(fig)

def matched_pumping(df):
    """Interpolate LN2 superheat/h at the pumping power of each He point (log-log)."""
    p = df[(df.gci == 'production')]
    n2 = p[(p.fluid == 'LN2')].sort_values('Wpump_W')
    out = []
    for _, r in p[p.fluid == 'He'].iterrows():
        if r.Wpump_W < n2.Wpump_W.min() or r.Wpump_W > n2.Wpump_W.max(): continue
        lw = np.log(n2.Wpump_W.values)
        h_n2 = np.exp(np.interp(np.log(r.Wpump_W), lw, np.log(n2.h_W_m2K.values)))
        dT_n2 = np.exp(np.interp(np.log(r.Wpump_W), lw, np.log(n2.dT_super.values)))
        out.append(dict(He_case=r.case, Wp_mW=r.Wpump_W * 1e3, h_He=r.h_W_m2K, h_N2_matched=h_n2, ratio_h=h_n2 / r.h_W_m2K,
                        dT_He=r.dT_super, dT_N2_matched=dT_n2, ratio_dT=r.dT_super / dT_n2))
    mp = pd.DataFrame(out); mp.to_csv(os.path.join(DATA, 'hx_matched_pumping.csv'), index=False); return mp

def gci_he(df):
    g = df[(df.fluid == 'He') & (df.Re_target == 2300) & (df.P_bar == 1)].set_index('gci')
    if not {'coarse', 'production', 'fine'} <= set(g.index): return None
    lines = ['He GCI (Celik 2008), Re=2300, 1 bar, r=1.5']
    for q in ('Nu', 'f_Darcy', 'h_W_m2K'):
        f1, f2, f3 = g.loc['fine', q], g.loc['production', q], g.loc['coarse', q]
        e21, e32 = f2 - f1, f3 - f2
        if e21 * e32 <= 0: lines.append(f'{q}: oscillatory/converged ({f3:.4g}, {f2:.4g}, {f1:.4g})'); continue
        pord = abs(math.log(abs(e32 / e21)) / math.log(1.5)); fext = f1 + (f1 - f2) / (1.5 ** pord - 1)
        gci21 = 1.25 * abs((f2 - f1) / f1) / (1.5 ** pord - 1) * 100; gci32 = 1.25 * abs((f3 - f2) / f2) / (1.5 ** pord - 1) * 100
        lines.append(f'{q}: coarse={f3:.4g} medium={f2:.4g} fine={f1:.4g} p={pord:.2f} ext={fext:.4g} GCI_fine={gci21:.2f}% GCI_medium={gci32:.2f}%')
    txt = '\n'.join(lines); open(os.path.join(DATA, 'hx_gci_He.txt'), 'w').write(txt); print(txt); return txt

if __name__ == '__main__':
    df = load(); print(df[['case', 'Re', 'Nu', 'h_W_m2K', 'dT_super', 'Wpump_W', 'Tw_max', 'sat_margin', 'ebal_pct', 'yplus_max']].to_string())
    fig_maps(df); fig_profiles(df); fig_pareto(df); print(matched_pumping(df)); gci_he(df)
    dp = df[(df.gci == 'production') & (df.Re_target == 2300)]
    dp.to_csv(os.path.join(DATA, 'hx_design_point.csv'), index=False)
