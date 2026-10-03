#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gates.py -- the gate definitions.

Each gate is a function gate(ctx, cfg) -> Result. `ctx` is the parsed-case
container built by runner.CaseData; `cfg` is the case config dict. Gates never
raise on missing data: they return status SKIP with a reason instead, so one
absent artifact cannot fail the whole suite.

Status vocabulary
    PASS  criterion met
    FAIL  criterion violated -- case must not be used as-is
    WARN  advisory / physics-consistency flag (does not block, but review)
    SKIP  required input not present

A case "passes the suite" iff it has zero FAILs (WARNs allowed, reviewed).
"""

from . import analytical as an
from . import materials as mat

GATE_REGISTRY = []          # filled by @gate decorator, preserves order


class Result:
    __slots__ = ("id", "tier", "name", "status", "measured",
                 "criterion", "basis", "detail")

    def __init__(self, id, tier, name, status, measured="", criterion="",
                 basis="", detail=""):
        self.id = id
        self.tier = tier
        self.name = name
        self.status = status
        self.measured = measured
        self.criterion = criterion
        self.basis = basis
        self.detail = detail

    def as_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}


def gate(id, tier, name):
    def deco(fn):
        fn._gate = dict(id=id, tier=tier, name=name)
        GATE_REGISTRY.append(fn)
        return fn
    return deco


def _R(fn, status, **kw):
    g = fn._gate
    return Result(g["id"], g["tier"], g["name"], status, **kw)


def _num(x, p=4):
    try:
        return ("%." + str(p) + "g") % x
    except (TypeError, ValueError):
        return str(x)


# ========================================================================== #
# TIER 0 -- numerical health
# ========================================================================== #
@gate("G0.1", 0, "Residual convergence")
def g_residuals(ctx, cfg):
    res = ctx.residuals
    if not res:
        return _R(g_residuals, "SKIP", detail="no solver log / residuals parsed")
    tol = cfg.get("thresholds", {}).get("residual_max", 1e-5)
    fields = cfg.get("residual_fields", ["Ux", "Uy", "Uz", "h", "p_rgh", "G"])
    bad = {f: res[f] for f in fields if f in res and res[f] > tol}
    present = {f: res[f] for f in fields if f in res}
    if not present:
        return _R(g_residuals, "SKIP", detail="none of the watched fields in log")
    meas = ", ".join("%s=%s" % (f, _num(v, 3)) for f, v in present.items())
    if bad:
        return _R(g_residuals, "FAIL", measured=meas,
                  criterion="all < %g" % tol,
                  detail="above tol: " + ", ".join(bad))
    return _R(g_residuals, "PASS", measured=meas, criterion="all < %g" % tol,
              basis="SIMPLE outer initial residuals at final iteration")


@gate("G0.2", 0, "Field bounds (T finite, in band, rho>0)")
def g_field_bounds(ctx, cfg):
    tcold = cfg["temperatures"]["T_cold"]
    twarm = cfg["temperatures"]["T_warm"]
    margin = cfg.get("thresholds", {}).get("T_margin_K", 1.0)
    lo, hi = tcold - margin, twarm + margin
    problems = []
    for region, (tmin, tmax) in ctx.T_bounds.items():
        if tmin != tmin or tmax != tmax:               # NaN
            problems.append("%s NaN" % region)
        elif tmin < lo - 1e-9 or tmax > hi + 1e-9:
            problems.append("%s [%s,%s]" % (region, _num(tmin), _num(tmax)))
    if ctx.rho is not None and ctx.rho <= 0:
        problems.append("rho<=0 (%s)" % _num(ctx.rho))
    if not ctx.T_bounds:
        return _R(g_field_bounds, "SKIP", detail="no T fields read")
    meas = "; ".join("%s:[%s,%s]" % (r, _num(b[0]), _num(b[1]))
                     for r, b in ctx.T_bounds.items())
    if problems:
        return _R(g_field_bounds, "FAIL", measured=meas,
                  criterion="T in [%g,%g] K, finite" % (lo, hi),
                  detail="; ".join(problems))
    return _R(g_field_bounds, "PASS", measured=meas,
              criterion="T in [%g,%g] K, finite, rho>0" % (lo, hi))


@gate("G0.3", 0, "Steady state (load drift between last two writes)")
def g_steady_state(ctx, cfg):
    if not ctx.prev_loads:
        return _R(g_steady_state, "SKIP",
                  detail="need two time dirs with fields to compare")
    tol = cfg.get("thresholds", {}).get("steady_rel", 0.01)
    worst = 0.0; who = ""
    for p, q_now in ctx.patch_total.items():
        q_old = ctx.prev_loads.get(p)
        if q_old is None or abs(q_now) < 1e-12:
            continue
        rel = abs(q_now - q_old) / max(abs(q_now), 1e-12)
        if rel > worst:
            worst, who = rel, p
    if worst > tol:
        return _R(g_steady_state, "FAIL",
                  measured="max drift %.3g%% (%s)" % (100 * worst, who),
                  criterion="< %g%%" % (100 * tol),
                  detail="loads still changing between last two time dirs")
    return _R(g_steady_state, "PASS",
              measured="max drift %.3g%%" % (100 * worst),
              criterion="< %g%%" % (100 * tol),
              basis="patch load change, last two time directories")


# ========================================================================== #
# TIER 1 -- conservation
# ========================================================================== #
@gate("G1.1", 1, "Global energy balance (sum of all wall loads = 0)")
def g_global_balance(ctx, cfg):
    if not ctx.patch_total:
        return _R(g_global_balance, "SKIP", detail="no wall loads")
    net = sum(ctx.patch_total.values())
    scale = max(abs(v) for v in ctx.patch_total.values())
    rel = abs(net) / scale if scale else 0.0
    tol = cfg.get("thresholds", {}).get("energy_balance_rel", 0.01)
    abstol = cfg.get("thresholds", {}).get("energy_balance_abs_W", None)
    ok = rel <= tol if abstol is None else abs(net) <= abstol
    crit = ("|net| < %g%% of max patch" % (100 * tol) if abstol is None
            else "|net| < %g W" % abstol)
    st = "PASS" if ok else "FAIL"
    return _R(g_global_balance, st,
              measured="net=%s W (%.3g%% of max)" % (_num(net), 100 * rel),
              criterion=crit,
              basis="sum_patches (Q_diffusive + Q_radiative); steady fluid has no source",
              detail="" if ok else "non-zero net => unaccounted source/sink")


@gate("G1.2", 1, "Radiation closure (enclosure radiative net = 0)")
def g_radiation_closure(ctx, cfg):
    rad = {p: ctx.patch_rad[p] for p in ctx.patch_rad}
    if not rad:
        return _R(g_radiation_closure, "SKIP", detail="no qr field")
    net = sum(rad.values())
    scale = max(abs(v) for v in rad.values()) or 1.0
    rel = abs(net) / scale
    tol = cfg.get("thresholds", {}).get("rad_closure_rel", 0.02)
    st = "PASS" if rel <= tol else "FAIL"
    detail = ""
    if st == "FAIL":
        # name the biggest one-sided contributor -- this is how the G=0 coax
        # sink shows up (a patch absorbing with no matching emitter).
        worst = max(rad.items(), key=lambda kv: abs(kv[1]))
        detail = ("net radiative imbalance => spurious sink/source; "
                  "largest one-sided patch: %s = %s W" % (worst[0], _num(worst[1])))
    return _R(g_radiation_closure, st,
              measured="net Q_rad=%s W (%.3g%% of max)" % (_num(net), 100 * rel),
              criterion="|net| < %g%%" % (100 * tol),
              basis="grey-diffuse enclosure: radiative exchange is internal, must sum ~0",
              detail=detail)


@gate("G1.3", 1, "Interface flux continuity (fluid vs solid at coax)")
def g_interface_continuity(ctx, cfg):
    pairs = ctx.interface_pairs            # [(fluid_patch, Q_fluid, Q_solid_or_None)]
    if not pairs:
        return _R(g_interface_continuity, "SKIP",
                  detail="solid-side coax patches not read")
    tol = cfg.get("thresholds", {}).get("interface_rel", 0.02)
    rows = []; worst = 0.0; fail = False
    for name, qf, qs in pairs:
        if qs is None:
            continue
        denom = max(abs(qf), abs(qs), 1e-12)
        rel = abs(qf + qs) / denom        # fluxes are equal & opposite -> sum ~0
        worst = max(worst, rel)
        rows.append("%s:%.2g%%" % (name, 100 * rel))
        if rel > tol:
            fail = True
    if not rows:
        return _R(g_interface_continuity, "SKIP", detail="no matched solid side")
    return _R(g_interface_continuity, "FAIL" if fail else "PASS",
              measured="max %.3g%% (%s)" % (100 * worst, ", ".join(rows)),
              criterion="|q_fluid+q_solid|/q < %g%%" % (100 * tol),
              basis="conservative CHT coupling: equal & opposite interface flux")


# ========================================================================== #
# TIER 2 -- radiation model validity
# ========================================================================== #
@gate("G2.1", 2, "Emissivity assignment audit")
def g_emissivity_audit(ctx, cfg):
    radiating = ctx.radiating_patches      # patches expected to radiate
    eps = ctx.emissivity
    missing = [p for p in radiating if p not in eps or eps[p] is None]
    bad = [p for p in radiating if p in eps and eps[p] is not None
           and not (0 < eps[p] <= 1)]
    if not radiating:
        return _R(g_emissivity_audit, "SKIP", detail="no radiating patch list")
    if missing or bad:
        return _R(g_emissivity_audit, "FAIL",
                  measured="assigned %d/%d" % (len(radiating) - len(missing),
                                               len(radiating)),
                  criterion="every radiating patch has 0<eps<=1",
                  detail="missing: %s; bad: %s" % (missing or "-", bad or "-"))
    return _R(g_emissivity_audit, "PASS",
              measured="all %d radiating patches assigned" % len(radiating),
              criterion="every radiating patch has 0<eps<=1",
              basis="catches unassigned-emissivity / G=0 absorber bug")


@gate("G2.2", 2, "View-factor row sums")
def g_viewfactor_rowsum(ctx, cfg):
    rs = ctx.viewfactor_rowsums
    if not rs:
        return _R(g_viewfactor_rowsum, "SKIP",
                  detail="F matrix / viewFactorField not parsed")
    tol = cfg.get("thresholds", {}).get("viewfactor_rowsum_tol", 1e-3)
    worst = max(abs(s - 1.0) for s in rs)
    st = "PASS" if worst <= tol else "FAIL"
    return _R(g_viewfactor_rowsum, st,
              measured="max|rowsum-1|=%s over %d faces" % (_num(worst), len(rs)),
              criterion="< %g" % tol,
              basis="closed enclosure: sum_j F_ij = 1")


@gate("G2.3", 2, "Analytical radiation cross-check (warm->shield)")
def g_analytical_radiation(ctx, cfg):
    rc = cfg.get("radiation_check")
    if not rc:
        return _R(g_analytical_radiation, "SKIP", detail="no radiation_check in cfg")
    patch = rc["cold_patch"]
    if patch not in ctx.patch_rad:
        return _R(g_analytical_radiation, "SKIP",
                  detail="cold patch '%s' has no qr" % patch)
    geom = getattr(ctx, "geom", {})
    # areas: explicit cfg value, else measured patch area from the mesh
    A_hot = rc.get("A_hot") or (geom.get(rc.get("hot_patch", ""), {}) or {}).get("area")
    A_cold = rc.get("A_cold") or (geom.get(patch, {}) or {}).get("area")
    if not A_hot or not A_cold:
        return _R(g_analytical_radiation, "SKIP",
                  detail="need A_hot/A_cold (explicit or via hot_patch/cold_patch geometry)")
    q_cfd = abs(ctx.patch_rad[patch])
    q_an = abs(an.two_surface_radiation(
        rc["eps_hot"], A_hot, rc["T_hot"],
        rc["eps_cold"], A_cold, rc["T_cold"], rc.get("F", 1.0)))
    tol = cfg.get("thresholds", {}).get("radiation_rel", 0.30)
    rel = abs(q_cfd - q_an) / max(q_an, 1e-15)
    st = "PASS" if rel <= tol else "WARN"
    return _R(g_analytical_radiation, st,
              measured="CFD=%s W vs analytic=%s W (%.1f%%)"
                       % (_num(q_cfd), _num(q_an), 100 * rel),
              criterion="within %g%%" % (100 * tol),
              basis="grey two-surface enclosure formula (geometry simplified => loose)",
              detail="" if st == "PASS" else "outside band; check F, areas, eps, geometry")


# ========================================================================== #
# TIER 3 -- analytical conduction
# ========================================================================== #
@gate("G3.1", 3, "Coax conduction vs conductivity integral")
def g_coax_conduction(ctx, cfg):
    coaxes = cfg.get("coax", [])
    if not coaxes:
        return _R(g_coax_conduction, "SKIP", detail="no coax definitions in cfg")
    tcold = cfg["temperatures"]["T_cold"]
    twarm = cfg["temperatures"]["T_warm"]
    tol = cfg.get("thresholds", {}).get("conduction_rel", 0.15)
    rows = []; worst = 0.0; fail = False; verify_any = False
    for c in coaxes:
        patch = c["patch"]
        if patch not in ctx.patch_diff:
            rows.append("%s: no CFD flux" % patch)
            continue
        q_cfd = abs(ctx.patch_diff[patch])
        q_an_total = 0.0
        for seg in c["segments"]:
            q, verify, _ = mat.conduction_load(
                seg["material"], seg["area_m2"], c["length_m"], tcold, twarm)
            q_an_total += q
            verify_any = verify_any or verify
        rel = abs(q_cfd - q_an_total) / max(q_an_total, 1e-15)
        worst = max(worst, rel)
        rows.append("%s: CFD=%s vs int=%s W (%.0f%%)"
                    % (patch, _num(q_cfd), _num(q_an_total), 100 * rel))
        if rel > tol:
            fail = True
    st = "FAIL" if fail else "PASS"
    detail = "rebuild material tables to NIST and set VERIFY=False" if verify_any else ""
    if verify_any and st == "PASS":
        st = "WARN"
        detail = "PASS but material k(T) still flagged VERIFY -- " + detail
    return _R(g_coax_conduction, st,
              measured="max %.0f%%; " % (100 * worst) + " | ".join(rows),
              criterion="|CFD - (A/L)∫k dT| within %g%%" % (100 * tol),
              basis="1-D Fourier conduction integral, no intermediate anchor",
              detail=detail)


@gate("G3.6", 3, "Effective-kappa bake closure (no solver run)")
def g_bake_closure(ctx, cfg):
    """Verify the baked solid k_eff reproduces the harness target BEFORE running
    the solver: Q_bake = (A_eff/L) * integral k_eff dT  ==  n_k * Q_cable.
    A_eff is the calibrated effective conductance area the solver actually sees."""
    from . import ofparse as P
    cal = cfg.get("calibration") or {}
    A_eff = cal.get("A_eff_m2")
    if not A_eff:
        return _R(g_bake_closure, "SKIP",
                  detail="no calibration.A_eff_m2 in cfg")
    if not ctx.solid_transport:
        return _R(g_bake_closure, "SKIP",
                  detail="no solid thermophysicalProperties parsed")
    tcold = cfg["temperatures"]["T_cold"]; twarm = cfg["temperatures"]["T_warm"]
    tol = cfg.get("thresholds", {}).get("bake_rel",
          cfg.get("thresholds", {}).get("conduction_rel", 0.15))
    rows = []; worst = 0.0; fail = False; verify_any = False
    for c in cfg.get("coax", []):
        region = c["patch"].replace("domain1_to_", "")
        tr = ctx.solid_transport.get(region)
        if tr is None:
            rows.append("%s: no props" % region); continue
        intk = P.integrate_kappa(tr, tcold, twarm)
        if intk is None:
            rows.append("%s: unreadable kappa" % region); continue
        L = c["length_m"]
        q_bake = (A_eff / L) * intk
        # harness target = n_k * per-cable integral (sum of component integrals)
        q_target = 0.0
        for seg in c["segments"]:
            q, v, _ = mat.conduction_load(seg["material"], seg["area_m2"], L,
                                          tcold, twarm)
            q_target += q; verify_any = verify_any or v
        rel = abs(q_bake - q_target) / max(q_target, 1e-15)
        worst = max(worst, rel)
        tag = tr[0]
        rows.append("%s[%s]: bake=%s vs target=%s W (%.0f%%)"
                    % (region, tag, _num(q_bake), _num(q_target), 100 * rel))
        if rel > tol:
            fail = True
    if not rows:
        return _R(g_bake_closure, "SKIP", detail="no coax to check")
    st = "FAIL" if fail else "PASS"
    detail = ""
    if not fail and any("constIso" in r for r in rows):
        detail = ("note: constant-kappa bake hits the load but not the steady "
                  "gradient; use polynomial k_eff(T) for the profile.")
    return _R(g_bake_closure, st,
              measured="A_eff=%s m^2; max %.0f%%; " % (_num(A_eff), 100 * worst)
                       + " | ".join(rows),
              criterion="(A_eff/L)∫k_eff dT within %g%% of n_k*Q_cable" % (100 * tol),
              basis="calibrated bake closure -- verifies k_eff before the solver run",
              detail=detail)


@gate("G3.2", 3, "Total cold-side load vs lumped network")
def g_total_network(ctx, cfg):
    net = cfg.get("network_check")
    if not net:
        return _R(g_total_network, "SKIP", detail="no network_check in cfg")
    # CFD: sum of loads onto the cold boundary patches
    cold_patches = net["cold_patches"]
    q_cfd = sum(abs(ctx.patch_total.get(p, 0.0)) for p in cold_patches)
    # analytic: conduction integrals + radiation onto cold stage
    q_cond = 0.0; verify_any = False
    tcold = cfg["temperatures"]["T_cold"]; twarm = cfg["temperatures"]["T_warm"]
    for c in cfg.get("coax", []):
        for seg in c["segments"]:
            q, v, _ = mat.conduction_load(seg["material"], seg["area_m2"],
                                          c["length_m"], tcold, twarm)
            q_cond += q; verify_any = verify_any or v
    q_rad = 0.0
    rc = cfg.get("radiation_check")
    if rc:
        geom = getattr(ctx, "geom", {})
        A_hot = rc.get("A_hot") or (geom.get(rc.get("hot_patch", ""), {}) or {}).get("area")
        A_cold = rc.get("A_cold") or (geom.get(rc.get("cold_patch", ""), {}) or {}).get("area")
        if A_hot and A_cold:
            q_rad = abs(an.two_surface_radiation(
                rc["eps_hot"], A_hot, rc["T_hot"],
                rc["eps_cold"], A_cold, rc["T_cold"], rc.get("F", 1.0)))
    q_an = q_cond + q_rad
    tol = cfg.get("thresholds", {}).get("network_rel", 0.25)
    rel = abs(q_cfd - q_an) / max(q_an, 1e-15)
    st = "PASS" if rel <= tol else "WARN"
    return _R(g_total_network, st,
              measured="CFD=%s W vs net(cond %s + rad %s)=%s W (%.0f%%)"
                       % (_num(q_cfd), _num(q_cond), _num(q_rad), _num(q_an), 100 * rel),
              criterion="within %g%%" % (100 * tol),
              basis="lumped resistance network: conduction integral + radiation",
              detail="material VERIFY flagged" if verify_any else "")


# ========================================================================== #
# TIER 4 -- regime guards (these would have caught the 1-atm bug)
# ========================================================================== #
@gate("G4.1", 4, "Pressure sanity (vacuum, not 1 atm)")
def g_pressure(ctx, cfg):
    if ctx.pressure is None:
        return _R(g_pressure, "SKIP", detail="no p internalField read")
    exp = cfg.get("regime", {}).get("expected_pressure_Pa", 0.001)
    factor = cfg.get("regime", {}).get("pressure_tol_factor", 10.0)
    lo, hi = exp / factor, exp * factor
    st = "PASS" if lo <= ctx.pressure <= hi else "FAIL"
    return _R(g_pressure, st,
              measured="p=%s Pa" % _num(ctx.pressure),
              criterion="%g..%g Pa" % (lo, hi),
              basis="vacuum operating pressure; guards against stray 101325 Pa",
              detail="" if st == "PASS" else "pressure off by >%gx -- check p, p_rgh, pRef, setFields" % factor)


@gate("G4.2", 4, "Density sanity (vacuum)")
def g_density(ctx, cfg):
    if ctx.rho is None:
        return _R(g_density, "SKIP", detail="no rho")
    lim = cfg.get("regime", {}).get("rho_max_kgm3", 1e-5)
    st = "PASS" if ctx.rho <= lim else "FAIL"
    return _R(g_density, st, measured="rho=%s kg/m^3" % _num(ctx.rho),
              criterion="<= %g" % lim,
              basis="ideal-gas rho=pM/RT; dense gas => convection regime",
              detail="" if st == "PASS" else "gas is dense -- likely wrong pressure")


@gate("G4.3", 4, "Rayleigh guard (no spurious convection)")
def g_rayleigh(ctx, cfg):
    rg = cfg.get("regime", {})
    p = ctx.pressure
    if p is None:
        return _R(g_rayleigh, "SKIP", detail="no pressure")
    mu = ctx.mu if ctx.mu is not None else rg.get("mu", 1e-11)
    Cp = rg.get("Cp", 5193.0); Pr = rg.get("Pr", 0.67)
    mw = rg.get("molWeight", 4.003)
    kappa = an.kappa_from_mu_pr(mu, Cp, Pr)
    L = rg.get("gap_m", 0.05)
    Ra = an.rayleigh(p, cfg["temperatures"]["T_warm"],
                     cfg["temperatures"]["T_cold"], L, mu, Cp, kappa, mw)
    limit = rg.get("rayleigh_max", 1e3)
    st = "PASS" if Ra < limit else "FAIL"
    return _R(g_rayleigh, st, measured="Ra=%s" % _num(Ra),
              criterion="< %g" % limit,
              basis="Ra<~1e3 => buoyant convection negligible & steady solve well-posed",
              detail="" if st == "PASS" else "high Ra => unsteady convection; steady laminar invalid")


@gate("G4.4", 4, "Knudsen / gas-conduction consistency")
def g_knudsen(ctx, cfg):
    rg = cfg.get("regime", {})
    p = ctx.pressure
    if p is None:
        return _R(g_knudsen, "SKIP", detail="no pressure")
    L = rg.get("gap_m", 0.05)
    Tg = 0.5 * (cfg["temperatures"]["T_warm"] + cfg["temperatures"]["T_cold"])
    Kn = an.knudsen(p, Tg, L)
    mu = ctx.mu if ctx.mu is not None else rg.get("mu", 1e-11)
    kappa = an.kappa_from_mu_pr(mu, rg.get("Cp", 5193.0), rg.get("Pr", 0.67))
    # spurious continuum gas conduction across the gap, vs stage load
    dT = abs(cfg["temperatures"]["T_warm"] - cfg["temperatures"]["T_cold"])
    A_gap = rg.get("gap_area_m2", 0.05)
    q_gas = an.continuum_gas_conduction(kappa, A_gap, L, dT)
    stage_load = max((abs(v) for v in ctx.patch_total.values()), default=1.0)
    frac = q_gas / stage_load if stage_load else 0.0
    budget = cfg.get("thresholds", {}).get("gas_conduction_frac", 0.01)
    if Kn > 1 and frac > budget:
        st, det = "WARN", ("Kn>1 (molecular) yet modelled gas conduction is %.2g%% "
                           "of load; continuum kappa is wrong form here" % (100 * frac))
    elif frac > budget:
        st, det = "WARN", "gas conduction %.2g%% of load exceeds budget" % (100 * frac)
    else:
        st, det = "PASS", ""
    return _R(g_knudsen, st,
              measured="Kn=%s, q_gas=%s W (%.2g%% of load)"
                       % (_num(Kn), _num(q_gas), 100 * frac),
              criterion="gas conduction < %g%% of stage load" % (100 * budget),
              basis="Kn>>1 => free-molecular (q~p), not Fourier; gas should be thermally inert",
              detail=det)


# ========================================================================== #
# TIER 5 -- provenance & boundary-condition audit
# ========================================================================== #
@gate("G5.1", 5, "Boundary-condition audit (T BCs match spec)")
def g_bc_audit(ctx, cfg):
    spec = cfg.get("expected_T_bc")
    if not spec:
        return _R(g_bc_audit, "SKIP", detail="no expected_T_bc table in cfg")
    problems = []
    for patch, want in spec.items():
        got = ctx.bc_T.get(patch)
        if got is None:
            problems.append("%s: absent" % patch); continue
        wt = want.get("type")
        if wt and isinstance(got, str) and got != wt:
            problems.append("%s: type %s!=%s" % (patch, got, wt))
        wv = want.get("value")
        if wv is not None and isinstance(got, (int, float)) \
                and abs(got - wv) > 1e-6 * max(1.0, abs(wv)):
            problems.append("%s: value %s!=%s" % (patch, _num(got), _num(wv)))
    st = "FAIL" if problems else "PASS"
    return _R(g_bc_audit, st,
              measured="checked %d patches" % len(spec),
              criterion="each T BC matches spec table",
              basis="catches mislabeled / wrong fixedValue (e.g. 300 K on cold end)",
              detail="; ".join(problems))


@gate("G5.2", 5, "controlDict patch-integral audit")
def g_controldict_audit(ctx, cfg):
    txt = ctx.controlDict_text
    if not txt:
        return _R(g_controldict_audit, "SKIP", detail="controlDict not read")
    import re
    # each functionObject named patchInt_<X>_... should reference patch <X>
    problems = []
    for m in re.finditer(r"(patchInt_(\w+?)_\w+)\s*\{(.*?)\}", txt, re.DOTALL):
        fo, tag, body = m.group(1), m.group(2), m.group(3)
        pm = re.search(r"\bpatch(?:es)?\b[^;]*?(\w+)\s*[;\)]", body)
        if pm and tag.lower() not in pm.group(1).lower() \
                and pm.group(1).lower() not in tag.lower():
            problems.append("%s -> patch %s" % (fo, pm.group(1)))
    st = "FAIL" if problems else "PASS"
    return _R(g_controldict_audit, st,
              measured="%d patchInt FOs scanned" % txt.count("patchInt_"),
              criterion="patchInt_<X> references patch <X>",
              basis="catches the coldPlate-using-shield-name reporting bug",
              detail="; ".join(problems))


@gate("G5.3", 5, "Mesh quality (checkMesh)")
def g_mesh_quality(ctx, cfg):
    cm = ctx.checkmesh
    if not cm:
        return _R(g_mesh_quality, "SKIP", detail="no checkMesh log")
    th = cfg.get("thresholds", {})
    no = cm.get("maxNonOrtho"); sk = cm.get("maxSkewness")
    probs = []
    if no is not None and no > th.get("max_non_ortho", 70):
        probs.append("nonOrtho %.1f" % no)
    if sk is not None and sk > th.get("max_skewness", 4.0):
        probs.append("skewness %.2f" % sk)
    st = "FAIL" if probs else "PASS"
    return _R(g_mesh_quality, st,
              measured="nonOrtho=%s skew=%s ok=%s"
                       % (_num(no), _num(sk), cm.get("mesh_ok")),
              criterion="nonOrtho<%g, skew<%g" % (th.get("max_non_ortho", 70),
                                                  th.get("max_skewness", 4.0)),
              basis="checkMesh", detail="; ".join(probs))


@gate("G5.4", 5, "Provenance record")
def g_provenance(ctx, cfg):
    p = ctx.provenance
    meas = ", ".join("%s=%s" % (k, v) for k, v in p.items()) or "none"
    return _R(g_provenance, "PASS", measured=meas,
              criterion="recorded", basis="reproducibility metadata")


def run_all(ctx, cfg):
    return [fn(ctx, cfg) for fn in GATE_REGISTRY]
