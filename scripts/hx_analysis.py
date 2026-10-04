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
if not os.path.isdir(CAMP): CAMP = os.path.join(ROOT, 'hx_sweep')   # public-repo layout
DATA = os.path.join(ROOT, 'data'); FIG = os.path.join(ROOT, 'figures')
plt.rcParams.update({'font.size': 9, 'font.family': 'DejaVu Serif', 'axes.grid': True,
                     'grid.alpha': 0.3, 'figure.dpi': 300, 'savefig.bbox': 'tight'})
C_HE, C_N2 = '#B85042', '#50708E'
TSAT_N2_1BAR, TSAT_N2_3BAR, TSAT_N2_5BAR = 77.36, 87.91, 94.00   # CoolProp/NIST saturation temperatures
TSAT_N2 = TSAT_N2_5BAR                 # nitrogen loop pressure: 5 bar (the Boussinesq solution is pressure-independent)
Q_W, A_HEAT, DH, L = 9.4, 0.015, 0.01, 0.30

def gnielinski(Re, Pr, f):
    return (f / 8) * (Re - 1000) * Pr / (1 + 12.7 * math.sqrt(f / 8) * (Pr ** (2 / 3) - 1))

def load():
    rows = []
    for d in sorted(glob.glob(os.path.join(CAMP, '*'))):
        m = os.path.join(d, 'metrics.csv')
        if not os.path.isfile(m): continue
        r = pd.read_csv(m).iloc[0].to_dict()
        name = os.path.basename(d); r['case'] = name     # directory name is the case identity (metrics.csv 'case' omits suffixes)
        r['gON'] = name.endswith('_gON'); name_core = name.replace('_gON', '')
        if 'gci' in name_core: r['gci'] = name_core.split('_')[-1]
        elif 'varprop' in name_core: r['gci'] = 'varprop'      # variable-property sensitivity run (He mu(T), k(T) polynomials)
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
        # heated-wall patch statistics (surfaceFieldValue max / min / areaAverage on the patch itself)
        def sfv(name):
            f = sorted(glob.glob(os.path.join(d, 'postProcessing', name, '*', 'surfaceFieldValue*.dat')))
            if not f: return np.nan
            return float([l for l in open(f[-1]) if not l.startswith('#')][-1].split()[1])
        r['Tw_max'] = sfv('wallTmax'); r['Tw_min'] = sfv('wallTmin'); r['Tw_mean_patch'] = sfv('wallTmean')
        # legacy line sample 0.4 mm inside the fluid (kept for the record; NOT a wall temperature)
        prof = sorted(glob.glob(os.path.join(d, 'postProcessing', 'sampleWall', '**', 'wallCentre_T.xy'), recursive=True))
        r['Tw_line_max'] = np.loadtxt(prof[-1])[:, 1].max() if prof else np.nan
        # face-centre maximum along the channel-1 centre row of the heated wall (wall_faces.py)
        ws = os.path.join(d, 'postProcessing', 'wallFaces', 'wall_stats.csv')
        r['Tw_cl_max'] = pd.read_csv(ws).centreline_max_K.iloc[0] if os.path.isfile(ws) else np.nan
        r['Tw_mean'] = r['Tw_K']; r['dT_super'] = r['Tw_K'] - r['Tb_K']
        r['sat_margin'] = (TSAT_N2 - r['Tw_max']) if r['fluid'] == 'LN2' else np.nan
        r['sat_margin_3bar'] = (TSAT_N2_3BAR - r['Tw_max']) if r['fluid'] == 'LN2' else np.nan
        r['Qvol_m3_s'] = r['mdot_kg_s'] / (r['dP_Pa'] * 0 + (r['mdot_kg_s'] / (r['Wpump_W'] / r['dP_Pa']))) if r['dP_Pa'] > 0 else np.nan
        rows.append(r)
    df = pd.DataFrame(rows)
    df = df.sort_values(['fluid', 'P_bar', 'Re_target']).reset_index(drop=True)
    df.to_csv(os.path.join(DATA, 'hx_sweep_all.csv'), index=False)
    return df

T_LIM_HE = TSAT_N2_1BAR               # helium plate no warmer than an LN2 bath plate (77.4 K)
T_LIM_N2 = TSAT_N2 - 2.0              # single phase with a 2 K margin at the 5 bar loop pressure (92.0 K)

def optimum_points(p):
    """Minimum pumping power subject to a wall-temperature limit, per fluid, from the production sweep,
    under two criteria: 'max' = local maximum over the heated-wall patch (the saturation / hot-spot
    criterion); 'mean' = area-mean wall temperature (the heat-transfer-coefficient criterion).
    Helium 1 bar: for 'max' the laminar runs never meet 77.4 K and the laminar->SST transition is not
    interpolated, so the first feasible run (Re = 5000, SST) is reported; for 'mean' the laminar curve
    crosses the limit between two runs and Re* is interpolated linearly in T, pumping power log-log.
    5 and 18 bar: pumping power scaled by the pressure-series ratios measured at Re = 2300 (wall
    temperature is pressure-independent to four figures).  Nitrogen: lowest-Re run meeting the limit."""
    out = []
    ref = p[(p.fluid == 'He') & (p.Re_target == 2300) & (~p.gON)].set_index('P_bar').Wpump_W
    for crit, col_T in (('max', 'Tw_max'), ('mean', 'Tw_K')):
        he = p[(p.fluid == 'He') & (p.P_bar == 1) & (~p.gON)].sort_values('Re_target')
        T, R, W, turb = he[col_T].values, he.Re.values, he.Wpump_W.values, he.turbulent.values
        i = np.where(T <= T_LIM_HE)[0][0]
        if i > 0 and turb[i] == turb[i - 1]:                      # same regime: interpolate
            Re_s = R[i - 1] + (R[i] - R[i - 1]) * (T[i - 1] - T_LIM_HE) / (T[i - 1] - T[i])
            Wp_s = math.exp(np.interp(math.log(Re_s), np.log(R), np.log(W))); T_s = T_LIM_HE; interp = True
        else:                                                      # regime change: first feasible run
            Re_s, Wp_s, T_s, interp = R[i], W[i], T[i], False
        for P in (1, 5, 18):
            if P not in ref.index: continue
            out.append(dict(crit=crit, fluid='He', P_bar=P, Re=Re_s, Wp_W=Wp_s * ref[P] / ref[1], T_K=T_s, interpolated=interp,
                            col=C_HE, label=('optimum, He 1 / 5 / 18 bar (%s)' % ('local max' if crit == 'max' else 'plate mean')) if P == 1 else None))
        n2 = p[(p.fluid == 'LN2') & (~p.gON)].sort_values('Re_target')
        ok = n2[n2[col_T] <= T_LIM_N2].iloc[0]
        out.append(dict(crit=crit, fluid='LN2', P_bar=5, Re=ok.Re, Wp_W=ok.Wpump_W, T_K=ok[col_T], interpolated=False, col=C_N2,
                        label='optimum, LN$_2$ (%s)' % ('local max' if crit == 'max' else 'plate mean')))
    pd.DataFrame([{k: v for k, v in o.items() if k != 'col'} for o in out]).to_csv(os.path.join(DATA, 'hx_optimum_points.csv'), index=False)
    for o in out: print(f"OPTIMUM [{o['crit']}] {o['fluid']} {o['P_bar']} bar: Re={o['Re']:.0f}  Wp={o['Wp_W']*1e6:.2f} uW  T={o['T_K']:.1f} K  interp={o['interpolated']}")
    return out

def fig_maps(df):
    p = df[df.gci == 'production']
    fig, ax = plt.subplots(2, 2, figsize=(5.4, 5.9)); ax = ax.ravel()
    for fl, col, lab in (('He', C_HE, 'He gas, 1 bar'), ('LN2', C_N2, 'LN$_2$ liquid, 77 K')):
        s = p[(p.fluid == fl) & (p.P_bar.isin([1, 3]))].sort_values('Re_target')
        lam, tur = s[~s.turbulent], s[s.turbulent]
        for sub, mk in ((lam, 'o'), (tur, 's')):
            if sub.empty: continue
            ax[0].plot(sub.Re, sub.h_W_m2K, mk + '-', color=col, ms=5, label=f'{lab} ({"SST" if mk=="s" else "laminar"})')
            ax[1].plot(sub.Re, sub.dT_super, mk + '-', color=col, ms=5)
            ax[2].plot(sub.Re, sub.Wpump_W * 1e3, mk + '-', color=col, ms=5)
        ax[3].plot(s.Re, s.Tw_max, 'o-', color=col, ms=5, label='hottest face of the heated wall' if fl == 'He' else None)
        ax[3].plot(s.Re, s.Tw_K, 'o--', color=col, ms=5, mfc='none', label='area mean of the heated wall' if fl == 'He' else None)
    # He pressure series
    hp = p[(p.fluid == 'He') & (p.Re_target == 2300)].sort_values('P_bar')
    ax[2].plot(hp.Re, hp.Wpump_W * 1e3, 'v', color=C_HE, ms=6, mfc='none', label='He at 5, 18 bar')
    for _, r in hp.iterrows(): ax[2].annotate(f'{r.P_bar} bar', (r.Re, r.Wpump_W * 1e3), textcoords='offset points', xytext=(6, -3), fontsize=7)
    for Tsat, lab, yoff in ((TSAT_N2_5BAR, 'N$_2$ saturation, 5 bar (94.0 K)', 0.6), (TSAT_N2_3BAR, 'N$_2$ saturation, 3 bar (87.9 K)', 0.6)):
        ax[3].axhline(Tsat, color=C_N2, ls='--', lw=1); ax[3].text(9800, Tsat + yoff, lab, color=C_N2, fontsize=7, ha='right', va='bottom')
    ax[3].axhline(TSAT_N2_1BAR, color='grey', ls=':', lw=1); ax[3].text(9800, 75.9, 'N$_2$ saturation, 1 bar (77.4 K)', color='grey', fontsize=7, ha='right', va='top')
    ax[3].set_ylim(44, 110)
    # --- optimum operating points: minimum pumping power subject to T_w,max <= T_lim ---------
    # helium: plate no warmer than a nitrogen-bath plate (77.4 K); nitrogen: single phase with 2 K margin
    opt = optimum_points(p)
    for o in opt:
        kw = dict(color=o['col'], ms=11, mec='k', mew=0.5, zorder=6) if o['crit'] == 'max' else dict(color='none', ms=11, mec=o['col'], mew=1.0, zorder=6)
        ax[2].plot(o['Re'], o['Wp_W'] * 1e3, '*', label=o['label'], **kw)
        ax[3].plot(o['Re'], o['T_K'], '*', **kw)
    for a in ax: a.set_xscale('log'); a.set_xlabel('$Re$')
    ax[0].set_yscale('log'); ax[0].set_ylabel('$h$ [W m$^{-2}$ K$^{-1}$]')
    ax[1].set_yscale('log'); ax[1].set_ylabel('wall superheat $T_w-T_b$ [K]')
    ax[2].set_yscale('log'); ax[2].set_ylabel('pumping power [mW]')
    ax[3].set_ylabel('heated-wall temperature [K]')
    for a, t in zip(ax, 'abcd'): a.set_title(f'({t})', loc='left', fontsize=9)
    h0, l0 = ax[0].get_legend_handles_labels(); h2, l2 = ax[2].get_legend_handles_labels(); h3, l3 = ax[3].get_legend_handles_labels()
    fig.legend(h0 + h3 + h2, l0 + l3 + l2, loc='lower center', ncol=2, fontsize=8, frameon=False, bbox_to_anchor=(0.5, 0.0), handlelength=2.2, columnspacing=1.2)
    fig.tight_layout(rect=[0, 0.16, 1, 1]); fig.savefig(os.path.join(FIG, 'fig5_operating_maps.png')); fig.savefig(os.path.join(FIG, 'fig5_operating_maps.pdf')); plt.close(fig)

def fig_profiles(df):
    fig, ax = plt.subplots(1, 2, figsize=(5.4, 3.3))
    for fl, col in (('He', C_HE), ('LN2', C_N2)):
        for Re, ls in ((500, ':'), (2300, '-'), (10000, '--')):
            P = 1 if fl == 'He' else 3
            d = os.path.join(CAMP, f'{fl}_{P}bar_Re{Re}')
            wf = os.path.join(d, 'postProcessing', 'wallFaces', 'wall_centreline.csv')   # heated-wall face values, channel-1 centre row
            if not os.path.isfile(wf): continue
            a = pd.read_csv(wf).values; Tin = 45.0 if fl == 'He' else 77.0
            ax[0].plot(a[:, 0] / L, a[:, 1] - Tin, ls, color=col, lw=1.3, label=f'{"He" if fl == "He" else "LN$_2$"}, $Re$ = {Re}')
            prof2 = sorted(glob.glob(os.path.join(d, 'postProcessing', 'sampleWall', '**', 'profileZ_T.xy'), recursive=True))
            if prof2:
                b = np.loadtxt(prof2[-1]); ax[1].plot(b[:, 1] - Tin, b[:, 0] / DH, ls, color=col, lw=1.3)
    ax[0].set_xlabel('$x/L$ along heated-wall centreline'); ax[0].set_ylabel('$T_w - T_{in}$ [K]'); ax[0].set_yscale('log'); ax[0].set_ylim(1e-1, 80)
    ax[1].set_xlabel('$T - T_{in}$ [K] at $x/L=0.5$'); ax[1].set_ylabel('$z/D_h$ (0 = heated wall)')
    for a, t in zip(ax, 'ab'): a.set_title(f'({t})', loc='left', fontsize=9)
    h, l = ax[0].get_legend_handles_labels()
    fig.legend(h, l, loc='lower center', ncol=3, fontsize=9, frameon=False, bbox_to_anchor=(0.5, 0.0), handlelength=2.2, columnspacing=1.2)
    fig.tight_layout(rect=[0, 0.15, 1, 1]); fig.savefig(os.path.join(FIG, 'fig6_wall_profiles.png')); fig.savefig(os.path.join(FIG, 'fig6_wall_profiles.pdf')); plt.close(fig)

def fig_pareto(df):
    p = df[df.gci == 'production']
    fig, ax = plt.subplots(figsize=(4.6, 3.3))
    for fl, col, lab in (('He', C_HE, 'He 1 bar'), ('LN2', C_N2, 'LN$_2$ liquid, 77 K')):
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

def label(case):
    f, P, Re = case.split('_')[:3]
    lab = ('He' if f == 'He' else '\\LNtwo') + f" {P.replace('bar', '')}\\,bar $\\Re$={Re.replace('Re', '')}"
    if case.endswith('_gON'): lab += ' (g on)'
    if 'gci_coarse' in case: lab += ' (coarse grid)'
    if 'gci_fine' in case: lab += ' (fine grid)'
    if 'varprop' in case: lab += ' (variable properties)'
    return lab

def write_table_S6(df):
    """Supplementary all-runs table (manuscript/table_S6.tex) from the merged sweep data."""
    old = pd.read_csv(os.path.join(DATA, 'table_S6_all_runs.csv')).set_index('case')
    dfi = df.set_index('case')
    # cases added after the table was first built (e.g. the variable-property runs): start from the production
    # counterpart's row (Gr/Re^2 is a flow property shared with it) and overwrite everything metrics.csv provides
    for c in dfi.index:
        if c in old.index: continue
        base = c.replace('_varprop', '')
        if base not in old.index: continue
        row = old.loc[base].copy(); r = dfi.loc[c]
        for k in ('Re', 'P_bar', 'mdot_kg_s', 'dP_Pa', 'Wpump_W', 'Tin', 'Tw_K', 'dT_super', 'h_W_m2K', 'Nu', 'f_Darcy', 'NTU', 'eps', 'Lt_over_L', 'Mo', 'yplus_max', 'ebal_pct'):
            if k in r.index: row[k] = r[k]
        row['Qvol_cm3_s'] = r['Qvol_m3_s'] * 1e6; row['Tout'] = r['Tin'] + r['dTcool_K']
        old.loc[c] = row
    for c in ('Tw_max', 'Tw_min', 'Tw_cl_max', 'sat_margin', 'sat_margin_3bar'):
        old[c] = dfi[c]
    old = old.loc[[c for c in dfi.index if c in old.index]]          # same order as the sweep (fluid, P, Re)
    old.reset_index().to_csv(os.path.join(DATA, 'table_S6_all_runs.csv'), index=False)
    def g(v, fmt='{:.3g}'):
        return '--' if (v is None or (isinstance(v, float) and np.isnan(v))) else fmt.format(v)
    rows = []
    for case, r in old.iterrows():
        rows.append(' & '.join([label(case), g(r.Re, '{:.0f}'), g(r.mdot_kg_s * 1e3), g(r.Qvol_cm3_s), g(r.dP_Pa), g(r.Wpump_W * 1e6),
                    g(r.Tout, '{:.2f}'), g(r.Tw_K, '{:.1f}'), g(r.Tw_max, '{:.1f}'), g(r.Tw_min, '{:.1f}'), g(r.dT_super, '{:.2f}'), g(r.h_W_m2K),
                    g(r.Nu), g(r.f_Darcy), g(r.NTU), g(r.eps), g(r.Gr_Re2, '{:.2g}'), g(r.sat_margin, '{:.1f}'), g(r.yplus_max, '{:.1f}'),
                    g(r.ebal_pct, '{:.2f}')]) + ' \\\\')
    tex = r'''\begin{table}[H]\centering\scriptsize
\caption{All cold-plate runs at 9.4\,W (production mesh unless marked). $\dot m$ in g\,s$^{-1}$, volumetric flow in cm$^3$\,s$^{-1}$, $\Delta p$ in Pa, $\dot W_{\mathrm p}$ in $\mu$W, temperatures in K, $h$ in W\,m$^{-2}$K$^{-1}$; $T_{\mathrm{in}}$ = 45\,K (He), 77\,K (\LNtwo). $T_{\mathrm w}$ is the area mean over the heated-wall patch, $T_{\mathrm{w,max}}$ and $T_{\mathrm{w,min}}$ its extreme face values (\texttt{surfaceFieldValue} on the patch); margin = $T_{\mathrm{sat}}(5\,\mathrm{bar})-T_{\mathrm{w,max}}$ = $94.0\,\mathrm K-T_{\mathrm{w,max}}$; $y^+$ = maximum on the heated wall; closure = energy-balance error. Gravity-on (g on) nitrogen runs did not reach a steady state (see closure).}
\label{tab:S6}
\setlength{\tabcolsep}{2.2pt}
\resizebox{\textwidth}{!}{\begin{tabular}{l r r r r r r r r r r r r r r r r r r r}
\toprule
Case & $\Re$ & $\dot m$ & $\dot V$ & $\Delta p$ & $\dot W_{\mathrm p}$ & $T_{\mathrm{out}}$ & $T_{\mathrm w}$ & $T_{\mathrm{w,max}}$ & $T_{\mathrm{w,min}}$ & $T_{\mathrm w}-T_{\mathrm b}$ & $h$ & $\Nu$ & $f$ & NTU & $\varepsilon$ & Gr/$\Re^2$ & margin & $y^+$ & closure \% \\
\midrule
''' + '\n'.join(rows) + r'''
\bottomrule
\end{tabular}}
\end{table}
'''
    open(os.path.join(ROOT, 'manuscript', 'table_S6.tex'), 'w').write(tex)

if __name__ == '__main__':
    df = load(); print(df[['case', 'Re', 'Nu', 'h_W_m2K', 'dT_super', 'Wpump_W', 'Tw_K', 'Tw_mean_patch', 'Tw_max', 'Tw_cl_max', 'Tw_line_max', 'sat_margin', 'ebal_pct', 'yplus_max']].to_string())
    fig_maps(df); fig_profiles(df); fig_pareto(df); print(matched_pumping(df)); gci_he(df); write_table_S6(df)
    dp = df[(df.gci == 'production') & (df.Re_target == 2300)]
    dp.to_csv(os.path.join(DATA, 'hx_design_point.csv'), index=False)
