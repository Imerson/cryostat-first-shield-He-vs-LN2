#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
materials.py -- cryogenic thermal-conductivity integrals for the conduction gate.

The analytical conduction load through a constant-cross-section bar with no
intermediate heat sink is

    Q = (A / L) * integral_{T_cold}^{T_warm} k(T) dT                       (W)

so the only material datum the gate needs is the *conductivity integral*
theta(T) = integral_{Tref}^{T} k(T') dT'  [W/m]; then
    Q = (A/L) * (theta(T_warm) - theta(T_cold)).

Two ways to supply k(T) are provided:

1. TABULATED  (recommended, transparent): give a list of (T, k) points from
   NIST cryogenics (cryogenics.nist.gov) or your conductor datasheet. The
   integral is done by the trapezoid rule on a log-spaced refinement.

2. NIST_LOGPOLY: NIST 4-300 K fits  log10(k) = a + b*log10(T) + c*log10(T)^2
   + ... + i*log10(T)^8 ; paste the published a..i coefficients.

IMPORTANT FOR PUBLICATION
-------------------------
The few built-in tables below are ROUGH literature values flagged VERIFY=True.
They exist only so the suite runs end-to-end out of the box. Before citing any
conduction number, replace them with values you have traced to NIST or the
manufacturer datasheet for YOUR conductor, and set VERIFY=False. The gate report
prints a WARNING for every material still flagged VERIFY.
"""

import math


# --------------------------------------------------------------------------- #
# representative tables  (T [K], k [W/m/K])  -- VERIFY before publication
# --------------------------------------------------------------------------- #
# Sources to replace these with: NIST Cryogenic Material Properties database;
# Ekin, "Experimental Techniques for Low-Temperature Measurements" (2006),
# conductivity-integral appendix.
_TABLES = {
    # 304 stainless steel -- common semi-rigid coax outer conductor / supports
    "SS304": dict(VERIFY=True, pts=[
        (4, 0.28), (10, 0.77), (20, 2.0), (40, 4.5), (77, 8.0),
        (100, 9.2), (150, 11.8), (200, 13.6), (300, 15.0)]),
    # Beryllium copper -- common coax inner/outer conductor
    "BeCu": dict(VERIFY=True, pts=[
        (4, 1.6), (10, 4.5), (20, 11), (40, 26), (77, 50),
        (100, 60), (150, 80), (200, 95), (300, 110)]),
    # Phosphor bronze -- low-conduction signal wiring
    "PhosphorBronze": dict(VERIFY=True, pts=[
        (4, 1.6), (10, 4.6), (20, 10), (40, 20), (77, 33),
        (100, 39), (150, 49), (200, 60), (300, 75)]),
    # Cupronickel (CuNi 70/30) -- common coax outer/inner for thermal isolation
    "CuNi": dict(VERIFY=True, pts=[
        (4, 0.8), (10, 2.3), (20, 5.5), (40, 11), (77, 18),
        (100, 21), (150, 26), (200, 30), (300, 37)]),
    # NbTi -- superconducting coax center conductor (very low k below Tc)
    "NbTi": dict(VERIFY=True, pts=[
        (4, 0.10), (10, 0.30), (20, 0.75), (40, 1.6), (77, 3.0),
        (100, 3.8), (150, 5.4), (200, 7.0), (300, 9.5)]),
    # PTFE dielectric (semi-rigid coax insulator) -- small area, low k
    "PTFE": dict(VERIFY=True, pts=[
        (4, 0.045), (10, 0.085), (20, 0.13), (40, 0.18), (77, 0.23),
        (100, 0.25), (150, 0.27), (200, 0.27), (300, 0.25)]),
}


def _interp_k(pts, T):
    if T <= pts[0][0]:
        return pts[0][1]
    if T >= pts[-1][0]:
        return pts[-1][1]
    for i in range(1, len(pts)):
        if T <= pts[i][0]:
            (t0, k0), (t1, k1) = pts[i - 1], pts[i]
            f = (T - t0) / (t1 - t0)
            return k0 + f * (k1 - k0)
    return pts[-1][1]


def conductivity_integral(spec, T_cold, T_warm, n=400):
    """integral_{T_cold}^{T_warm} k(T) dT  [W/m].
    `spec` is one of:
       - str name into the built-in _TABLES
       - dict(pts=[(T,k),...])              custom table
       - dict(nist=[a,b,c,...])             NIST log10 polynomial coefficients
    Returns (value, verify_flag, source_note)."""
    verify = False
    note = ""
    if isinstance(spec, str):
        if spec not in _TABLES:
            raise KeyError("unknown material '%s'; known: %s"
                           % (spec, ", ".join(sorted(_TABLES))))
        tbl = _TABLES[spec]
        pts = tbl["pts"]; verify = tbl["VERIFY"]; note = "built-in table"
        kfun = lambda T: _interp_k(pts, T)
    elif isinstance(spec, dict) and "pts" in spec:
        pts = sorted(spec["pts"]); verify = spec.get("VERIFY", False)
        note = spec.get("source", "user table")
        kfun = lambda T: _interp_k(pts, T)
    elif isinstance(spec, dict) and "nist" in spec:
        c = spec["nist"]; verify = spec.get("VERIFY", False)
        note = spec.get("source", "NIST log-poly")

        def kfun(T):
            x = math.log10(T)
            return 10.0 ** sum(c[i] * x ** i for i in range(len(c)))
    else:
        raise ValueError("bad material spec: %r" % (spec,))

    lo, hi = min(T_cold, T_warm), max(T_cold, T_warm)
    h = (hi - lo) / n
    s = 0.5 * (kfun(lo) + kfun(hi))
    for i in range(1, n):
        s += kfun(lo + i * h)
    return s * h, verify, note


def conduction_load(spec, area, length, T_cold, T_warm):
    """Analytical axial conduction Q = (A/L) * integral k dT  [W].
    Returns (Q, verify_flag, note)."""
    integ, verify, note = conductivity_integral(spec, T_cold, T_warm)
    return (area / length) * integ, verify, note


def known_materials():
    return sorted(_TABLES)
