#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selftest.py -- build a synthetic OpenFOAM case in a temp dir and run the suite
against it, asserting that gates fire correctly. No OpenFOAM install needed.

Run:  python3 tests/selftest.py      (exit 0 = all assertions passed)
"""

import os
import sys
import json
import shutil
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from gatecheck import runner  # noqa: E402

HEAD = ("FoamFile\n{\n version 2.0; format ascii; class %s;"
        " location \"%s\"; object %s;\n}\n// * * *\n")

# unit-cube boundary faces (each area = 1) -> 6 named patches
FACES = ["4(0 3 2 1)", "4(4 5 6 7)", "4(0 1 5 4)",
         "4(3 7 6 2)", "4(0 4 7 3)", "4(1 2 6 5)"]
POINTS = ["(0 0 0)", "(1 0 0)", "(1 1 0)", "(0 1 0)",
          "(0 0 1)", "(1 0 1)", "(1 1 1)", "(0 1 1)"]
PATCHES = ["warmPlate", "shield", "coldPlate", "shield_bottom",
           "domain1_to_coax_L1", "domain1_to_coax_L2"]


def _w(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(text)


def _field_bfile(loc, obj, perpatch, cls="volScalarField"):
    s = HEAD % (cls, loc, obj) + "dimensions [0 0 0 0 0 0 0];\n"
    s += "internalField uniform 0;\nboundaryField\n{\n"
    for p in PATCHES:
        s += "    %s { type calculated; value uniform %g; }\n" % (p, perpatch[p])
    s += "}\n"
    return s


def build_case(root, pressure=0.001, rad=None, diff=None, T_internal=150.0):
    """rad/diff: dict patch->value. Defaults give closed radiation & balance."""
    if rad is None:
        rad = {"warmPlate": 3.0, "shield": -1.5, "coldPlate": -1.5,
               "shield_bottom": 0.0, "domain1_to_coax_L1": 0.0,
               "domain1_to_coax_L2": 0.0}
    if diff is None:
        diff = {"warmPlate": 4.0, "shield": 0.0, "coldPlate": 0.0,
                "shield_bottom": 0.0, "domain1_to_coax_L1": -2.0,
                "domain1_to_coax_L2": -2.0}

    reg = "domain1"
    mesh = os.path.join(root, "constant", reg, "polyMesh")
    _w(os.path.join(mesh, "points"),
       HEAD % ("vectorField", "constant/%s/polyMesh" % reg, "points")
       + "8\n(\n" + "\n".join(POINTS) + "\n)\n")
    _w(os.path.join(mesh, "faces"),
       HEAD % ("faceList", "constant/%s/polyMesh" % reg, "faces")
       + "6\n(\n" + "\n".join(FACES) + "\n)\n")
    bnd = HEAD % ("polyBoundaryMesh", "constant/%s/polyMesh" % reg, "boundary")
    bnd += "6\n(\n"
    for i, p in enumerate(PATCHES):
        typ = "mappedWall" if "coax" in p else "wall"
        bnd += "    %s { type %s; nFaces 1; startFace %d; }\n" % (p, typ, i)
    bnd += ")\n"
    _w(os.path.join(mesh, "boundary"), bnd)

    # thermophysicalProperties
    _w(os.path.join(root, "constant", reg, "thermophysicalProperties"),
       "thermoType { equationOfState perfectGas; }\n"
       "mixture { specie { molWeight 4.003; } thermodynamics { Cp 5193; }"
       " transport { mu 1e-11; Pr 0.67; } }\n")
    # boundaryRadiationProperties (emissivities assigned to all radiating patches)
    br = ""
    for p in PATCHES:
        e = 0.04 if p in ("warmPlate", "coldPlate", "shield_bottom") else 0.02
        br += "%s { type lookup; emissivity %g; absorptivity %g; }\n" % (p, e, e)
    _w(os.path.join(root, "constant", reg, "boundaryRadiationProperties"), br)

    # time dir 2000 fields
    t = os.path.join(root, "2000", reg)
    _w(os.path.join(t, "wallHeatFlux"),
       _field_bfile("2000/%s" % reg, "wallHeatFlux", diff))
    _w(os.path.join(t, "qr"), _field_bfile("2000/%s" % reg, "qr", rad))
    _w(os.path.join(t, "p"),
       HEAD % ("volScalarField", "2000/%s" % reg, "p")
       + "dimensions [1 -1 -2 0 0 0 0];\ninternalField uniform %g;\n"
         "boundaryField { }\n" % pressure)
    # T with BCs matching the spec table
    Tbc = {"warmPlate": ("fixedValue", 300.0), "shield": ("fixedValue", 77.0),
           "coldPlate": ("fixedValue", 77.0), "shield_bottom": ("fixedValue", 77.0),
           "domain1_to_coax_L1": ("compressible::turbulentTemperatureCoupledBaffleMixed", None),
           "domain1_to_coax_L2": ("compressible::turbulentTemperatureCoupledBaffleMixed", None)}
    Ttxt = (HEAD % ("volScalarField", "2000/%s" % reg, "T")
            + "dimensions [0 0 0 1 0 0 0];\ninternalField uniform %g;\n"
              "boundaryField\n{\n" % T_internal)
    for p, (typ, val) in Tbc.items():
        if val is None:
            Ttxt += "    %s { type %s; value uniform %g; }\n" % (p, typ, T_internal)
        else:
            Ttxt += "    %s { type %s; value uniform %g; }\n" % (p, typ, val)
    Ttxt += "}\n"
    _w(os.path.join(t, "T"), Ttxt)

    # also a previous time (1950) identical -> steady passes
    shutil.copytree(os.path.join(root, "2000"), os.path.join(root, "1950"))

    # controlDict with a correct patchInt FO and a buggy one
    _w(os.path.join(root, "system", "controlDict"),
       "functions {\n"
       "  patchInt_shield_WHF { type surfaceFieldValue; regionType patch;"
       " name shield; }\n"
       "}\n")
    # solver log: residuals descending below tol
    log = ""
    for it, r in [(1, 1e-1), (2, 1e-3), (3, 1e-6), (4, 5e-7)]:
        log += "Time = %d\n" % it
        for f in ["Ux", "Uy", "Uz", "h", "p_rgh", "G"]:
            log += ("smoothSolver:  Solving for %s, Initial residual = %g,"
                    " Final residual = %g, No Iterations 3\n" % (f, r, r / 10))
    _w(os.path.join(root, "log.solve"), log)


def make_cfg(root):
    from gatecheck import materials as mat
    cfg_path = os.path.join(ROOT, "config", "stage1_shield_77K.json")
    cfg = json.load(open(cfg_path))
    cfg["case_dir"] = root
    cfg["log_file"] = "log.solve"
    cfg["solid_regions"] = []           # synthetic case has no solids
    cfg["radiating_patches"] = list(PATCHES)   # only patches the toy mesh has
    # size a single SS304 segment so the integral matches the toy flux (|2 W|)
    integ, _, _ = mat.conductivity_integral("SS304", 77.0, 300.0)
    area = 2.0 * 0.335 / integ
    cfg["coax"] = [
        {"patch": "domain1_to_coax_L1", "length_m": 0.335,
         "segments": [{"material": "SS304", "area_m2": area}]},
        {"patch": "domain1_to_coax_L2", "length_m": 0.335,
         "segments": [{"material": "SS304", "area_m2": area}]},
    ]
    tmp = os.path.join(root, "_cfg.json")
    json.dump(cfg, open(tmp, "w"))
    return tmp


def status_of(results, gid):
    for r in results:
        if r.id == gid:
            return r.status
    return None


def main():
    failures = []

    def check(cond, msg):
        print(("  ok  " if cond else "  FAIL") + "  " + msg)
        if not cond:
            failures.append(msg)

    # ---- 1. healthy case: no FAILs -------------------------------------- #
    d = tempfile.mkdtemp(prefix="gateself_")
    try:
        build_case(d)
        results, counts = runner.run(make_cfg(d), quiet=True)
        print("[healthy case]")
        check(counts["FAIL"] == 0, "healthy case has zero FAILs (got %d)" % counts["FAIL"])
        check(status_of(results, "G1.1") == "PASS", "G1.1 energy balance PASS")
        check(status_of(results, "G1.2") == "PASS", "G1.2 radiation closure PASS")
        check(status_of(results, "G0.1") == "PASS", "G0.1 residuals PASS")
        check(status_of(results, "G4.1") == "PASS", "G4.1 pressure PASS")
        check(status_of(results, "G5.1") == "PASS", "G5.1 BC audit PASS")
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # ---- 2. 1-atm bug: pressure & density & rayleigh FAIL --------------- #
    d = tempfile.mkdtemp(prefix="gateself_")
    try:
        build_case(d, pressure=101325.0)
        results, counts = runner.run(make_cfg(d), quiet=True)
        print("[1-atm pressure bug]")
        check(status_of(results, "G4.1") == "FAIL", "G4.1 pressure FAIL at 1 atm")
        check(status_of(results, "G4.2") == "FAIL", "G4.2 density FAIL at 1 atm")
        check(status_of(results, "G4.3") == "FAIL", "G4.3 rayleigh FAIL at 1 atm")
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # ---- 3. radiation-sink bug (G=0 style): closure FAIL ---------------- #
    d = tempfile.mkdtemp(prefix="gateself_")
    try:
        rad = {"warmPlate": 3.0, "shield": -1.5, "coldPlate": -1.5,
               "shield_bottom": 0.0, "domain1_to_coax_L1": -3.945,  # spurious sink
               "domain1_to_coax_L2": 0.0}
        build_case(d, rad=rad)
        results, counts = runner.run(make_cfg(d), quiet=True)
        print("[spurious radiation sink]")
        check(status_of(results, "G1.2") == "FAIL", "G1.2 radiation closure FAIL with sink")
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # ---- 4. wrong BC: cold end at 300 K -> BC audit FAIL ---------------- #
    d = tempfile.mkdtemp(prefix="gateself_")
    try:
        build_case(d)
        # corrupt shield BC to 300 in the T file
        tf = os.path.join(d, "2000", "domain1", "T")
        txt = open(tf).read().replace("shield { type fixedValue; value uniform 77",
                                      "shield { type fixedValue; value uniform 300")
        open(tf, "w").write(txt)
        results, counts = runner.run(make_cfg(d), quiet=True)
        print("[wrong cold BC]")
        check(status_of(results, "G5.1") == "FAIL", "G5.1 BC audit FAIL when shield=300")
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # ---- 5. bake-closure gate G3.6 (no solver) -------------------------- #
    d = tempfile.mkdtemp(prefix="gateself_")
    try:
        build_case(d)
        from gatecheck import materials as mat
        cfg = json.load(open(make_cfg(d)))
        # target per coax (make_cfg sizes both L1,L2 to ~2 W via SS304)
        A_eff = 3.93e-3
        cfg["calibration"] = {"A_eff_m2": A_eff, "length_m": 0.335}
        cfg["solid_regions"] = ["coax_L1", "coax_L2"]
        cfg["thresholds"]["bake_rel"] = 0.15
        # constant-kappa bake calibrated to hit each coax's target
        for cx in cfg["coax"]:
            region = cx["patch"].replace("domain1_to_", "")
            L = cx["length_m"]
            q_t = sum(mat.conduction_load(s["material"], s["area_m2"], L, 77.0, 300.0)[0]
                      for s in cx["segments"])
            kappa = q_t * L / (A_eff * (300.0 - 77.0))   # constIso to hit target
            _w(os.path.join(d, "constant", region, "thermophysicalProperties"),
               "thermoType { transport constIso; }\n"
               "mixture { transport { kappa %g; } }\n" % kappa)
        tmp = os.path.join(d, "_cfg2.json"); json.dump(cfg, open(tmp, "w"))
        results, _ = runner.run(tmp, quiet=True)
        print("[bake closure G3.6 -- correct bake]")
        check(status_of(results, "G3.6") == "PASS", "G3.6 PASS when bake hits target")
        # now corrupt one coax kappa by 3x -> must FAIL
        _w(os.path.join(d, "constant", "coax_L1", "thermophysicalProperties"),
           "thermoType { transport constIso; }\n"
           "mixture { transport { kappa 999; } }\n")
        results, _ = runner.run(tmp, quiet=True)
        print("[bake closure G3.6 -- wrong kappa]")
        check(status_of(results, "G3.6") == "FAIL", "G3.6 FAIL when bake off target")
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("\n%d assertion(s) failed" % len(failures) if failures
          else "\nALL SELF-TESTS PASSED")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
