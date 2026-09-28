#!/usr/bin/env python3
"""Fig. 1 -- system schematic: the three first-shield pre-cooling routes compared in the paper,
where the passive enclosure model and the active cold-plate model connect, and which loads
enter the work ledger. Pure matplotlib, no data dependencies."""
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch, FancyBboxPatch
import os

OUT = os.path.join(os.path.dirname(__file__), '..', 'figures', 'fig1_schematic.png')
plt.rcParams.update({'font.size': 8.5, 'font.family': 'DejaVu Sans'})
C_WARM, C_S1, C_S2 = '#C8553D', '#588B8B', '#2F4858'
C_HE, C_N2, C_GREY = '#B85042', '#50708E', '#777777'

fig, axes = plt.subplots(1, 3, figsize=(10.5, 4.6), gridspec_kw={'wspace': 0.08})
titles = [('(a) Reference: conductive PTR first stage', 'He pulse tube, 1st stage 40--50 K'),
          ('(b) Route He: circulated helium gas', 'cold plate cooled by He gas, 45--50 K'),
          ('(c) Route N$_2$: liquid nitrogen', 'cold plate cooled by LN$_2$, 77 K, 3 bar')]

def stage_stack(ax, Ts1, route):
    ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis('off')
    # OVC / warm plate 300 K
    ax.add_patch(Rectangle((0.6, 8.3), 8.8, 0.55, fc=C_WARM, ec='k', lw=0.6))
    ax.text(5, 8.57, 'warm plate / OVC  300 K', ha='center', va='center', color='w', fontsize=8)
    # first-stage shield + plate
    ax.add_patch(Rectangle((1.2, 5.4), 7.6, 0.5, fc=C_S1, ec='k', lw=0.6))
    ax.text(5, 5.65, f'first shield  {Ts1}', ha='center', va='center', color='w', fontsize=8)
    ax.plot([1.2, 1.2], [5.4, 3.0], color=C_S1, lw=3); ax.plot([8.8, 8.8], [5.4, 3.0], color=C_S1, lw=3)
    # 4 K plate
    ax.add_patch(Rectangle((2.0, 2.5), 6.0, 0.5, fc=C_S2, ec='k', lw=0.6))
    ax.text(5, 2.75, '4 K plate', ha='center', va='center', color='w', fontsize=8)
    ax.text(5, 1.9, 'dilution unit / payload below 4 K: not modelled', ha='center', fontsize=7, color=C_GREY, style='italic')
    # harness lines
    for x in (3.0, 4.3, 5.7, 7.0):
        ax.plot([x, x], [8.3, 3.0], color='#333', lw=1.0)
    ax.text(7.2, 7.2, 'coaxial\nharness\n65 lines', fontsize=6.3, va='center')
    # radiation arrows Stage 1
    for x in (1.9, 2.4):
        ax.add_patch(FancyArrowPatch((x, 8.25), (x, 5.95), arrowstyle='-|>', mutation_scale=7, color=C_WARM, lw=0.8, ls=(0, (2, 1.5))))
    ax.text(0.15, 7.1, 'radiation\n$\\dot Q_{r,1}$', fontsize=6.5, color=C_WARM, va='center')
    ax.text(3.35, 7.5, '$\\dot Q_{c,1}$', fontsize=6.5, color='#333')
    # stage 2 loads
    ax.add_patch(FancyArrowPatch((2.4, 4.6), (2.4, 3.05), arrowstyle='-|>', mutation_scale=7, color=C_S1, lw=0.8, ls=(0, (2, 1.5))))
    ax.text(0.05, 3.1, 'residual\nradiation\n$\\dot Q_{r,2}$', fontsize=6, color=C_S1, va='center')
    ax.text(3.35, 3.5, '$\\dot Q_{c,2}$', fontsize=6.5, color='#333')
    # passive-model box
    ax.add_patch(FancyBboxPatch((0.5, 2.3), 9.0, 7.25, boxstyle='round,pad=0.05,rounding_size=0.2',
                                fc='none', ec=C_GREY, lw=0.8, ls='--'))
    ax.text(0.7, 9.25, 'Q1: enclosure CHT model (passive)', fontsize=6.5, color=C_GREY, ha='left', va='center')
    # route-specific cooling of stage 1
    if route == 'ptr':
        ax.add_patch(Rectangle((8.95, 5.2), 0.85, 2.9, fc='#ddd', ec='k', lw=0.6))
        ax.text(9.37, 6.65, 'PTR\n1st\nstage', ha='center', va='center', fontsize=6.5)
        ax.add_patch(Rectangle((8.9, 2.4), 0.9, 0.7, fc='#ddd', ec='k', lw=0.6))
        ax.text(9.35, 2.75, 'PTR\n2nd', ha='center', va='center', fontsize=5.5)
        ax.text(5, 0.9, 'first-stage duty removed by conduction to the PTR;\nno coolant circuit (used for the reference wall temperature only)', ha='center', fontsize=6.8)
    else:
        col = C_HE if route == 'he' else C_N2
        # channels in the plate
        # channelled cold plate bolted under the shield plate
        ax.add_patch(Rectangle((2.0, 4.75), 6.0, 0.45, fc='#e9eef0', ec=col, lw=0.8))
        for x in (2.7, 3.85, 5.0, 6.15, 7.3):
            ax.add_patch(Rectangle((x - 0.17, 4.82), 0.34, 0.31, fc='w', ec=col, lw=1.0))
        ax.add_patch(FancyArrowPatch((0.3, 4.97), (1.95, 4.97), arrowstyle='-|>', mutation_scale=8, color=col, lw=1.4))
        ax.add_patch(FancyArrowPatch((8.05, 4.97), (9.65, 4.97), arrowstyle='-|>', mutation_scale=8, color=col, lw=1.4))
        lab_in = 'He in\n45 K\n1--18 bar' if route == 'he' else 'LN$_2$ in\n77 K\n3 bar'
        ax.text(0.05, 4.05, lab_in, fontsize=6, color=col, va='top', ha='left')
        ax.text(9.95, 4.05, 'out', fontsize=6, color=col, ha='right', va='top')
        ax.text(5.0, 4.6, 'channelled cold plate: Q2 HX model (active)', fontsize=6.3, color=col, ha='center', va='top')
        src = 'He cryoplant / circulator\n(cf. ITER 80 K, LHC 50--75 K shields)' if route == 'he' else 'LN$_2$ supply (air-separation plant)\nboil-off or pressurised loop'
        ax.text(5, 0.9, 'first-stage duty $\\dot Q_1 = \\dot Q_{r,1}+\\dot Q_{c,1}$ removed by the coolant\n' + src, ha='center', fontsize=6.8)

for ax, (t1, t2), Ts1, route in zip(axes, titles, ('50 K', '50 K (nominal)', '77 K'), ('ptr', 'he', 'n2')):
    stage_stack(ax, Ts1, route)
    ax.set_title(f'{t1}\n{t2}', fontsize=8.5, pad=4)

fig.text(0.5, 0.005, 'Q3 work ledger: $\\dot W = \\sum_i \\dot Q_i\\,(T_0-T_i)/(T_i\\,\\eta_i)$ over the first-stage load $\\dot Q_1$ (at $T_1$) and the 4 K load $\\dot Q_2$ (at 4 K); '
         '$\\eta_i$ = 1 (ideal) or measured fraction of Carnot (real).', ha='center', fontsize=7.5)
fig.savefig(OUT, dpi=300, bbox_inches='tight'); print('wrote', OUT)
