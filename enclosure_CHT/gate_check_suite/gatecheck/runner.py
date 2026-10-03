#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
runner.py -- load a case, build the ctx, run gates, emit report.

Usage:
    python3 -m gatecheck.runner CONFIG.json [--case DIR] [--json OUT.json]
                                            [--junit OUT.xml] [--quiet]

CONFIG.json fully describes the case (region/patch names, temperatures,
materials, thresholds, expected BCs). See config/*.json for worked examples.
"""

import os
import re
import sys
import json
import argparse

from . import ofparse as P
from . import logparse as L
from . import analytical as an
from . import gates as G


# --------------------------------------------------------------------------- #
class CaseData:
    """Everything the gates read, parsed once."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.case = cfg["_case_dir"]
        self.fluid = cfg.get("fluid_region", "domain1")

        self.patch_diff = {}        # patch -> integral(wallHeatFlux)  [W]
        self.patch_rad = {}         # patch -> integral(qr)            [W]
        self.patch_total = {}       # diff + rad
        self.prev_loads = {}        # patch -> total at previous time
        self.T_bounds = {}          # region -> (min,max)
        self.bc_T = {}              # patch -> BC type(str) or value(float)
        self.emissivity = {}        # patch -> eps
        self.residuals = {}
        self.n_steps = 0
        self.pressure = None
        self.rho = None
        self.mu = None
        self.viewfactor_rowsums = []
        self.interface_pairs = []   # (fluid_patch, Q_fluid, Q_solid|None)
        self.controlDict_text = ""
        self.checkmesh = {}
        self.provenance = {}
        self.solid_transport = {}   # region -> (type, kappa|coeffs)
        self.radiating_patches = cfg.get("radiating_patches", [])

        self._load()

    # ---- helpers --------------------------------------------------------- #
    def _times(self):
        return P.list_time_dirs(self.case)

    def _integrate(self, fieldvals, geom):
        """fieldvals: {patch->float|list|str}; geom: {patch->dict(area,areas)}."""
        out = {}
        for name, g in geom.items():
            v = fieldvals.get(name)
            if v is None or isinstance(v, str):
                continue
            if isinstance(v, list):
                if len(v) != len(g["areas"]):
                    continue
                out[name] = sum(v[i] * g["areas"][i] for i in range(len(v)))
            else:
                out[name] = v * g["area"]
        return out

    # ---- main load ------------------------------------------------------- #
    def _load(self):
        case, fluid = self.case, self.fluid
        times = self._times()
        t = self.cfg.get("time", None)
        if t is None or not os.path.isdir(os.path.join(case, str(t))):
            t = times[-1] if times else None
        self.time = t

        # geometry of fluid region
        try:
            pts, geom = P.patch_area_map(case, fluid)
        except OSError as e:
            self.provenance["geom_error"] = str(e)
            return
        self.geom = geom

        # wall loads at converged time
        fdir = os.path.join(case, str(t), fluid)
        whf = self._safe_field(os.path.join(fdir, "wallHeatFlux"))
        qr = self._safe_field(os.path.join(fdir, "qr"))
        self.patch_diff = self._integrate(whf, geom)
        self.patch_rad = self._integrate(qr, geom)
        for p in set(self.patch_diff) | set(self.patch_rad):
            self.patch_total[p] = (self.patch_diff.get(p, 0.0)
                                   + self.patch_rad.get(p, 0.0))

        # previous time -> steady-state drift
        prev = [x for x in times if float(x) < float(t)]
        if prev:
            pdir = os.path.join(case, str(prev[-1]), fluid)
            pw = self._safe_field(os.path.join(pdir, "wallHeatFlux"))
            pq = self._safe_field(os.path.join(pdir, "qr"))
            pdiff = self._integrate(pw, geom); prad = self._integrate(pq, geom)
            for p in set(pdiff) | set(prad):
                self.prev_loads[p] = pdiff.get(p, 0.0) + prad.get(p, 0.0)

        # T bounds for fluid + solid regions
        regions = [fluid] + self.cfg.get("solid_regions", [])
        for r in regions:
            tb = self._field_bounds(os.path.join(case, str(t), r, "T"))
            if tb:
                self.T_bounds[r] = tb

        # T boundary conditions (fluid region)
        self.bc_T = self._bc_types_values(os.path.join(case, str(t), fluid, "T"))

        # pressure + density + mu
        self.pressure = self._internal_repr(os.path.join(case, str(t), fluid, "p"))
        if self.pressure is None:
            self.pressure = self._internal_repr(os.path.join(case, "0", fluid, "p"))
        rho = self._internal_repr(os.path.join(case, str(t), fluid, "rho"))
        thp = os.path.join(case, "constant", fluid, "thermophysicalProperties")
        self.mu = P.read_dict_scalar(thp, "mu")
        mw = P.read_dict_scalar(thp, "molWeight") or self.cfg.get("regime", {}).get("molWeight", 4.003)
        if rho is not None:
            self.rho = rho
        elif self.pressure is not None and self.T_bounds.get(fluid):
            Tm = 0.5 * sum(self.T_bounds[fluid])
            self.rho = an.gas_density(self.pressure, max(Tm, 1e-3), mw)

        # emissivities
        self.emissivity = self._emissivities(
            os.path.join(case, "constant", fluid, "boundaryRadiationProperties"))
        if not self.radiating_patches:
            self.radiating_patches = list(self.emissivity)

        # solid coax effective conductivity (for bake-closure gate)
        for r in self.cfg.get("solid_regions", []):
            tp = os.path.join(case, "constant", r, "thermophysicalProperties")
            if os.path.exists(tp):
                self.solid_transport[r] = P.read_solid_transport(tp)

        # interface continuity: match domain1_to_coax_Lk with solid coax patch
        self._interfaces()

        # residuals + steps
        logf = self.cfg.get("log_file")
        if logf:
            lp = logf if os.path.isabs(logf) else os.path.join(case, logf)
            if not os.path.exists(lp):                  # maybe relative to parent
                lp2 = os.path.join(os.path.dirname(case), logf)
                lp = lp2 if os.path.exists(lp2) else lp
            self.residuals = L.last_residuals(lp)
            self.n_steps = L.n_time_steps(lp)

        # checkMesh
        cmf = self.cfg.get("checkmesh_log")
        if cmf:
            cmp = cmf if os.path.isabs(cmf) else os.path.join(case, cmf)
            self.checkmesh = L.parse_checkmesh(cmp)

        # controlDict
        cd = os.path.join(case, "system", "controlDict")
        if os.path.exists(cd):
            try:
                self.controlDict_text = open(cd, "r", errors="replace").read()
            except OSError:
                pass

        # view factors (optional)
        self._viewfactors()

        # provenance
        self._provenance()

    # ---- sub-readers ----------------------------------------------------- #
    def _safe_field(self, path):
        try:
            return P.read_field_boundary(path)
        except (OSError, ValueError):
            return {}

    def _internal_repr(self, path):
        """Representative internal scalar (uniform value or mean of list)."""
        if not os.path.exists(path):
            return None
        try:
            kind, data = P.read_internal_scalar(path)
        except (OSError, ValueError, struct_err()):
            return None
        if kind == "uniform":
            return data
        if kind == "nonuniform" and data:
            return sum(data) / len(data)
        return None

    def _field_bounds(self, path):
        if not os.path.exists(path):
            return None
        try:
            kind, data = P.read_internal_scalar(path)
        except (OSError, ValueError):
            return None
        if kind == "uniform":
            return (data, data)
        if kind == "nonuniform" and data:
            return (min(data), max(data))
        return None

    def _bc_types_values(self, path):
        """Return patch -> value(float) if fixedValue uniform, else type str."""
        if not os.path.exists(path):
            return {}
        try:
            raw = open(path, "rb").read().decode("latin-1", "replace")
        except OSError:
            return {}
        out = {}
        i = raw.find("boundaryField")
        body = raw[i:] if i >= 0 else raw
        for m in re.finditer(r"(\w+)\s*\{([^{}]*?)\}", body, re.DOTALL):
            name, blk = m.group(1), m.group(2)
            tp = re.search(r"type\s+(\S+)\s*;", blk)
            val = re.search(r"value\s+uniform\s+([-+0-9.eE]+)\s*;", blk)
            if val:
                out[name] = float(val.group(1))
            elif tp:
                out[name] = tp.group(1)
        return out

    def _emissivities(self, path):
        if not os.path.exists(path):
            return {}
        try:
            txt = open(path, "rb").read().decode("latin-1", "replace")
        except OSError:
            return {}
        out = {}
        for m in re.finditer(r"(\w+)\s*\{[^}]*?emissivity\s+([-+0-9.eE]+)", txt):
            out[m.group(1)] = float(m.group(2))
        return out

    def _interfaces(self):
        """Pair fluid-side coax interface flux with the solid-side patch flux."""
        pairs = []
        for fp, qf in self.patch_diff.items():
            m = re.search(r"coax[_]?(L?\d+)", fp, re.I)
            if not m or "coax" not in fp.lower():
                continue
            qs = None
            # try solid region 'coax_<id>' with patch '<region>_to_<fluid>'
            for cand_region in self.cfg.get("solid_regions", []):
                if m.group(1).lower() in cand_region.lower():
                    sdir = os.path.join(self.case, str(self.time), cand_region)
                    sw = self._safe_field(os.path.join(sdir, "wallHeatFlux"))
                    try:
                        _, sgeom = P.patch_area_map(self.case, cand_region)
                    except OSError:
                        sgeom = {}
                    sint = self._integrate(sw, sgeom)
                    if sint:
                        # solid patch facing the fluid
                        for sp, sv in sint.items():
                            if self.fluid.lower() in sp.lower() or "domain" in sp.lower():
                                qs = sv; break
                    break
            pairs.append((fp, qf, qs))
        self.interface_pairs = pairs

    def _viewfactors(self):
        """Optional: row sums from constant/<fluid>/F if present (ascii)."""
        fpath = os.path.join(self.case, "constant", self.fluid, "F")
        if not os.path.exists(fpath):
            return
        try:
            raw = open(fpath, "rb").read().decode("latin-1", "replace")
        except OSError:
            return
        # F is a List<scalarList>; sum each inner list. Best-effort ascii parse.
        rows = []
        body = raw[raw.find("// *"):] if "// *" in raw else raw
        for inner in re.finditer(r"\d+\s*\(([^()]*)\)", body):
            nums = re.findall(r"[-+0-9.eE]+", inner.group(1))
            if nums:
                rows.append(sum(float(x) for x in nums))
        # drop the outer count match if present
        self.viewfactor_rowsums = rows[1:] if len(rows) > 1 else rows

    def _provenance(self):
        self.provenance["solver"] = self.cfg.get("solver", "chtMultiRegionSimpleFoam")
        self.provenance["time"] = str(self.time)
        self.provenance["n_iter"] = self.n_steps
        # OpenFOAM version from a field header
        ph = os.path.join(self.case, str(self.time), self.fluid, "T")
        if os.path.exists(ph):
            try:
                head = open(ph, "rb").read(800).decode("latin-1", "replace")
                mv = re.search(r"Version:\s*([\w.]+)", head)
                if mv:
                    self.provenance["OF_version"] = mv.group(1)
            except OSError:
                pass


def struct_err():
    import struct
    return struct.error


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #
COLORS = dict(PASS="\033[92m", FAIL="\033[91m", WARN="\033[93m",
              SKIP="\033[90m", END="\033[0m")


def _c(status, txt, color):
    return (COLORS[status] + txt + COLORS["END"]) if color else txt


def print_report(results, cfg, color=True):
    name = cfg.get("name", cfg.get("_case_dir", "case"))
    print("\n" + "=" * 78)
    print("GATE-CHECK REPORT  --  %s" % name)
    print("=" * 78)
    cur = None
    tiers = {0: "Numerical health", 1: "Conservation", 2: "Radiation model",
             3: "Analytical conduction", 4: "Regime guards",
             5: "Provenance & BC audit"}
    for r in sorted(results, key=lambda r: (r.tier, r.id)):
        if r.tier != cur:
            cur = r.tier
            print("\n-- Tier %d: %s " % (cur, tiers.get(cur, "")) + "-" * 30)
        tag = _c(r.status, "%-4s" % r.status, color)
        print("  [%s] %-6s %s" % (tag, r.id, r.name))
        if r.measured:
            print("           measured : %s" % r.measured)
        if r.criterion:
            print("           criterion: %s" % r.criterion)
        if r.detail:
            print("           note     : %s" % r.detail)
    counts = {s: sum(1 for r in results if r.status == s)
              for s in ("PASS", "FAIL", "WARN", "SKIP")}
    print("\n" + "=" * 78)
    verdict = "PASS (no FAILs)" if counts["FAIL"] == 0 else "FAIL"
    print("SUMMARY: %s | PASS %d  FAIL %d  WARN %d  SKIP %d"
          % (_c("PASS" if counts["FAIL"] == 0 else "FAIL", verdict, color),
             counts["PASS"], counts["FAIL"], counts["WARN"], counts["SKIP"]))
    print("=" * 78 + "\n")
    return counts


def write_json(results, cfg, path):
    out = dict(name=cfg.get("name"), case=cfg.get("_case_dir"),
               results=[r.as_dict() for r in results])
    out["summary"] = {s: sum(1 for r in results if r.status == s)
                      for s in ("PASS", "FAIL", "WARN", "SKIP")}
    with open(path, "w") as f:
        json.dump(out, f, indent=2)


def write_junit(results, cfg, path):
    import xml.sax.saxutils as su
    n = len(results)
    nf = sum(1 for r in results if r.status == "FAIL")
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<testsuite name="%s" tests="%d" failures="%d">'
             % (su.quoteattr(cfg.get("name", "case"))[1:-1], n, nf)]
    for r in results:
        nm = su.quoteattr("%s %s" % (r.id, r.name))
        lines.append('  <testcase name=%s classname="tier%d">' % (nm, r.tier))
        if r.status == "FAIL":
            lines.append('    <failure message=%s>%s</failure>'
                         % (su.quoteattr(r.criterion),
                            su.escape("%s | %s" % (r.measured, r.detail))))
        elif r.status == "SKIP":
            lines.append('    <skipped message=%s/>' % su.quoteattr(r.detail))
        lines.append('  </testcase>')
    lines.append('</testsuite>')
    open(path, "w").write("\n".join(lines))


# --------------------------------------------------------------------------- #
def load_config(path, case_override=None):
    with open(path) as f:
        cfg = json.load(f)
    case = case_override or cfg.get("case_dir")
    if not case:
        case = os.path.dirname(os.path.abspath(path))
    cfg["_case_dir"] = os.path.abspath(os.path.expanduser(case))
    return cfg


def run(config_path, case_override=None, json_out=None, junit_out=None,
        color=True, quiet=False):
    cfg = load_config(config_path, case_override)
    ctx = CaseData(cfg)
    results = G.run_all(ctx, cfg)
    if not quiet:
        counts = print_report(results, cfg, color=color)
    else:
        counts = {s: sum(1 for r in results if r.status == s)
                  for s in ("PASS", "FAIL", "WARN", "SKIP")}
    if json_out:
        write_json(results, cfg, json_out)
    if junit_out:
        write_junit(results, cfg, junit_out)
    return results, counts


def main(argv=None):
    ap = argparse.ArgumentParser(description="Cryostat CHT gate-check suite")
    ap.add_argument("config")
    ap.add_argument("--case", default=None, help="override case directory")
    ap.add_argument("--json", default=None, help="write JSON report")
    ap.add_argument("--junit", default=None, help="write JUnit XML")
    ap.add_argument("--no-color", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    _, counts = run(a.config, a.case, a.json, a.junit,
                    color=not a.no_color, quiet=a.quiet)
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
