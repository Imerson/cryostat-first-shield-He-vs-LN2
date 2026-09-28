#!/usr/bin/env python3
"""gen_hx_sweep.py -- build the cold-plate HX parametric campaign (paper v2, TSEP).

Clones the grid-converged production cases
  He : /home/ubuntu/channel/remesh/production/He_graded   (buoyantSimpleFoam, perfectGas)
  LN2: /home/ubuntu/channel/remesh/production/LN2_graded  (buoyantBoussinesqSimpleFoam)
into /home/ubuntu/hx_sweep/<case>/ with CORRECTED NIST/CoolProp properties, a target
Reynolds number, an operating pressure and (for Re >= 4000) the k-omega SST model.

Property sources (CoolProp HEOS, = NIST REFPROP): see data/fluid_properties.csv in the paper folder.
  He  @ 50 K, 1 bar : rho 0.9608  cp 5201  mu 6.360e-6  k 0.04668  Pr 0.709
  LN2 @ 77 K, 3 bar : rho 808.2   cp 2038  mu 1.635e-4  k 0.1457   Pr 2.286  beta 5.617e-3
The OLD He values (mu 2.73e-6, k 0.0185) correspond to helium near 15 K and were wrong.

Geometry (unchanged): 5 square 10 mm ducts, L = 0.3 m, heated area 0.015 m2, Q = 9.4 W.
"""
import os, shutil, re, math, sys, json

ROOT = '/home/ubuntu/hx_sweep'
SRC = {'He': '/home/ubuntu/channel/remesh/production/He_graded',
       'LN2': '/home/ubuntu/channel/remesh/production/LN2_graded'}
Q_W, A_HEAT, A_CS, DH, L = 9.4, 0.015, 0.0005, 0.01, 0.3
Q_FLUX = Q_W / A_HEAT                           # 626.67 W/m2
RGAS, MW_HE = 8.314, 4.0026e-3

PROPS = {
  'He':  dict(cp=5201.0, mu=6.360e-6, k=0.04668, Pr=0.709, Tin=45.0, Tref=50.0),
  'LN2': dict(rho=808.2, cp=2038.0, mu=1.635e-4, k=0.1457, Pr=2.286, beta=5.617e-3, Tin=77.0, Tref=77.0),
}

# ---------------- campaign definition ----------------
CASES = []
for Re in (500, 1000, 1500, 2300, 5000, 10000):
    CASES.append(dict(fluid='He', Re=Re, P=1e5))
    CASES.append(dict(fluid='LN2', Re=Re, P=3e5))
for P in (5e5, 18e5):                            # pressure series at Re 2300 (ITER shield loop: 18 bar)
    CASES.append(dict(fluid='He', Re=2300, P=P))
for fl, P, Re in (('LN2', 3e5, 500), ('LN2', 3e5, 2300), ('He', 1e5, 2300)):   # buoyancy sensitivity (g on)
    CASES.append(dict(fluid=fl, Re=Re, P=P, g=True))

def name(c): return f"{c['fluid']}_{int(c['P']/1e5)}bar_Re{c['Re']}" + ("_gON" if c.get('g') else "")

def sub(path, pattern, repl, count=0, must=True):
    s = open(path).read(); s2, n = re.subn(pattern, repl, s, count=count, flags=re.M)
    if must and n == 0: raise RuntimeError(f"pattern not found in {path}: {pattern}")
    open(path, 'w').write(s2)

def write(path, txt): open(path, 'w').write(txt)

HDR = lambda cls, obj: f"FoamFile {{ version 2.0; format ascii; class {cls}; object {obj}; }}\n"

def turb_fields(d, fluid, U, k_in, om_in, compressible):
    nut_dims = "[0 2 -1 0 0 0 0]" if not compressible else "[0 2 -1 0 0 0 0]"
    write(f"{d}/0/k", HDR("volScalarField", "k") + f"""dimensions [0 2 -2 0 0 0 0];
internalField uniform {k_in:.6e};
boundaryField
{{
    inlet          {{ type fixedValue; value uniform {k_in:.6e}; }}
    outlet         {{ type inletOutlet; inletValue uniform {k_in:.6e}; value uniform {k_in:.6e}; }}
    heatedWall     {{ type kqRWallFunction; value uniform {k_in:.6e}; }}
    adiabaticWalls {{ type kqRWallFunction; value uniform {k_in:.6e}; }}
}}
""")
    write(f"{d}/0/omega", HDR("volScalarField", "omega") + f"""dimensions [0 0 -1 0 0 0 0];
internalField uniform {om_in:.6e};
boundaryField
{{
    inlet          {{ type fixedValue; value uniform {om_in:.6e}; }}
    outlet         {{ type inletOutlet; inletValue uniform {om_in:.6e}; value uniform {om_in:.6e}; }}
    heatedWall     {{ type omegaWallFunction; blended true; value uniform {om_in:.6e}; }}
    adiabaticWalls {{ type omegaWallFunction; blended true; value uniform {om_in:.6e}; }}
}}
""")
    write(f"{d}/0/nut", HDR("volScalarField", "nut") + f"""dimensions {nut_dims};
internalField uniform 0;
boundaryField
{{
    inlet          {{ type calculated; value uniform 0; }}
    outlet         {{ type calculated; value uniform 0; }}
    heatedWall     {{ type nutLowReWallFunction; value uniform 0; }}
    adiabaticWalls {{ type nutLowReWallFunction; value uniform 0; }}
}}
""")
    # alphat stays 'calculated' (= rho*nut/Prt at the wall = 0 with the low-Re nut wall function),
    # so the fixedGradient wall heat flux q = k dT/dn is delivered EXACTLY. y+ is written by postProcess.
    write(f"{d}/constant/turbulenceProperties", HDR("dictionary", "turbulenceProperties") + """simulationType RAS;
RAS
{
    RASModel        kOmegaSST;
    turbulence      on;
    printCoeffs     on;
}
""")

def build(c):
    fl, Re, P = c['fluid'], c['Re'], c['P']
    pr = PROPS[fl]; d = f"{ROOT}/{name(c)}"; src = SRC[fl]
    if os.path.exists(d): shutil.rmtree(d)
    os.makedirs(d)
    for sd in ('0', 'system', 'constant'):
        shutil.copytree(f"{src}/{sd}", f"{d}/{sd}", ignore=shutil.ignore_patterns('*.bak*', 'cellToRegion', 'U.bak_original'))
    turbulent = Re >= 4000
    compressible = (fl == 'He')
    if compressible:
        shutil.copy(f"{SRC['LN2']}/system/blockMeshDict", f"{d}/system/blockMeshDict")  # graded dict (He_graded's is stale)
        rho_in = P * MW_HE / (RGAS * pr['Tin'])
        rho_ref = P * MW_HE / (RGAS * pr['Tref'])
        mdot = Re * pr['mu'] * A_CS / DH
        U = mdot / (rho_ref * A_CS)
        # thermo: mu, Pr
        sub(f"{d}/constant/thermophysicalProperties", r"mu\s+[0-9.eE+-]+;", f"mu {pr['mu']:.4e};")
        sub(f"{d}/constant/thermophysicalProperties", r"Pr\s+[0-9.eE+-]+;", f"Pr {pr['Pr']:.4f};")
        sub(f"{d}/constant/thermophysicalProperties", r"Cp\s+[0-9.eE+-]+;", f"Cp {pr['cp']:.1f};")
        # pressure fields + pRefValue
        for f in ('p', 'p_rgh'):
            sub(f"{d}/0/{f}", r"101325", f"{P:.0f}")
        sub(f"{d}/system/fvSolution", r"pRefValue\s+[0-9.eE+-]+;", f"pRefValue {P:.0f};")
        # inlet mass flow
        sub(f"{d}/0/U", r"massFlowRate\s+[0-9.eE+-]+;", f"massFlowRate {mdot:.6e};")
        sub(f"{d}/0/U", r"uniform \([0-9.eE+-]+ 0 0\)", f"uniform ({U:.6f} 0 0)")
        # wall heat flux gradient
        sub(f"{d}/0/T", r"gradient\s+uniform\s+[0-9.eE+-]+;", f"gradient uniform {Q_FLUX/pr['k']:.4f};")
        rho_for_turb = rho_ref
    else:
        rho_in = rho_ref = pr['rho']; nu = pr['mu'] / pr['rho']
        U = Re * nu / DH; mdot = pr['rho'] * U * A_CS
        sub(f"{d}/constant/transportProperties", r"nu\s+\[.*?\]\s+[0-9.eE+-]+;", f"nu [ 0 2 -1 0 0 0 0 ] {nu:.5e};")
        sub(f"{d}/constant/transportProperties", r"beta\s+\[.*?\]\s+[0-9.eE+-]+;", f"beta [ 0 0 0 -1 0 0 0 ] {pr['beta']:.4e};")
        sub(f"{d}/constant/transportProperties", r"Pr\s+\[.*?\]\s+[0-9.eE+-]+;", f"Pr [ 0 0 0 0 0 0 0 ] {pr['Pr']:.3f};")
        sub(f"{d}/0/U", r"uniform \( ?[0-9.eE+-]+ 0 0 ?\)", f"uniform ({U:.6f} 0 0)")
        sub(f"{d}/0/T", r"gradient\s+uniform\s+[0-9.eE+-]+;", f"gradient uniform {Q_FLUX/pr['k']:.4f};")
        rho_for_turb = pr['rho']
        # pressure solver: with g=0 the p_rgh field is tiny and GAMG/GaussSeidel at relTol 0.01 needed ~50
        # cycles per solve (3.4 s/it). GAMG with a DIC-smoothed cycle at relTol 0.05 is ~3x faster (2026-09-27).
        sub(f"{d}/system/fvSolution", r"    p_rgh\s*\{[^}]*\}", "    p_rgh\n    {\n        solver GAMG;\n        smoother DICGaussSeidel;\n        nPreSweeps 0;\n        nPostSweeps 2;\n        nCellsInCoarsestLevel 100;\n        tolerance 1e-8;\n        relTol 0.05;\n    }", count=1)
    # gravity: OFF for the forced-convection sweep (orientation-independent basis); ON only for the
    # mixed-convection sensitivity cases (flag g=True), reported separately with Gr/Re^2.
    gvec = "(0 -9.81 0)" if c.get('g') else "(0 0 0)"
    write(f"{d}/constant/g", HDR("uniformDimensionedVectorField", "g") + f"dimensions [0 1 -2 0 0 0 0];\nvalue {gvec};\n")
    # controlDict: write only the final time; function objects sample every 100 iterations
    sub(f"{d}/system/controlDict", r"^\s*writeInterval\s+[0-9]+;", "writeInterval   6000;", count=1)
    sub(f"{d}/system/controlDict", r"^(\s+)writeInterval\s+(1|100);", r"\1writeInterval   100;", must=False)
    sub(f"{d}/system/controlDict", r"^purgeWrite\s+0;", "purgeWrite      1;")
    if turbulent:
        I = 0.05; k_in = 1.5 * (I * U) ** 2; om_in = math.sqrt(k_in) / (0.09 ** 0.25 * 0.07 * DH)
        turb_fields(d, fl, U, k_in, om_in, compressible)
        # schemes / solvers for k, omega
        sub(f"{d}/system/fvSchemes", r"(divSchemes\s*\{)", r"\1\n    div(phi,k)      bounded Gauss limitedLinear 1;\n    div(phi,omega)  bounded Gauss limitedLinear 1;")
        with open(f"{d}/system/fvSchemes", 'a') as fs: fs.write("\nwallDist { method meshWave; }\n")
        if compressible:
            sub(f"{d}/system/fvSolution", r'"\(U\|h\)"', '"(U|h|k|omega)"')
            sub(f"{d}/system/fvSolution", r"equations\s*\{\s*U 0.3; h 0.7;\s*\}", "equations { U 0.3; h 0.7; k 0.7; omega 0.7; }")
            sub(f"{d}/system/fvSolution", r"residualControl \{ p_rgh 1e-6; U 1e-6; h 1e-6; \}", "residualControl { p_rgh 1e-6; U 1e-6; h 1e-6; k 1e-5; omega 1e-5; }")
        else:
            sub(f"{d}/system/fvSolution", r'"\(U\|T\)"', '"(U|T|k|omega)"')
            sub(f"{d}/system/fvSolution", r"equations \{ U 0.2; T 0.2; \}", "equations { U 0.2; T 0.2; k 0.5; omega 0.5; }")
            sub(f"{d}/system/fvSolution", r"T 1e-7;\s*\}", "T 1e-7;\n        k 1e-6;\n        omega 1e-6;\n    }")
        sub(f"{d}/system/controlDict", r"^endTime\s+6000;", "endTime         8000;")
    # metricConstants (used by postProcess_metrics.sh)
    mc = f"{d}/system/metricConstants"
    sub(mc, r"^CASE_NAME=.*", f"CASE_NAME={name(c)}")
    sub(mc, r"^FLUID_NAME=.*", f'FLUID_NAME="{fl}_{int(pr["Tref"])}K_{int(P/1e5)}bar"')
    sub(mc, r"^k_W_mK=.*", f"k_W_mK={pr['k']}")
    sub(mc, r"^mu_Pa_s=.*", f"mu_Pa_s={pr['mu']}")
    sub(mc, r"^nu_m2_s=.*", f"nu_m2_s={pr['mu']/rho_ref:.5e}")
    sub(mc, r"^Pr=.*", f"Pr={pr['Pr']}")
    sub(mc, r"^cp_J_kgK=.*", f"cp_J_kgK={pr['cp']}")
    sub(mc, r"^rho_kg_m3=.*", f"rho_kg_m3={rho_ref:.5g}")
    if 'beta' in pr: sub(mc, r"^beta_1_K=.*", f"beta_1_K={pr['beta']}")
    with open(mc, 'a') as f:
        f.write(f"GRAVITY={1 if c.get('g') else 0}\n")
        f.write(f"Re_target={Re}\nP_Pa={P:.0f}\nTURBULENT={1 if turbulent else 0}\nUmean_nominal={U:.6f}\nmdot_nominal={mdot:.6e}\n")
    # mixing-cup outlet temperature must be mass-flux weighted WITHOUT the extra area factor:
    # OpenFOAM's weightedAreaAverage = sum(w*A*T)/sum(w*A); with w=phi (already an area-integrated flux)
    # this double-weights large core faces and biased T_out low on graded meshes (found 2026-09-27).
    sub(f"{d}/system/postProcess_metrics.sh", r"operation weightedAreaAverage; weightField phi;", "operation weightedAverage; weightField phi;", must=False)
    # clean stale outputs
    for junk in ('postProcessing', 'dynamicCode'):
        shutil.rmtree(f"{d}/{junk}", ignore_errors=True)
    for f in os.listdir(d):
        if f.startswith('log.') or f.endswith('.foam') or f in ('metrics.csv', 'Nu_f_report.txt', 'GATE_CHECK.txt', 'egm_lax.csv'):
            os.remove(f"{d}/{f}")
    for t in os.listdir(d):
        if re.fullmatch(r"[0-9]+", t) and t != '0': shutil.rmtree(f"{d}/{t}")
    open(f"{d}/{name(c)}.foam", 'w').close()
    return dict(case=name(c), fluid=fl, Re=Re, P_Pa=P, U_m_s=U, mdot_kg_s=mdot, rho_ref=rho_ref,
                turbulent=turbulent, q_wall_W_m2=Q_FLUX, gradT_wall=Q_FLUX / pr['k'])

if __name__ == '__main__':
    os.makedirs(ROOT, exist_ok=True)
    only = sys.argv[1:]  # optional subset of case names
    manifest = []
    for c in CASES:
        if only and name(c) not in only: continue
        manifest.append(build(c)); print("built", name(c), manifest[-1])
    json.dump(manifest, open(f"{ROOT}/manifest_{'sub' if only else 'all'}.json", 'w'), indent=1)
    with open(f"{ROOT}/queue_laminar.txt", 'w') as f:
        for m in manifest:
            if not m['turbulent']: f.write(f"{ROOT}/{m['case']}\n")
    with open(f"{ROOT}/queue_turbulent.txt", 'w') as f:
        for m in manifest:
            if m['turbulent']: f.write(f"{ROOT}/{m['case']}\n")
    print("queues written")
