#!/usr/bin/env python3
"""Illustrative (non-data) figures for paper v2:
  figA_cryostat_routes.png   -- cryostat cross-section: He-gas route (left) vs LN2 route (right),
                                 with the full stack incl. dilution unit (greyed, not modelled)
  figB_coldplate_geometry.png -- channelled cold plate: 5 square ducts, dimensions, BCs, sampling lines
  figC_harness_lumping.png   -- 65 coaxial lines -> 4 lumped cylinders; UT-085 cross-section; k_eff(T)
"""
import os, math, numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Wedge, PathPatch
from matplotlib.path import Path
FIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')
plt.rcParams.update({'font.size': 8, 'font.family': 'DejaVu Sans'})
C_WARM, C_S1, C_S2, C_GREY = '#C8553D', '#588B8B', '#2F4858', '#9a9a9a'
C_HE, C_N2, C_MLI = '#B85042', '#50708E', '#e0b84a'

def arrow(ax, p, q, color, lw=1.3, ls='-', ms=9):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle='-|>', mutation_scale=ms, color=color, lw=lw, ls=ls))

# ---------------------------------------------------------------- Fig A
def cryostat(ax, route):
    ax.set_xlim(-2.6, 11.8); ax.set_ylim(-0.8, 12.6); ax.axis('off'); ax.set_aspect('equal')
    col = C_HE if route == 'he' else C_N2
    # OVC (300 K) -- outer can
    ax.add_patch(Rectangle((0.3, 0.3), 9.4, 11.2, fc='none', ec=C_WARM, lw=3))
    ax.text(5.0, 11.75, 'outer vacuum can, 300 K', ha='center', color=C_WARM, fontsize=8)
    # vacuum label
    ax.text(0.5, 10.9, 'vacuum', fontsize=7, color=C_GREY, style='italic')
    # warm plate (300K) top
    ax.add_patch(Rectangle((0.3, 10.3), 9.4, 0.35, fc=C_WARM, ec='none')); ax.text(5.0, 10.47, '300 K plate', ha='center', va='center', color='w', fontsize=7)
    # first shield: hangs from first-stage plate; MLI option drawn as dashed golden line
    T1 = '50 K' if route == 'he' else '77 K'
    ax.add_patch(Rectangle((1.3, 7.3), 7.4, 0.35, fc=C_S1, ec='none'))
    ax.text(5.0, 7.47, f'first-stage plate  {T1}', ha='center', va='center', color='w', fontsize=7.5)
    ax.plot([1.3, 1.3, 8.7, 8.7], [7.3, 1.0, 1.0, 7.3], color=C_S1, lw=2.2)       # shield walls + bottom
    ax.plot([1.15, 1.15, 8.85, 8.85], [7.2, 0.85, 0.85, 7.2], color=C_MLI, lw=1.0, ls='--')
    ax.text(8.95, 2.6, 'MLI\n(variant)', fontsize=6.5, color='#8a6d1a', va='center')
    ax.text(1.45, 6.2, f'first shield {T1}', fontsize=7, color=C_S1)
    # 4 K plate + shield
    ax.add_patch(Rectangle((2.2, 4.6), 5.6, 0.32, fc=C_S2, ec='none')); ax.text(5.0, 4.76, '4 K plate', ha='center', va='center', color='w', fontsize=7.5)
    ax.plot([2.2, 2.2, 7.8, 7.8], [4.6, 1.5, 1.5, 4.6], color=C_S2, lw=1.8)
    # below 4 K: still, cold plate, mixing chamber (greyed = not modelled)
    for y, lab in ((3.7, 'still  ~0.8 K'), (2.9, 'cold plate  ~0.1 K'), (2.1, 'mixing chamber  ~0.01 K')):
        ax.add_patch(Rectangle((3.0, y), 4.0, 0.22, fc='#d8d8d8', ec='none')); ax.text(5.0, y + 0.11, lab, ha='center', va='center', fontsize=6.5, color='#555')
    ax.text(5.0, 1.75, 'dilution unit / payload: not modelled', ha='center', fontsize=6.5, color='#777', style='italic')
    # harness lines from 300 K plate to 4 K plate (and greyed below)
    for x in (3.4, 4.2, 5.8, 6.6):
        ax.plot([x, x], [10.3, 4.92], color='#333', lw=1.0); ax.plot([x, x], [4.6, 2.32], color='#bbb', lw=0.8)
        ax.plot([x - 0.12, x + 0.12], [7.47, 7.47], color='k', lw=2.0)   # heat sink at first stage
    ax.text(7.0, 9.3, 'coaxial\nharness\n(65 lines)', fontsize=6.5, va='center')
    ax.text(7.0, 7.95, 'heat sink', fontsize=6, va='center')
    # radiation arrows 300 K -> shield
    for x in (2.0, 2.6):
        arrow(ax, (x, 10.25), (x, 7.7), C_WARM, lw=0.9, ls=(0, (2, 1.5)), ms=7)
    ax.text(1.5, 9.0, 'radiation\n$\\dot Q_{r,1}$', fontsize=6.5, color=C_WARM, ha='center')
    ax.text(4.55, 8.9, '$\\dot Q_{c,1}$', fontsize=6.5)
    arrow(ax, (2.9, 7.25), (2.9, 4.97), C_S1, lw=0.9, ls=(0, (2, 1.5)), ms=7)
    ax.text(2.6, 6.1, '$\\dot Q_{r,2}$', fontsize=6.5, color=C_S1, ha='right'); ax.text(4.55, 6.1, '$\\dot Q_{c,2}$', fontsize=6.5)
    # coolant loop through the first-stage plate
    ax.add_patch(Rectangle((1.3, 7.02), 7.4, 0.26, fc='#e9eef0', ec=col, lw=0.7))
    for x in (2.2, 3.0, 4.9, 5.05, 6.2, 7.4, 8.1):
        ax.add_patch(Rectangle((x - 0.11, 7.06), 0.22, 0.18, fc='w', ec=col, lw=0.8))
    ax.text(5.0, 6.72, 'channelled cold plate (Q2 model)', fontsize=6, color=col, ha='center', va='top')
    # pipes out of the cryostat to the plant (left side)
    ax.plot([1.3, -0.9, -0.9], [7.2, 7.2, 9.6], color=col, lw=1.6)
    ax.plot([1.3, -1.6, -1.6], [7.08, 7.08, 9.6], color=col, lw=1.6)
    
    if route == 'he':
        ax.add_patch(FancyBboxPatch((-2.45, 9.6), 2.35, 1.7, boxstyle='round,pad=0.02,rounding_size=0.1', fc='#f6e3df', ec=col, lw=1))
        ax.text(-1.28, 10.45, 'He cryoplant\n+ circulator\n45 K, 1--18 bar', ha='center', va='center', fontsize=6.3, color=col)
        ttl = '(a) Helium-gas route: shield and first-stage plate at 50 K (nominal)'
        ax.text(-0.75, 8.3, 'in', fontsize=6.5, color=col); ax.text(-2.05, 8.3, 'out', fontsize=6.5, color=col)
    else:
        ax.add_patch(FancyBboxPatch((-2.45, 9.6), 2.35, 1.7, boxstyle='round,pad=0.02,rounding_size=0.1', fc='#dfe6ec', ec=col, lw=1))
        ax.text(-1.28, 10.45, 'LN$_2$ dewar\n+ pump\n77 K, 3 bar', ha='center', va='center', fontsize=6.3, color=col)
        ttl = '(b) Liquid-nitrogen route: shield and first-stage plate at 77 K'
        ax.text(-0.75, 8.3, 'in', fontsize=6.5, color=col); ax.text(-2.05, 8.3, 'out', fontsize=6.5, color=col)
    # 4 K cryocooler stub (both routes)
    ax.add_patch(Rectangle((9.75, 4.4), 1.4, 0.7, fc='#ddd', ec='k', lw=0.6)); ax.plot([7.8, 9.75], [4.76, 4.76], color='k', lw=1.2)
    ax.text(10.45, 4.75, '4 K\ncryocooler', ha='center', va='center', fontsize=6)
    if route == 'he':
        ax.text(10.45, 3.6, '(or PTR\n2nd stage)', ha='center', fontsize=5.5, color='#666')
    ax.set_title(ttl, fontsize=8.5, loc='left')

fig, axes = plt.subplots(1, 2, figsize=(10.5, 6.2), gridspec_kw={'wspace': 0.02})
cryostat(axes[0], 'he'); cryostat(axes[1], 'n2')
fig.text(0.5, 0.02, 'Modelled: the dashed/boxed region from the 300 K plate to the 4 K plate (enclosure CHT), and the channelled first-stage plate (cold-plate HX). '
         'Greyed stages below 4 K are shown for context only.', ha='center', fontsize=7.2, color='#444')
fig.savefig(os.path.join(FIG, 'figA_cryostat_routes.png'), dpi=300, bbox_inches='tight'); plt.close(fig)

# ---------------------------------------------------------------- Fig B: cold-plate geometry
fig = plt.figure(figsize=(10.0, 4.4))
ax = fig.add_axes([0.02, 0.05, 0.60, 0.9]); ax.set_xlim(-1.5, 13.5); ax.set_ylim(-1.5, 6.5); ax.axis('off'); ax.set_aspect('equal')
# oblique projection of 5 ducts: length L along x (foreshortened), width along y
L, W, H, dx, dy = 9.0, 0.9, 0.9, 1.4, 0.7   # dx,dy = oblique offsets for depth
def duct(x0, y0, col):
    # front face (inlet), top, side
    ax.add_patch(Polygon([(x0, y0), (x0 + L, y0), (x0 + L, y0 + H), (x0, y0 + H)], fc='#eef3f6', ec='k', lw=0.8))
    ax.add_patch(Polygon([(x0, y0 + H), (x0 + L, y0 + H), (x0 + L + dx, y0 + H + dy), (x0 + dx, y0 + H + dy)], fc='#f7d6cf', ec='k', lw=0.8))
    ax.add_patch(Polygon([(x0 + L, y0), (x0 + L + dx, y0 + dy), (x0 + L + dx, y0 + H + dy), (x0 + L, y0 + H)], fc='#dfe6ec', ec='k', lw=0.8))
for i in range(5):
    duct(0.0, i * 1.15 - 0.0 + 0.0, None) if False else None
# draw ducts stacked in depth (y) via oblique offset so they look side by side
for i in range(5):
    x0 = 0.0 + i * 0.0; y0 = 0.0
    off = i * 0.62
    xo, yo = x0 + off * dx / dy * 0.0, y0
    # shift each duct back in depth
    X = 0.0 + i * 0.55; Y = 0.0 + i * 0.95
    ax.add_patch(Polygon([(X, Y), (X + L, Y), (X + L, Y + H), (X, Y + H)], fc='#eef3f6', ec='k', lw=0.8, zorder=5 - i))
    ax.add_patch(Polygon([(X, Y + H), (X + L, Y + H), (X + L + dx * 0.4, Y + H + dy * 0.55), (X + dx * 0.4, Y + H + dy * 0.55)], fc='#f4c9c0' if True else None, ec='k', lw=0.8, zorder=5 - i))
    ax.add_patch(Polygon([(X + L, Y), (X + L + dx * 0.4, Y + dy * 0.55), (X + L + dx * 0.4, Y + H + dy * 0.55), (X + L, Y + H)], fc='#dfe6ec', ec='k', lw=0.8, zorder=5 - i))
# flow arrows
for i in range(5):
    X = 0.0 + i * 0.55; Y = 0.0 + i * 0.95
    arrow(ax, (X - 1.0, Y + H / 2), (X - 0.1, Y + H / 2), '#333', lw=1.0, ms=8)
ax.text(-1.4, -0.9, 'inlet: $T_{in}$, $\\dot m$ (He: mass-flow BC; LN$_2$: velocity BC)', fontsize=7)
ax.text(L + 0.6, -0.9, 'outlet: fixed $p$', fontsize=7)
ax.text(4.5, 5.9, 'heated wall (top of every duct): uniform $q_w = \\dot Q/A_{heated}$ = 627 W m$^{-2}$', fontsize=7.5, color='#8a2f22')
ax.text(10.9, 2.2, 'other walls:\nadiabatic,\nno slip', fontsize=7)
# dimension lines
ax.plot([0, L], [-0.35, -0.35], color='k', lw=0.7); ax.text(L / 2, -0.62, '$L$ = 300 mm', ha='center', fontsize=7)
ax.plot([-0.25, -0.25], [0, H], color='k', lw=0.7); ax.text(-0.35, H + 0.05, '10 mm', ha='right', va='bottom', fontsize=7)
ax.plot([L + 0.15, L + 0.15 + dx * 0.4], [H + 0.15, H + 0.15 + dy * 0.55], color='k', lw=0.7); ax.text(L + 0.8, H + 0.55, '10 mm', fontsize=7)
ax.text(5.5, -1.35, 'five parallel square ducts, $D_h$ = 10 mm, pitch 18 mm; total heated area 0.015 m$^2$, flow area 5$\\times$10$^{-4}$ m$^2$', ha='center', fontsize=7.2)
ax.set_title('(a) cold-plate heat-exchanger domain', fontsize=8.5, loc='left')
# (b) cross-section with graded mesh + sampling lines
ax2 = fig.add_axes([0.66, 0.12, 0.32, 0.78]); ax2.set_aspect('equal'); ax2.set_xlim(-0.15, 1.15); ax2.set_ylim(-0.25, 1.15); ax2.axis('off')
n = 18; r = 6 ** (1 / 8)
def graded(n):
    half = n // 2; s = np.array([r ** k for k in range(half)]); s = s / s.sum() * 0.5
    edges = np.concatenate([[0], np.cumsum(s[::-1])]); return np.concatenate([edges, 1 - edges[-2::-1]])
e = graded(n)
for v in e: ax2.plot([v, v], [0, 1], color='#999', lw=0.4); ax2.plot([0, 1], [v, v], color='#999', lw=0.4)
ax2.add_patch(Rectangle((0, 0), 1, 1, fc='none', ec='k', lw=1.2))
ax2.plot([0, 1], [1.0, 1.0], color='#8a2f22', lw=3); ax2.text(0.5, 1.06, 'heated wall, $q_w$', ha='center', color='#8a2f22', fontsize=7)
ax2.plot([0.5, 0.5], [0, 1], color=C_N2, lw=1.2, ls='--'); ax2.text(0.52, 0.5, 'profile line\n$T(y)$ at $x/L$=0.5', fontsize=6.5, color=C_N2)
ax2.plot(0.5, 0.985, 'o', color=C_HE, ms=4); ax2.text(0.55, 0.9, 'centreline $T_w(x)$', fontsize=6.5, color=C_HE)
ax2.text(0.5, -0.12, '18$\\times$18 cells per duct, two-sided grading ratio 6\nfirst cell 0.19 mm; 180 cells along $L$; 2.9$\\times$10$^5$ cells', ha='center', fontsize=6.5)
ax2.set_title('(b) duct cross-section: mesh and sampling lines', fontsize=8.5, loc='left')
fig.savefig(os.path.join(FIG, 'figB_coldplate_geometry.png'), dpi=300, bbox_inches='tight'); plt.close(fig)

# ---------------------------------------------------------------- Fig C: harness lumping
fig = plt.figure(figsize=(10.0, 3.9))
# (a) plan view of the 65 physical lines grouped in 4 families -> 4 cylinders in the model
ax = fig.add_axes([0.02, 0.08, 0.30, 0.84]); ax.set_aspect('equal'); ax.axis('off'); ax.set_xlim(-0.25, 0.25); ax.set_ylim(-0.25, 0.25)
ax.add_patch(Circle((0, 0), 0.24, fc='none', ec=C_WARM, lw=1.5)); ax.text(0.2, 0.2, 'OVC', color=C_WARM, fontsize=6.5, ha='left', va='bottom')
ax.add_patch(Circle((0, 0), 0.20, fc='none', ec=C_S1, lw=1.2)); ax.text(0, 0.16, 'shield', color=C_S1, fontsize=6.5, ha='center')
fam = [((0.139, 0.056), 25, 'drive', C_HE), ((-0.056, 0.139), 25, 'flux', '#7a4f9d'), ((-0.139, -0.056), 10, 'readout', C_N2), ((0.056, -0.139), 5, 'pump', '#3c8c5a')]
rng = np.random.default_rng(3)
for (cx, cy), n_, lab, c in fam:
    ax.add_patch(Circle((cx, cy), 0.01, fc='none', ec='k', lw=1.0, ls='--'))
    pts = rng.normal(size=(n_, 2)); pts = pts / np.linalg.norm(pts, axis=1).max() * 0.009
    ax.scatter(cx + pts[:, 0], cy + pts[:, 1], s=3, color=c, zorder=5)
    lx, ly = {'drive': (0.105, 0.085), 'flux': (-0.09, 0.105), 'readout': (-0.105, -0.09), 'pump': (0.085, -0.108)}[lab]
    ax.text(lx, ly, f'{lab}\n{n_} lines', fontsize=6.3, ha='center', va='center', color=c)
ax.set_title('(a) 65 coaxial lines in four functional families', fontsize=8, loc='left')
ax.text(0, -0.27, 'each family $\\to$ one 20 mm cylinder at $r$ = 0.15 m (plan view, to scale)', fontsize=6.5, ha='center')
# (b) UT-085 cross-section
ax = fig.add_axes([0.35, 0.08, 0.28, 0.84]); ax.set_aspect('equal'); ax.axis('off'); ax.set_xlim(-1.35, 1.35); ax.set_ylim(-1.35, 1.35)
R_out, R_pt, R_c = 1.08, 0.84, 0.255   # UT-085: OD 2.2 mm; dielectric OD ~1.68 mm; centre 0.51 mm (relative units)
ax.add_patch(Circle((0, 0), R_out, fc='#b8bec4', ec='k', lw=0.8)); ax.add_patch(Circle((0, 0), R_pt, fc='#f2efe6', ec='k', lw=0.6)); ax.add_patch(Circle((0, 0), R_c, fc='#b8bec4', ec='k', lw=0.6))
ax.annotate('outer conductor\n304 stainless, 1.585 mm$^2$', (R_out * 0.72, R_out * 0.72), (0.55, 1.22), fontsize=6.3, arrowprops=dict(arrowstyle='-', lw=0.6))
ax.annotate('dielectric\nPTFE, 2.001 mm$^2$', (0.55, -0.35), (0.75, -1.05), fontsize=6.3, arrowprops=dict(arrowstyle='-', lw=0.6))
ax.annotate('centre conductor\n304 stainless, 0.205 mm$^2$', (0.0, 0.2), (-1.3, 0.95), fontsize=6.3, arrowprops=dict(arrowstyle='-', lw=0.6))
ax.text(0, -1.3, 'UT-085-SS-SS, OD 2.2 mm', ha='center', fontsize=6.8)
ax.set_title('(b) cable cross-section (components $i$)', fontsize=8, loc='left')
# (c) k_eff(T): component k(T) and the lumped effective conductivity for the drive bundle
ax = fig.add_axes([0.70, 0.16, 0.28, 0.72])
MAT = {'304 SS': [-1.4087, 1.3982, 0.2543, -0.6260, 0.2334, 0.4256, -0.4658, 0.1650, -0.0199],
       'PTFE': [2.7380, -30.677, 89.430, -136.99, 124.69, -69.556, 23.320, -4.3135, 0.33829]}
def kmat(m, T): x = np.log10(T); return 10 ** sum(c * x ** n for n, c in enumerate(MAT[m]))
T = np.linspace(4, 300, 300)
ax.plot(T, kmat('304 SS', T), color='#555', lw=1.2, label='304 SS')
ax.plot(T, kmat('PTFE', T), color='#c9a227', lw=1.2, label='PTFE')
A = {'304 SS': 1.585e-6 + 0.205e-6, 'PTFE': 2.001e-6}; nk = 25; Amodel = math.pi * 0.01 ** 2
keff = nk / Amodel * (A['304 SS'] * kmat('304 SS', T) + A['PTFE'] * kmat('PTFE', T))
ax.plot(T, keff, color=C_HE, lw=1.8, label='$\\kappa_{eff}$, drive bundle (25 lines)')
ax.set_xscale('log'); ax.set_yscale('log'); ax.set_xlabel('$T$ [K]'); ax.set_ylabel('$k$ [W m$^{-1}$ K$^{-1}$]'); ax.grid(alpha=0.3); ax.legend(fontsize=6.3, loc='lower right')
ax.set_title('(c) $\\kappa_{eff}(T)=\\frac{n_k}{A_{model}}\\sum_i A_i k_i(T)$', fontsize=8, loc='left')
fig.savefig(os.path.join(FIG, 'figC_harness_lumping.png'), dpi=300, bbox_inches='tight'); plt.close(fig)
print('wrote A, B, C')
