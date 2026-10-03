# Cryostat CHT Gate-Check Suite

A defined, automated pass/fail gate suite for the OpenFOAM
`chtMultiRegionSimpleFoam` cryostat passive-heat-load model. It replaces the
ad-hoc checks (residuals, energy balance, T bounds, view-factor row sums) with a
versioned suite of gates, each with an explicit threshold and an analytical or
conservation basis, producing a console report plus machine-readable JSON/JUnit.

A case **passes the suite iff it has zero `FAIL`s.** `WARN`s are advisory
(review them); `SKIP`s mean a required artifact was absent.

Pure Python 3 standard library — no OpenFOAM install, no numpy/scipy/pyyaml
needed. The OpenFOAM field reader is reused from the project's own
`extract_heat_loads.py`, so it parses the same ascii/binary fields you already
trust.

---

## Quick start

```bash
# 1. validate the suite itself (synthetic case, no OpenFOAM required)
python3 tests/selftest.py

# 2. gate a real case (console report)
python3 -m gatecheck.runner config/stage1_shield_77K.json \
        --case /path/to/stage1_shield_77K_v2

# 3. machine-readable outputs for CI / the dissertation appendix
python3 -m gatecheck.runner config/stage2_4K_from77K.json \
        --case /path/to/stage2_4K_from77K_v2 \
        --json reports/stage2.json --junit reports/stage2.xml
```

Exit code is `1` if any gate `FAIL`s, `0` otherwise — so it drops straight into
a `Allrun` tail or CI step.

If `case_dir` is set in the JSON (or you pass `--case`), that wins; otherwise the
case is assumed to be the config file's own folder. `log_file` / `checkmesh_log`
are resolved relative to the case dir (or its parent).

---

## Layout

```
gate_check_suite/
  gatecheck/
    ofparse.py     OpenFOAM mesh/field reader (ascii+binary), geometry, areas
    logparse.py    SIMPLE residual history + checkMesh parser
    materials.py   cryo k(T) conductivity integrals  (EDIT before publishing)
    analytical.py  radiation, Kn, Ra, Pe, free-molecular references
    gates.py       the gate definitions (Tiers 0-5)
    runner.py      case loader + report (console / JSON / JUnit)
  config/
    stage1_shield_77K.json   stage1_shield_50K.json
    stage2_4K_from77K.json   stage2_4K_from50K.json
  tests/
    selftest.py    builds a synthetic case, asserts gates fire correctly
    test_gates.py  pytest wrapper (+ optional real-case gating via GATE_CONFIG)
  requirements.txt
```

---

## The gates

### Tier 0 — Numerical health
| ID | Gate | Criterion | Basis |
|----|------|-----------|-------|
| G0.1 | Residual convergence | every watched field's final SIMPLE initial residual `< residual_max` (1e-5) | converged steady state |
| G0.2 | Field bounds | all region T within `[T_cold-margin, T_warm+margin]`, finite, `rho>0` | no negative-T / NaN blow-up |
| G0.3 | Steady state | max patch-load drift between last two time dirs `< steady_rel` (1%) | iteration-independent result |

### Tier 1 — Conservation
| ID | Gate | Criterion | Basis |
|----|------|-----------|-------|
| G1.1 | Global energy balance | `|Σ_patches (Q_diff+Q_rad)|` < 1% of largest patch (or `energy_balance_abs_W`) | steady fluid region has no volumetric source |
| G1.2 | Radiation closure | `|Σ_patches Q_rad|` < 2% of largest | grey-diffuse enclosure exchange is internal → nets to zero. **This is the gate that catches the G=0 coax sink** (a one-sided absorber shows up as a non-zero net). |
| G1.3 | Interface continuity | `|q_fluid+q_solid|/q` < 2% at each coax CHT interface | conservative coupling → equal & opposite flux |

### Tier 2 — Radiation model validity
| ID | Gate | Criterion | Basis |
|----|------|-----------|-------|
| G2.1 | Emissivity audit | every radiating patch has `0<ε≤1` assigned | catches unassigned-emissivity / G=0 absorber |
| G2.2 | View-factor row sums | `max|Σ_j F_ij − 1|` < 1e-3 | closed enclosure |
| G2.3 | Analytical radiation cross-check | CFD net radiative load on the cold patch within 30% of the grey two-surface enclosure formula | sanity bound (geometry simplified ⇒ loose) |

The two-surface reference is
`Q = σ(T_h⁴−T_c⁴) / [ (1−ε_h)/(ε_h A_h) + 1/(A_h F) + (1−ε_c)/(ε_c A_c) ]`,
with areas taken from the actual mesh patches unless overridden.

### Tier 3 — Analytical conduction (the core physics gate)
| ID | Gate | Criterion | Basis |
|----|------|-----------|-------|
| G3.1 | Coax conduction vs conductivity integral | per coax, CFD axial load within 15% of `Q=(A/L)∫_{T_c}^{T_h} k(T)dT` | 1-D Fourier conduction integral, no intermediate anchor |
| G3.2 | Total cold-side load vs lumped network | total cold-boundary load within 25% of (conduction integral + radiation) | independent resistance-network estimate |

`∫k(T)dT` uses temperature-dependent conductivity — **not** `kΔT`. See the
material warning below.

### Tier 4 — Regime guards (these catch the bugs you already hit)
| ID | Gate | Criterion | Basis |
|----|------|-----------|-------|
| G4.1 | Pressure sanity | `p` within `expected_pressure_Pa × [1/factor, factor]` | **directly catches a stray 101325 Pa** |
| G4.2 | Density sanity | `rho ≤ rho_max_kgm3` (1e-5) | `rho=pM/RT`; dense gas ⇒ wrong pressure |
| G4.3 | Rayleigh guard | `Ra < rayleigh_max` (1e3) | `Ra>~1e3` ⇒ buoyant convection ⇒ steady laminar solve ill-posed (the 1-atm instability) |
| G4.4 | Knudsen / gas-conduction consistency | continuum gas conduction `< gas_conduction_frac` (1%) of stage load; `WARN` if `Kn>1` and it isn't negligible | `Kn≫1` ⇒ free-molecular (`q∝p`), not Fourier; gas should be thermally inert |

### Tier 5 — Provenance & boundary-condition audit
| ID | Gate | Criterion | Basis |
|----|------|-----------|-------|
| G5.1 | BC audit | each T BC type/value matches the `expected_T_bc` spec | **catches mislabeled / wrong fixedValue (e.g. 300 K on the cold end)** |
| G5.2 | controlDict patch-integral audit | `patchInt_<X>` reports patch `<X>` | catches the coldPlate-using-shield-name bug |
| G5.3 | Mesh quality | checkMesh non-orthogonality < 70, skewness < 4 | standard FV quality |
| G5.4 | Provenance record | records OF version, solver, time, iters | reproducibility (always informational) |

---

## Configuring a case

Each stage is one JSON config (see `config/`). Key blocks:

- `fluid_region`, `solid_regions` — region names (`domain1`, `coax_L1..L4`).
- `temperatures` — `T_cold`, `T_warm` for this stage.
- `expected_T_bc` — the BC spec table G5.1 audits against.
- `radiating_patches` — patches that must carry an emissivity.
- `radiation_check` — hot/cold patch + ε + T for the G2.3 cross-check (areas
  auto-filled from the mesh).
- `coax` — per cable, `length_m` and a list of `segments`
  (`material`, `area_m2`) for the G3.1 conduction integral.
- `regime` — expected pressure, μ, Cp, Pr, molWeight, gap size, Ra limit.
- `thresholds` — every numeric tolerance, all in one place and versioned.

To tighten/loosen a gate, edit `thresholds` — never the code.

---

## ⚠ Before you publish: replace the material data

`materials.py` ships with **rough literature `k(T)` tables flagged
`VERIFY=True`** so the suite runs out of the box. Any gate that uses them
(`G3.1`, `G3.2`) is reported as `WARN`, not `PASS`, until you fix this.

For publishable numbers, for each conductor:
1. Get `k(T)` from **NIST Cryogenic Material Properties**
   (cryogenics.nist.gov) or your manufacturer datasheet.
2. Replace the table in `materials._TABLES` (or pass `{"pts": [...]}` /
   `{"nist": [a,b,...]}` directly in the config) and set `VERIFY=False`.
3. Set the real per-conductor cross-sectional `area_m2` and `length_m` in the
   config (the shipped coax geometry is a **placeholder**).

The conductivity-integral method itself (`Q=(A/L)∫k dT`) is correct as written;
only the property data and cross-sections are yours to supply.

---

## Notes / conventions

- Sign: OpenFOAM positive = heat **leaving** the fluid through the wall (same as
  `extract_heat_loads.py`).
- `wallHeatFlux` is the diffusive (conduction/convection) wall flux; `qr` is the
  radiative flux, stored separately. Total wall energy = `wallHeatFlux + qr`;
  they are **not** subtracted.
- Gates never raise on missing files — they `SKIP` with a reason, so one absent
  artifact can't fail the suite.
- View-factor reciprocity (`A_iF_ij=A_jF_ji`) is available once an ascii `F`
  matrix is present in `constant/<region>/F`; otherwise G2.2 `SKIP`s.
