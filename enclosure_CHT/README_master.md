# Cryostat CHT Thermal Model Suite — Master README

This directory contains six independent OpenFOAM `chtMultiRegionSimpleFoam` cases ("v2"),
each modelling steady-state conjugate heat transfer (CHT) across one stage of a
dilution-refrigerator-style cryostat, from the room-temperature vacuum can down to the
mixing-chamber (10 mK) stage. This document ties the six per-stage models together,
gives a cascading Watt-budget comparison, summarises the shared model architecture and
v1→v2 bug-fix history, and lists suite-wide caveats that apply to **every** stage.

**Read this file first**, then the per-stage README in each subdirectory for the full
detail (geometry, dictionaries, material properties, BCs, solver settings, per-patch
results) behind the numbers quoted here.

---

## 1. Cryostat Staging Architecture

The six cases model the following cascade (two alternative paths are provided for the
first transition, depending on whether the shield is precooled to 50 K or 77 K):

```
                         300 K  (room temperature / OVC)
                           |
            -------------------------------
            |                              |
     stage1_shield_50K_v2          stage1_shield_77K_v2
            |                              |
          50 K                           77 K
            |                              |
   stage2_4K_from50K_v2            stage2_4K_from77K_v2
            |                              |
            -------------------------------
                           |
                          4 K
                           |
                  stage3_100mK_v2
                           |
                        100 mK
                           |
                  stage4_10mK_v2
                           |
                         10 mK   (mixing chamber / "chip")
```

- **stage1_shield_50K_v2 / stage1_shield_77K_v2** — outer 300 K → 50 K or 77 K
  radiation-shield gap. Two alternative shield pre-cool strategies (e.g. pulse-tube
  50 K stage vs. an LN2/77 K-precooled shield); they are NOT meant to be summed, they
  are alternatives.
- **stage2_4K_from50K_v2 / stage2_4K_from77K_v2** — 50 K→4 K or 77 K→4 K gap, continuing
  from whichever stage1 variant is used.
- **stage3_100mK_v2** — 4 K → 100 mK (still → cold plate) gap.
- **stage4_10mK_v2** — 100 mK → 10 mK (mixing-chamber) gap, the final stage. This is the
  only case with an extra **"chip"** region (a passive 10 mm conduction block — see
  §6 and §9).

### Directory map

| Case | README |
|---|---|
| `stage1_shield_50K_v2/` | [README.md](stage1_shield_50K_v2/README.md) |
| `stage1_shield_77K_v2/` | [README.md](stage1_shield_77K_v2/README.md) |
| `stage2_4K_from50K_v2/` | [README.md](stage2_4K_from50K_v2/README.md) |
| `stage2_4K_from77K_v2/` | [README.md](stage2_4K_from77K_v2/README.md) |
| `stage3_100mK_v2/` | [README.md](stage3_100mK_v2/README.md) |
| `stage4_10mK_v2/` | [README.md](stage4_10mK_v2/README.md) |

---

## 2. Common Model Architecture

Every case shares the same template geometry and `regionProperties` pattern:

- **domain0** — the *outer* gap, between the outer vacuum-can wall ("OVC") and the
  outer face of the radiation shield ("shield_slave").
- **domain1** — the *inner* gap, between the warm plate ("warmPlate") and the cold
  plate/shield of that stage ("coldPlate" / "shield" / "shield_bottom").
- **coax_L1 … coax_L4** — four *lumped* coaxial signal-cable bundles running axially
  through domain1, each CHT-coupled to both the warm and cold plates.
  **Each `coax_L*` represents 6 of the original 24 physical coax cables**
  (24 → 4 lumping, applied uniformly across all six stages to cut mesh size). Divide
  any `coax_L*` heat-flow value by 6 to get a per-physical-cable estimate.
- **chip** (stage4 only) — a small solid block at the coldest end, see §6/§9.

In **stage1** (50 K and 77 K cases), domain0/domain1 are **fluid** regions: a
near-vacuum helium gas (`heRhoThermo`/perfectGas) with viscosity reduced to
`mu = 1e-11 Pa·s` (Fix 1) so that convection is suppressed and the gas behaves as a
near-stagnant conduction + radiation medium — physically appropriate for an evacuated
gap.

In **stage2/3/4**, `regionProperties` lists domain0/domain1 as **solid** regions
(`fluid ()`, `solid (domain0 domain1 coax_L1-4 [chip])`). Physically this represents the
same evacuated gaps, now approximated as **conduction-only solid fillers** (no
momentum/pressure equations are solved) — a reasonable simplification given that gas
convection/conduction becomes utterly negligible below ~4 K. **Caveat:** the
`thermophysicalProperties` files that would specify domain0/domain1's conductivity in
this approximation could not be located in the synced copies of stage2/3/4 (see §8) —
their numeric values are therefore unverified.

CHT coupling between coax cables and domain1 (and, in stage2/3/4, between the
"solid" domain0/domain1 and coax) uses
`compressible::turbulentTemperatureCoupledBaffleMixed` with `kappaMethod
fluidThermo`/`solidThermo` as appropriate — i.e. continuity of temperature and heat
flux is enforced across region interfaces.

**Radiation status by stage:**

| Stage | Radiation model | Notes |
|---|---|---|
| stage1 (50 K, 77 K) | `viewFactor`, 1 band, grey-diffuse | Confirmed ON in both domain0/domain1, emissivities 0.02 (shield/shield_slave/coax) and 0.04 (plates/shield_bottom). |
| stage2 (from50K, from77K) | nominally `fvDOM`, "on" | But `absorptivity = emissivity = 0` placeholders ⇒ `qr ≈ 0` everywhere — **effectively inert**. |
| stage3 (100 mK) | none / off (Fix 5) | No per-region `radiationProperties` found; only an inert top-level placeholder. T⁴ → 0 below 4 K makes this moot regardless. |
| stage4 (10 mK) | none / off (Fix 5) | Same as stage3; T⁴ ~ 1e-8, radiation is astronomically negligible. |

All six cases run `chtMultiRegionSimpleFoam` (SIMPLE algorithm), `startTime=0` →
`endTime=2000` (2000 pseudo-iterations, `deltaT=1`, `writeInterval=50`,
`purgeWrite=2` — only `1950/` and `2000/` remain on disk).

---

## 3. Cascading Heat-Load Table (Final, Time = 2000)

**Source convention used for ALL six stages:** `postProcessing/<region>/<functionObjectName>/0/surfaceFieldValue_0.dat`
(the **`_0`-suffixed** file), last row (Time = 2000). This convention was validated for
`stage1_shield_50K_v2` against an independent synced console log
(`log.chtMultiRegionSimpleFoam_cp`, the final 2026-05-30 queue run), which printed
*identical* numbers. The other five stages have **no** synced console log, so their
`_0.dat` values are taken on the strength of that one cross-check plus each agent's
internal face-count/magnitude sanity checks — see each stage's README §9 for specific
caveats. Sign convention: **positive = heat flowing INTO domain1 across that patch from
the warm side; negative = heat flowing OUT of domain1 into the cold side.**

| Quantity (W) | stage1_50K (300→50 K) | stage1_77K (300→77 K) | stage2_from50K (50→4 K) | stage2_from77K (77→4 K) | stage3 (4 K→100 mK) | stage4 (100 mK→10 mK) |
|---|---:|---:|---:|---:|---:|---:|
| domain1 warm-side inflow (warmPlate) | +4.849e-1 | +2.512 | — | — | +7.590e-4 | +1.125e-5 |
| domain1 "OVC"-labelled inflow* | +4.814e-1 | — | +3.931e-2 | +6.238e-2 | +9.036e-4 † | +1.379e-5 |
| domain1 → shield (cold) | −4.739 | −2.330 | −1.572e-2 | −2.494e-2 | −7.786e-4 | −1.104e-5 |
| domain1 → coldPlate (cold) | −1.636e-1 | −1.973 | −5.19e-4 ‡ | −8.233e-4 | −4.413e-5 | −4.544e-7 |
| domain1 → shield_bottom (cold) | n/a | −1.576e-1 | n/a | n/a | −1.699e-6 | −4.623e-8 |
| domain1 ↔ coax_L1-4 (each, sum of 4) | not captured | +5.7e-6 each (negl.) | not captured | −1.063e-3 each (Σ −4.252e-3) | +1.637e-5 each (Σ +6.546e-5) | +7.908e-8 each (Σ +3.163e-7) |
| domain0 (OVC ↔ shield_slave) | **not instrumented in any stage** | | | | | |
| chip | n/a | n/a | n/a | n/a | n/a | no postProcessing — passive conductor only |
| **Net imbalance (Σ in − Σ \|out\|)** | **−3.94 W** (~810% of inflow) | **−1.95 W** (~78%) | **+2.4e-2** (~61%) | **+3.24e-2** (~52%) | **~4e-9** (closes) | **~3.6e-8** (closes) |

\* For stage1_50K, "OVC" and "warmPlate" are two *separate* domain1 function objects
that both report similar but non-identical inflow values — see that stage's README §9
for the naming-mismatch investigation. For stage2/3/4, the "OVC"-labelled domain1
function object is the best-available proxy for warm-side inflow where a distinctly
named `warmPlate` integral wasn't found.
† For stage3, `patchInt_domain1_OVC_WHF` (+9.04e-4 W) and `warmPlate` (+7.59e-4 W) are
both reported but were found to be **inconsistent / partially duplicated** dict
entries — the `warmPlate` row is the one that participates in the (near-perfect)
8-patch energy balance and is the recommended figure.
‡ Face-count for stage2_from50K's `coldPlate` entry did not match the live mesh —
treat as indicative only.

**Per-physical-cable conduction estimates** (lumped value ÷ 6):

| Stage | coax_L* contribution | per physical cable |
|---|---:|---:|
| stage1_77K | +5.7e-6 W (domain1-side, negligible) | ~9.5e-7 W |
| stage2_from77K | −1.063e-3 W (domain1-side) | ~−1.77e-4 W |
| stage3 | +6.467e-5 W (warm/4K end) | ~1.08e-5 W |
| stage4 | +1.024e-7 W (warm/100mK end) | ~1.7e-8 W |

### Headline trend

Reading down the "warm-side inflow" row, the heat load drops by roughly
**2–3 orders of magnitude at each successive stage transition**
(O(1 W) at 300 K→50/77 K → O(0.01–0.1 W) at 50/77 K→4 K → O(1e-4 W) at 4 K→100 mK →
O(1e-5 W) at 100 mK→10 mK). This is qualitatively exactly what a multi-stage cryostat
is *for*, and is the most defensible, citable conclusion from this model suite as a
whole. **Do not** read too much into the absolute numbers or into the
stage1_77K > stage1_50K inversion (2.51 W vs 0.48 W, despite 77 K giving a *smaller*
ΔT than 50 K) — given the documented postProcessing naming/duplication issues in every
stage (§5), this could easily be a labelling artefact rather than real physics, and
needs independent re-verification before being cited.

---

## 4. Comparison to Literature Heat Budgets

Krinner et al. (2019), reporting on a Bluefors XLD400 dilution refrigerator, give
**total** stage heat budgets of roughly **30 W at the 50 K stage** and **~1.5 W at the
4 K stage** (summed over *all* heat-leak mechanisms: radiation through all shields,
all wiring looms, mechanical supports, etc.).

This model's domain1 + 4 lumped coax cables represents **one inner vacuum gap plus one
set of 24 signal cables** — i.e. one contributor among many to the full budget. The
~0.48–2.5 W found here for the 50/77 K stage and ~0.02–0.06 W for the 4 K stage are
**plausible as a fraction of** the ~30 W / ~1.5 W totals (the remainder being other
wiring looms, the outer domain0 radiation path which is unmeasured here, mechanical
supports, etc.). **Do not present these numbers as "the" 50 K or 4 K stage heat load —
they are a sub-component.** No directly-comparable published figures were available in
project memory for the 100 mK / 10 mK stages, so no literature comparison is offered
for stage3/stage4; this would be a useful addition if a suitable reference is found.

---

## 5. Suite-Wide Caveats and Limitations

These apply to **all six** cases and should be read alongside each stage's own §9.

1. **domain0 (the outer OVC ↔ shield_slave gap) has zero postProcessing coverage in
   every stage.** The entire outer-can radiation/conduction path is unquantified
   across the whole suite — a significant gap for any total-budget claim.
2. **postProcessing data has multiple "generations".** `.../100/surfaceFieldValue.dat`
   is stale template data, *identical across all six stage directories* (verified) —
   ignore it. `.../0/surfaceFieldValue.dat` (no suffix) is an earlier pre-fix run
   (e.g. showing the ~360 W radiation bug from before Fix 2). Only
   `.../0/surfaceFieldValue_0.dat` (with the `_0` suffix), last row, was used for §3.
3. **controlDict postProcessing function objects are inconsistently named/mapped in
   every stage**: duplicate `patchInt_domain1_coldPlate_WHF` entries, "OVC"-named
   function objects in domain1 that don't correspond to a real "OVC" patch on that
   region's mesh, entries whose reported face count doesn't match the live mesh, and
   entries that stop updating at Time=600 (stale). Each per-stage README documents the
   specific mismatches found and how the agent resolved them by cross-checking face
   counts and value magnitudes.
4. **`thermophysicalProperties` files are missing from the synced local copies of
   stage2, stage3 and stage4 (all regions)** — the coax `kappa` values quoted
   throughout (4.50, 4.16, 0.159, 0.0043 W/m·K) and any domain0/domain1 solid
   conductivity could **not** be independently verified against case files; they are
   carried forward from the 2026-05-30 fix-session project memory only. Re-sync or
   regenerate these dictionaries before quoting kappa values as fact.
5. **Large energy imbalances in stage1 and stage2** (−3.94 W / −1.95 W / +0.024 W /
   +0.032 W, i.e. 50–800% of the warm-side inflow) — most likely attributable to (a)
   the un-instrumented domain0 path and (b) coax end-cap fluxes not captured by any
   function object. **stage3 and stage4 close almost perfectly** (<1e-7 relative),
   likely because their simpler conduction-only, radiation-off setup happens to have
   complete function-object coverage of all boundary patches.
6. **Coax lumping (24 → 4)**: each `coax_L*` represents 6 physical cables; divide by 6
   for a per-cable estimate (see table in §3).
7. **Kapitza (acoustic-mismatch) interface resistance is not modeled anywhere.**
   Negligible above ~4 K (stage1/stage2). For **stage3** (0.1 K), Kapitza
   κ_eff ≈ 5e-4 W/m·K is *comparable to* the bulk coax κ = 0.159 W/m·K — results are a
   plausible upper bound. For **stage4** (0.01 K), Kapitza κ_eff ≈ 5e-7 W/m·K is **~3
   orders of magnitude below** the bulk coax κ = 0.0043 W/m·K — Kapitza resistance
   would *dominate* the interface if included, so **stage4's heat-load numbers are
   likely overestimates by orders of magnitude**. An on-paper "_kap" variant
   (`kapitza_L1-4` thin solid annuli) was designed but never built or run — it does not
   exist as a result and should not be cited as one.
8. **stage4's "chip" region is a passive conductor only** — a 10×10×9.5 mm solid block
   CHT-coupled to domain1 with a fixedValue 10 mK cold anchor, and **no
   heat-dissipation/power source**. It does **not** represent an active experiment or
   qubit heat load. If the dissertation needs a "sample power dissipation" figure, this
   model does not provide one — that would need to be added as an `fvOptions` heat
   source in a future revision.
9. **Console logs**: only `stage1_shield_50K_v2` has synced console logs — and it has
   *two* generations: an intermediate 2026-05-29 run (`log.chtMultiRegionSimpleFoam_50K_v2`,
   superseded) and the final 2026-05-30 run (`log.chtMultiRegionSimpleFoam_cp`,
   canonical, used for §3). `log.chtMultiRegionSimpleFoam_77K_32ray` is an **old
   pre-v2 run of a differently-structured predecessor case**
   (`stage1_shield_77K_improved_cht_coax`, with `domain1/domain2/coax_lumped` regions
   and 32-ray fvDOM radiation) — it is historical context only and was not used for any
   v2 result. No console logs exist for stage2/3/4.
10. **Dead/stale artefacts** appear in every stage's `system/` and `0/` directories:
    individual `coax01`–`coax24` cable dicts, leftover `domain2/3/5/7` (stage1) or
    `domain1`–`domain14` (stage2+) region dicts, `fluid`/`coax_lumped` template
    directories, and entire dead `postProcessing/domain2/...` trees. These are
    pre-lumping/pre-refactor template leftovers, **not** active model components, and
    must not be described as such in the dissertation.
11. **Steady-state only** — no transient cooldown trajectory is modeled by any case.
    **Mesh independence has not been checked** for any of the six stages.

---

## 6. Model Evolution: v1 → v2 Fix History

All six "_v2" cases were run together in a queue on 2026-05-30
(`run_v2_all_queue.sh`, order: stage1_77K, stage1_50K, stage2_from77K, stage2_from50K,
stage3, stage4), each from `startTime=0` to `endTime=2000`. The fixes below were
applied on top of an earlier v1/template setup that was found to give unphysical
results.

| Fix | Applies to | What it fixed / why | Status here |
|---|---|---|---|
| 2026-05-29 (a) SIGFPE p=0 on coax CHT patches | stage1 (fluid domain0/domain1) | Zero density on coax coupling faces crashed the solver | Done |
| 2026-05-29 (b) domain1/T `zeroGradient` → CHT | All | Coax coupling patches now use `turbulentTemperatureCoupledBaffleMixed` for proper conjugate coupling | Done |
| 2026-05-29 (c) view-factor F-matrix regen | stage3 | Regenerated radiosity view-factor matrix | Done — now **vestigial** since radiation is off in stage3 |
| 2026-05-29 (d) controlDict patch-name fixes | All | Postprocessing function objects updated to reference v2's `domain0/domain1/coax_L1-4` patch names instead of an older `domain2/coax_lumped` template | **Partially done** — residual dead/duplicate/mismatched entries remain in all six stages (§5.3) |
| Fix 1 — He gas viscosity reduction | stage1: μ=1e-11 Pa·s; stage2-4: μ=1e-10 Pa·s if fluid | Suppresses spurious convection in near-vacuum perfect-gas regions | Confirmed in stage1; **N/A** for stage2-4 (no fluid regions) |
| Fix 2 — coax radiation G=0 bug | domain1_to_coax_L1-4 | `calculated; value 0` (perfect-blackbody-at-0K sink, ~3.9 W spurious loss) → `MarshakRadiation; emissivity 0.02` | Confirmed for stage1 (both); not found in stage2 dicts but `qr≈0` anyway (low impact); N/A stage3/4 |
| Fix 3 — coax κ correction | All coax_L1-4 | `0.006277` (≈2000× too low) → temperature-integrated effective κ: 12.9 (77K), 12.2 (50K), 4.16 (2-from77K), 4.50 (2-from50K), 0.159 (stage3), 0.0043 (stage4) W/m·K | Confirmed in stage1 dicts; **unverifiable** in stage2-4 (missing thermophysicalProperties, §5.4) |
| Fix 4 — coax warm-end anchoring | stage2 only | Added a `warmPlate` patch (topoSet+createPatch, z≈0.2447 m) to coax_L1-4, fixedValue T = upstream stage's cold-plate temperature (50 K or 77 K) | Confirmed for both stage2 variants; minor 956-vs-938-face mismatch on the domain1 mapped side, handled by nearestPatchFace mapping |
| Fix 5 — radiation off | stage3/4 | `radiationModel none; radiation off;` — T⁴ negligible below ~4 K | Effectively confirmed (no per-region radiationProperties + physically moot) |
| Fix 6 — Kapitza resistance | stage3/4 | **Skipped** (would require remesh). See §5.7 | Not implemented |
| Fix 7 — T limiters (Tlow/Thigh) | stage2-4 gas regions | Prevent enthalpy→T inversion blow-ups | Likely **N/A** — stage2-4 have no fluid regions; appears to be a residual/unused setting |

---

## 7. Notes for Dissertation Use

- **Safe to cite directly**: the overall cascade architecture (§1–2), the qualitative
  2–3-orders-of-magnitude drop in heat load per stage transition (§3), the radiation
  model choice per stage and its physical justification (§2), the coax 24→4 lumping
  convention, and the v2 fix history (§6) as a record of model development.
- **Needs re-verification before being quoted as a final number**: every absolute
  Watt value in §3, especially stage1 and stage2 given their large unexplained energy
  imbalances; all coax κ values for stage2-4 (missing source dictionaries); the
  stage1_77K vs stage1_50K inflow comparison; and any claim about stage4's "chip"
  representing an experiment heat load (it does not, currently).
- **Recommended follow-up work** before final write-up: (1) add domain0
  `surfaceFieldValue` function objects to all six controlDicts; (2) clean up the
  duplicate/stale/mismatched postProcessing entries identified per-stage; (3)
  re-confirm/regenerate `thermophysicalProperties` for stage2-4; (4) build and run the
  on-paper Kapitza `_kap` variants for stage3/stage4 and compare against the baseline
  numbers here; (5) if a sample heat load is needed, add an `fvOptions` heat source to
  stage4's "chip" region.
