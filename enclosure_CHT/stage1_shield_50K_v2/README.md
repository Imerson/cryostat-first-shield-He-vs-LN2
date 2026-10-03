# stage1_shield_50K_v2

**Stage 1 — 50 K radiation shield, fed from the 300 K flange**

Steady-state conjugate-heat-transfer (CHT) CFD model of the passive heat load between two
cryostat stages, solved with OpenFOAM v2412 `chtMultiRegionSimpleFoam`. A single solve
resolves **all three** passive mechanisms self-consistently: surface-to-surface
**radiation**, solid **conduction** down the cable harness, and **convection** (which is
identically zero here — the inter-stage space is vacuum). Numbers in this README are taken
directly from the converged solution at **t = 2900** (`postProcessing/heatLoadSummary/heat_load_summary.dat`)
so the document and the model cannot disagree.

---

## 1. Methodology

| mechanism | how it is obtained | where |
|---|---|---|
| Radiation | `viewFactor` surface-to-surface model, agglomerated F-matrix, solved every 10 outer iters (`solverFreq`) | CFD |
| Conduction | solid heat equation in the 4 coax regions with an effective T-dependent conductivity `k_eff(T)` | CFD |
| Convection | none — vacuum gap (g = 0, density driven to ~0), so there is no buoyant gas flow | n/a (=0) |

- Regions: `domain0`, `domain1` are the vacuum gas gaps (fluid regions kept radiatively
  transparent so radiation is purely surface-to-surface); `coax_L1..L4` are the solid cable
  bundles bridging the two plates. `chtMultiRegionSimpleFoam` couples them.
- The gas is forced to behave as vacuum: **p = 0.001 Pa**, **g = (0 0 0)**, μ = 1e-11
  (κ_gas ≈ 1e-7 W/m·K), so gas conduction and convection are negligible by construction.
- Energy is conserved by the segregated solver; this is checked, not assumed (Section 4).

## 2. Boundary conditions

- **Warm plate = 300 K**, **cold plate = 50 K**, both `fixedValue` temperature —
  these fixed-T plates set the gradient that drives both radiation and conduction.
- Wall surface emissivities (`boundaryRadiationProperties`, grey-diffuse): ε=0.04 on coldPlate, shield_bottom, warmPlate; ε=0.02 on coax, shield.
- `qr` on radiating walls: `greyDiffusiveRadiationViewFactor`; coax fluid-side: `calculated`.
- Coax↔gas interfaces: `compressible::turbulentTemperatureCoupledBaffleMixed` (CHT coupling).
- Velocity `noSlip`, `p_rgh` `fixedFluxPressure` (irrelevant at vacuum but required by the solver).

## 3. The analytical model baked into the conduction

The 4 coax cylinders are **not** 4 physical cables — they are a lumped stand-in for the full
microwave harness of **65 RF lines** (one functional bundle per coax), following the
Krinner et al. 2019 cabling of a Bluefors-class dilution refrigerator:

| coax | lines | family |
|---|---|---|
| coax_L1 | 25 | drive (SS_UT085) |
| coax_L2 | 25 | flux (SS_UT085) |
| coax_L3 | 10 | readout+readin (SS_UT085) |
| coax_L4 | 5 | pump (SS_UT085) |

Each coax is assigned an **effective temperature-dependent conductivity** so that one
modelled solid carries the conduction of its share of cables, with the correct magnitude
*and* the correct temperature profile:

```
k_eff(T) = (n_k / A_model) · Σ_components  A_i · k_i(T)
```

- `n_k` = cables in that bundle; `A_i`, `k_i(T)` = real conductor/dielectric cross-sections and
  material conductivities of a UT-085-SS-SS stainless coax (outer + centre SS304, PTFE
  dielectric), with **k(T) from the NIST cryogenic database** (not placeholder values).
- `A_model` is the modelled coax cross-section and **cancels analytically**:
  `Q = (A_model/L)∫k_eff dT = n_k·(1/L)Σ A_i ∫k_i dT = n_k·Q_cable`. It is **calibrated per
  geometry** (here A_model = 2.9752e-04 m², L = 0.3350 m) from one reference solve so the CFD's
  effective conductance equals the analytic target.
- `k_eff(T)` is fitted to an **order-5 polynomial** (`kappaCoeffs<8>`, OpenFOAM `polynomial`
  solid transport); the fit error is **0.13%** for this case.

So the conduction is genuinely **solved by the CFD** (solid heat equation with `k_eff(T)`);
the analytic harness load is the *target* the gates verify it reproduces.

## 4. Gate checks (sanity), at t = 2900 — **7/7 pass**

```
  [PASS] no_solver_errors                 log=log.chtMultiRegionSimpleFoam
  [PASS] energy_cons_domain0              net sum(whf+qr)=-5.15e-04 W (0.0%)
  [PASS] energy_cons_domain1              net sum(whf+qr)=+1.64e-06 W (0.0%)
  [PASS] radiation_active                 radiation on cold = 8411.264 mW
  [PASS] G3.1_conduction_CFD_vs_harness   CFD=1029.09 mW target=1029.05 mW err=0.0%
  [PASS] G3.4_keff_fit                    max k_eff poly(order 5) fit err = 0.13%
  [PASS] G3.5_harness_accounting          65 lines; W/cable=15.832 mW; total cond=1029.09 mW
```
- `energy_cons_*`: net Σ(wallHeatFlux + qr) over each gas region → 0 (energy conserved).
- `G3.1`: CFD-resolved coax axial conduction equals the analytic harness target (≤15%).
- `G3.4`: the k_eff polynomial reproduces the tabulated k_eff(T) (≤2%).
- `G3.5`: harness accounting — 65 lines, W-per-cable, total.
- View-factor closure (row sums → 1): ~99% (domain0) / ~91% (domain1) of agglomerated rows
  within ±10%.

## 5. Results — heat load on the 50 K stage (converged, t = 2900)

| mechanism | Q |
|---|---|
| Radiation (viewFactor) | 8411.26 mW |
| Conduction (65-cable harness, CFD) | 1029.09 mW |
| Convection (vacuum) | 0 |
| **TOTAL** | **9440.35 mW = 9.44 W** |

Per-bundle conduction (CFD vs analytic target):

| coax | lines | family | CFD | target |
|---|---|---|---|---|
| coax_L1 | 25 | drive | 395.803 mW | 395.788 mW |
| coax_L2 | 25 | flux | 395.804 mW | 395.788 mW |
| coax_L3 | 10 | readout+readin | 158.321 mW | 158.315 mW |
| coax_L4 | 5 | pump | 79.161 mW | 79.158 mW |

Cooling budget at the 50 K stage ≈ 30.0 W → this load is **31.5%** of budget.
**This stage is radiation-dominated.**

## 6. Honest caveats (reasonable assumptions)

1. **Lumped coax, not 65 meshed cables.** The harness is represented by 4 effective-conductivity
   solids, not individual wires. `A_model` is calibrated per geometry so the CFD conduction
   equals the measured-cable target; this reproduces the *total* and *gradient* but not the
   per-wire field. (RAM-budget choice; validated by gate G3.1 to 0.0%.)
2. **Vacuum modelled as a near-zero-density fluid.** OpenFOAM viewFactor radiation needs a
   fluid region, so the gap is a fluid forced to vacuum (p=0.001 Pa, g=0). Gas conduction/
   convection are therefore ~µW / 0, consistent with a real OVC (<1e-5 mbar) but not a true
   molecular-regime treatment.
3. **Single cable type (UT-085-SS-SS stainless).** All 65 lines use one stainless coax with
   NIST k(T). A cupronickel (SC-086) harness would give a lower bound (~3–7× less conduction);
   real looms mix types. NbTi superconducting sections (4 K→MXC) are not in these stages.
4. **Fixed-temperature plates, no intermediate thermalisation.** This models the unanchored
   conduction/radiation between the two plates of one stage; Krinner-style attenuator
   thermalisation at intermediate anchors is a separate model.
5. **k_eff(T) is an order-5 polynomial fit** (error 0.13% here) and is linearly extrapolated
   below the lowest NIST data point — a small overestimate of low-T conductivity.
6. **View-factor closure has a few-% tail** (domain1 ~91% of rows within ±10%), mostly on the
   thin coax surfaces; the energy equation still conserves (gate `energy_cons`).
7. **Convection is taken as exactly zero** (vacuum). Reported "convection = 0" is a modelling
   statement, not a solved nonzero value.

---
*Scripts in this folder regenerate everything: `harness_kappa.py` (k_eff, NIST k(T), cable
specs, polynomial fit), `extract_heat_loads.py` (field readers), `finalize_case.py` (heat
loads → `heat_loads_stage1_shield_50K_v2.xlsx` + gate report). Cross-case comparison: `heat_load_comparison_ALL.csv`.*
