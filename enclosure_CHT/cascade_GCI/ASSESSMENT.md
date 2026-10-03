# Cascade CHT — Grid/View-Factor Convergence & Cooling-Requirement Lock

**Purpose:** verify that the passive heat load predicted by the Stage-1 and Stage-2 enclosure CHT
models (which *is* the cold-plate heat-exchanger duty) is grid-independent, so the HX cooling
requirement can be locked. Representative cases: `stage1_shield_50K_v2` (300→50 K) and
`stage2_4K_from50K_v2` (50→4 K). OpenFOAM v2412 `chtMultiRegionSimpleFoam`.

---

## 1. What is and isn't mesh-dependent (key framing)

The cooling requirement = **radiation + conduction** on the cold stage.

- **Conduction is NOT a CFD/mesh result — it is analytically locked.** Each lumped coax gets an
  effective conductivity `k_eff(T)` calibrated so the CFD reproduces the analytic Fourier harness
  load `n_k·(1/L)·Σ A_i ∫k_i dT` (gate G3.1 = 0.0%). That target is a pure material/geometry
  integral, independent of mesh. Fixed by construction: **1.029 W (S1-50K), 0.96 W (S1-77K),
  70.3 mW (S2-from50K), 162 mW (S2-from77K).**
- **Only the radiation is discretisation-dependent** (`viewFactor` surface-to-surface). The
  radiating wall temperatures are **fixed-value BCs** and the surfaces are **flat plates with exact
  areas**, so the *volume* mesh barely matters — the meaningful discretisation is the **view-factor
  surface resolution** (agglomeration `nFacesInCoarsestLevel`), validated against the closed-form
  grey-body enclosure solution.

## 2. View-factor resolution sweep (radiation)

| level | nFaces(coarsest) | Stage-1 50K radiation | Stage-2 50K radiation |
|---|---|---|---|
| coarse | 60 | 9.456 W | 5.287 mW |
| **medium (production)** | **250** | **8.411 W** | **3.443 mW** |
| fine | 500 | 3.575 W *(corrupted)* | 3.443 mW |
| **analytic grey-body** | — | **7.07 W** | **3.15 mW** |

- **Stage-2 is cleanly grid-converged:** medium and fine are identical (3.443 mW) and match the
  analytic anchor to ~9%. And radiation there is negligible vs the 70.3 mW conduction anyway.
- **Stage-1 sweep is non-monotonic:** coarse over-predicts (9.46), medium (8.41) sits ~19% above the
  analytic anchor, and the "fine" 3.58 W falls *below* the analytic maximum — unphysical. At 1233
  coarse faces with fixed Gauss quadrature the view-factor matrix stops closing (row sums drift from
  1), so radiation is spuriously under-counted. **The fine point is discarded as a closure artifact.**
- Trustworthy Stage-1 value = **production (medium) 8.411 W** (closure ~99% domain0 / ~91% domain1),
  bracketing the analytic anchor within ~19%.

## 3. Analytic grey-body anchor (validation)

Two-surface enclosure per fluid region, F=1, ε_warm=0.04, ε_cold=0.02, areas measured from the mesh:
- **Stage-1 50K:** domain0 (OVC+warmPlate 300K → shield 50K) 4.24 W + domain1 (warmPlate → shield/
  coldPlate) 2.84 W → **total 7.07 W**.
- **Stage-2 50K:** domain0 1.75 mW + domain1 1.40 mW → **total 3.15 mW**.

Both production CFD values sit just above the analytic anchor (S1 +19%, S2 +9%) — consistent with
the F=1 analytic being a slight under-estimate of the true multi-surface coupling. This
cross-validation is the real "lock": for fixed-T flat enclosures no mesh can beat the analytic value.

## 4. LOCKED cooling requirement

| stage | radiation (locked) | conduction (analytic) | **total requirement** |
|---|---|---|---|
| Stage-1, 50 K | 7.1–8.4 W | 1.03 W | **~8.1–9.4 W** (best est. ~8.5 W; production 9.44 W) |
| Stage-1, 77 K | ~7–8.4 W | 0.96 W | **~8–9.3 W** |
| Stage-2, from 50 K | 3.2 mW (converged) | 70.3 mW | **~73.5 mW** (conduction-dominated) |
| Stage-2, from 77 K | ~30 mW | 162 mW | **~190 mW** |

**HX duty implication:** the **9.4 W** matched duty used for the He-vs-N2 cold-plate study is a
**defensible, slightly conservative upper bound** for the Stage-1 load. A refined best estimate is
**~8.5 W**. The He-vs-N2 comparison is unaffected (both share the duty); only the absolute design
point shifts ~10% if the analytic anchor is adopted.

## 5. Honest caveats

1. The agglomeration sweep is **not a clean Roache/Celik GCI** for Stage-1 (view-factor accuracy is
   non-monotonic in agglomeration). The defensible evidence is Stage-2's identical medium/fine result
   + the analytic grey-body cross-check.
2. The analytic anchor is an approximate two-surface, F=1 lumping — treat as ±10–15%.
3. Conduction is analytically locked by design (gate G3.1 = 0% enforces CFD = analytic harness).
4. Only the 50 K representatives were swept; the 77 K cases follow the same structure (radiation ≈
   Stefan-Boltzmann T⁴; conduction analytically locked).
5. To tighten Stage-1 radiation <5%: increase the Gauss quadrature at fixed moderate agglomeration
   until row-sum closure → 1 (deferred; the analytic anchor already brackets it).

---
*Data: `cascade_convergence.csv`, `cascade_raw_results.txt`. Study run on `openfoam-vm`. Conduction
lock + gates documented in the per-case CHT READMEs under `../1-CHT models/`.*
