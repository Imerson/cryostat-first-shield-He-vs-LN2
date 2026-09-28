#!/usr/bin/env python3
"""Fig. 1 -- system schematic: the three first-shield pre-cooling routes compared in the paper,
where the passive enclosure model and the active cold-plate model connect, and which loads
enter the work ledger. Pure matplotlib, no data dependencies."""
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch, FancyBboxPatch
import os

OUT = os.path.join(os.path.dirname(__file__), '..', 'figures', 'fig1_schematic.png')
plt.rcParams.update({'font.size': 13, 'font.family': 'DejaVu Sans'})
C_WARM, C_S1, C_S2 = '#C8553D', '#588B8B', '#2F4858'
C_HE, C_N2, C_GREY = '#B85042', '#50708E', '#777777'

fig, axes = plt.subplots(1, 3, figsize=(10.5, 4.2), gridspec_kw={'wspace': 0.04})
titles = [('(a) reference: PTR first stage', '40--50 K, conductive'),
          ('(b) route He: circulated gas', '50 K nominal; 45 K in, 1--18 bar'),
          ('(c) route N$_2$: liquid nitrogen', '77 K in, 3 bar')]

def stage_stack(ax, Ts1, route):
    ax.set_xlim(0, 10); ax.set_ylim(0.2, 10); ax.axis('off')
    col = C_HE if route == 'he' else C_N2
    LINES = (3.6, 4.6, 5.8, 6.8)                  # harness x positions: labels at x < 3.5 or x > 7.0
    # passive-model box and label
    ax.add_patch(FancyBboxPatch((0.5, 2.3), 9.0, 7.25, boxstyle='round,pad=0.05,rounding_size=0.2', fc='none', ec=C_GREY, lw=0.8, ls='--'))
    ax.text(0.7, 9.25, 'Q1: enclosure CHT model (passive)', fontsize=7.6, color=C_GREY, ha='left', va='center')
    # warm plate / OVC
    ax.add_patch(Rectangle((0.6, 8.3), 8.8, 0.55, fc=C_WARM, ec='k', lw=0.6))
    ax.text(5, 8.57, 'warm plate / OVC  300 K', ha='center', va='center', color='w', fontsize=9.2)
    # first shield bar and legs
    ax.add_patch(Rectangle((1.2, 5.4), 7.6, 0.5, fc=C_S1, ec='k', lw=0.6))
    ax.text(1.35, 5.65, f'first shield  {Ts1}', ha='left', va='center', color='w', fontsize=8.6)
    ax.plot([1.2, 1.2], [5.4, 3.0], color=C_S1, lw=3); ax.plot([8.8, 8.8], [5.4, 3.0], color=C_S1, lw=3)
    # 4 K plate
    ax.add_patch(Rectangle((2.0, 2.5), 6.0, 0.5, fc=C_S2, ec='k', lw=0.6))
    ax.text(5, 2.75, '4 K plate', ha='center', va='center', color='w', fontsize=9.2)
    ax.text(5, 1.95, 'dilution unit below 4 K: not modelled', ha='center', va='center', fontsize=7.4, color=C_GREY, style='italic')
    # harness lines
    for x in LINES:
        ax.plot([x, x], [8.3, 3.0], color='#333', lw=1.0)
    ax.text(7.05, 7.3, 'coaxial\nharness\n65 lines', fontsize=7.4, va='center', ha='left')
    # radiation, stage 1
    for x in (2.75, 3.2):
        ax.add_patch(FancyArrowPatch((x, 8.25), (x, 5.95), arrowstyle='-|>', mutation_scale=7, color=C_WARM, lw=0.8, ls=(0, (2, 1.5))))
    ax.text(1.25, 7.2, 'radiation\n$\\dot Q_{r,1}$', fontsize=7.6, color=C_WARM, va='center', ha='left')
    ax.text(5.2, 7.5, '$\\dot Q_{c,1}$', fontsize=7.6, color='#333', ha='center')
    # stage 2 loads
    ax.add_patch(FancyArrowPatch((7.25, 4.7), (7.25, 3.05), arrowstyle='-|>', mutation_scale=7, color=C_S1, lw=0.8, ls=(0, (2, 1.5))))
    ax.text(7.4, 3.6, 'residual\nradiation\n$\\dot Q_{r,2}$', fontsize=6.6, color=C_S1, va='center', ha='left')
    ax.text(5.2, 3.6, '$\\dot Q_{c,2}$', fontsize=7.6, color='#333', ha='center')
    if route == 'ptr':
        ax.add_patch(Rectangle((8.9, 2.5), 0.55, 5.6, fc='#ddd', ec='k', lw=0.6))
        ax.text(9.17, 5.3, 'pulse-tube refrigerator (1st and 2nd stage)', ha='center', va='center', fontsize=6.3, rotation=90)
        ax.text(5, 1.15, 'duty removed by conduction to the PTR;\nno coolant circuit', ha='center', va='center', fontsize=8)
    else:
        # channelled cold plate under the shield bar, coolant in from the left, out to the right
        ax.add_patch(Rectangle((2.0, 4.75), 6.0, 0.45, fc='#e9eef0', ec=col, lw=0.8))
        for x in (2.5, 3.05, 5.2, 7.25, 7.7):
            ax.add_patch(Rectangle((x - 0.17, 4.82), 0.34, 0.31, fc='w', ec=col, lw=1.0))
        ax.add_patch(FancyArrowPatch((0.3, 4.97), (1.95, 4.97), arrowstyle='-|>', mutation_scale=8, color=col, lw=1.4))
        ax.add_patch(FancyArrowPatch((8.05, 4.97), (9.65, 4.97), arrowstyle='-|>', mutation_scale=8, color=col, lw=1.4))
        lab_in = 'He in, 45 K\n1--18 bar' if route == 'he' else 'LN$_2$ in, 77 K\n3 bar'
        ax.text(1.35, 4.5, lab_in, fontsize=7.0, color=col, va='top', ha='left')
        ax.text(9.9, 4.55, 'out', fontsize=6.8, color=col, ha='right', va='top')
        ax.text(1.35, 3.6, 'cold plate:\nQ2 model', fontsize=7.0, color=col, ha='left', va='center')
        src = 'He cryoplant and circulator' if route == 'he' else 'LN$_2$ dewar or pressurised loop'
        ax.text(5, 1.15, 'duty $\\dot Q_1$ removed by the coolant:\n' + src, ha='center', va='center', fontsize=8)

for ax, (t1, t2), Ts1, route in zip(axes, titles, ('50 K', '50 K', '77 K'), ('ptr', 'he', 'n2')):
    stage_stack(ax, Ts1, route)
    ax.set_title(f'{t1}\n{t2}', fontsize=10.2, pad=4)

fig.savefig(OUT, dpi=300, bbox_inches='tight'); fig.savefig(OUT.replace('.png', '.pdf'), bbox_inches='tight'); print('wrote', OUT)
