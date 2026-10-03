# How to build a `chtMultiRegionSimpleFoam` case — walkthrough using stage1_shield_50K_v2

A learning guide for *this* model (OpenFOAM v2412). It explains what the solver does, how the case
is laid out, the exact build pipeline, and the few traps that cost the most time.

---

## 1. What `chtMultiRegionSimpleFoam` is

It is the **steady-state, multi-region Conjugate Heat Transfer** solver. "Conjugate" = it solves
heat transfer in **several meshed regions at once** — some *fluid*, some *solid* — and couples them
at their shared interfaces so temperature and heat flux are continuous across the metal↔gas
boundaries. Each region has its own mesh, physics, and fields; the solver loops over all of them
every outer (SIMPLE) iteration.

Here the "fluid" regions are the **vacuum gaps** (radiation only) and the "solid" regions are the
**coax cable bundles** (conduction). Radiation across the vacuum + conduction down the cables + the
coupling between them = the passive heat load on the cold stage.

## 2. The regions in this case (`constant/regionProperties`)

```
regions
(
    fluid   (domain0 domain1)                    // the two vacuum gaps
    solid   (coax_L1 coax_L2 coax_L3 coax_L4)    // 4 lumped cable bundles
);
```
This single file tells the solver which regions exist and whether each is fluid or solid.
**Everything else is replicated per region.**

## 3. Directory layout — the key mental model

A single-region case has `0/`, `constant/`, `system/`. A multi-region case has those **plus a
sub-folder per region** inside each:

```
constant/
  regionProperties              <- lists fluid/solid regions (above)
  g                             <- gravity (shared)
  domain1/                      <- one FLUID region
    polyMesh/                   <- this region's mesh (made by splitMeshRegions)
    thermophysicalProperties    <- gas properties (here: vacuum)
    radiationProperties         <- viewFactor radiation settings
    boundaryRadiationProperties <- per-patch emissivities
    viewFactorsDict             <- how to build the view-factor matrix
    F, finalAgglom, ...         <- the computed view-factor matrix (generated)
  coax_L1/                      <- one SOLID region
    polyMesh/
    thermophysicalProperties    <- solid k_eff(T) polynomial
system/
  controlDict                   <- shared: application, time control, function objects
  fvSchemes, fvSolution         <- top-level defaults
  blockMeshDict, snappyHexMeshDict, topoSetDict, surfaceFeatureExtractDict   <- meshing
  domain1/  coax_L1/  ...        <- per-region fvSchemes, fvSolution, fvOptions
0/
  domain1/  coax_L1/  ...        <- per-region initial & boundary fields
```
Fluid regions carry `T U p p_rgh alphat` plus radiation fields `G IDefault qr`. Solid regions carry
only `T` (and a dummy `p`). Compare `0/domain1/` vs `0/coax_L1/` to see the difference.

> Note: this folder also has leftover `coax01..24`, `coax_lumped`, `fluid` dirs from earlier model
> iterations. The **active** regions are only the 6 listed in `regionProperties`.

## 4. The build pipeline (run in this order)

`source /usr/lib/openfoam/openfoam2412/etc/bashrc` first. The mesh starts as **one combined mesh**
and is then **split** into the per-region meshes.

```bash
# (1) feature edges from the STL geometry (OVC, shield surfaces)
surfaceFeatureExtract

# (2) background hex mesh covering the whole domain
blockMesh                          # system/blockMeshDict  -> e.g. (30 30 14)

# (3) carve the real geometry into it; creates cellZones for each body
snappyHexMesh -overwrite           # system/snappyHexMeshDict (STLs + searchableBox for coax)

# (4) define the cell/face zones used to separate regions
topoSet                            # system/topoSetDict

# (5) SPLIT the single mesh into per-region meshes (domain0, domain1, coax_L1..4)
splitMeshRegions -cellZones -overwrite
#   -> creates constant/<region>/polyMesh and the *_to_* coupling patches

# (6) put the per-region constant/ and 0/ files in place
#     thermophysicalProperties, radiationProperties, fields + coupling BCs
#     (in this project a setup script writes them; you can also use changeDictionary)

# (7) build the view-factor matrix for EACH fluid region (radiation)
faceAgglomerate -region domain0  &&  viewFactorsGen -region domain0
faceAgglomerate -region domain1  &&  viewFactorsGen -region domain1

# (8) solve all regions, coupled
chtMultiRegionSimpleFoam > log.chtMultiRegionSimpleFoam 2>&1
```

`splitMeshRegions` is the heart of it: it turns one mesh into N region meshes and **auto-creates the
coupling patches** named `<regionA>_to_<regionB>` (e.g. `domain1_to_coax_L1`). Those patches are
where the CHT coupling BC lives (next section).

## 5. The three ideas that make it work

### (a) The CHT coupling boundary condition
At every solid↔fluid interface, both sides use a *coupled* temperature BC that exchanges T and heat
flux with the neighbour region:
```
type        compressible::turbulentTemperatureCoupledBaffleMixed;
Tnbr        T;                 // neighbour field to couple to
kappaMethod fluidThermo;       // (use solidThermo on the solid side)
```
See it in `0/domain1/T` (patch `domain1_to_coax_L1`, `kappaMethod fluidThermo`) and the matching
`0/coax_L1/T` (`kappaMethod solidThermo`). This makes heat continuous across the cable surface. The
driving temperatures are the `fixedValue` walls: warmPlate = 300 K, shield/coldPlate = 50 K.

### (b) View-factor radiation (the vacuum heat transfer)
`constant/domain1/radiationProperties`:
```
radiationModel  viewFactor;
solverFreq 10;                 // update radiation every 10 outer iterations
```
`viewFactorsGen` precomputes the geometric **F matrix** (who sees whom) from the surface mesh;
`faceAgglomerate` first coarsens the surfaces so F is small/fast. Emissivities live in
`boundaryRadiationProperties` (plates 0.04, shield/coax 0.02). Grey-body surface-to-surface exchange
— no participating medium.

### (c) Modelling vacuum as an inert "fluid"
viewFactor radiation must run inside a *fluid* region, so the gap is a fluid forced to behave like
vacuum: `g = (0 0 0)` (no convection), `p = 0.001 Pa`, `mu = 1e-11` (κ_gas ≈ 1e-7 → no gas
conduction), radiatively transparent gas. Result: the only heat across the gap is radiation.
*(Trap: keep p ≈ 0.001 Pa consistently — using 1e5 Pa while density is clipped makes the pressure
equation fight the equation of state and the run never converges.)*

## 6. Running and reading it
```bash
chtMultiRegionSimpleFoam        # reads regionProperties, iterates all regions
```
Heat loads are extracted from the final-time fields by `extract_heat_loads.py` / `finalize_case.py`
(integrate `qr` for radiation, `wallHeatFlux` for conduction). `GATE_CHECK_full.txt` is the QA.
`README.md` has the converged numbers.

## 7. How to modify it (practice)
- **Change a stage temperature:** edit the `fixedValue` in `0/<region>/T` (warmPlate / shield),
  rerun from `0/`. (Radiation scales ~ T⁴.)
- **Change an emissivity:** edit `constant/<fluidRegion>/boundaryRadiationProperties`, regenerate F
  (`faceAgglomerate` + `viewFactorsGen`), rerun.
- **Refine the mesh:** change the `(30 30 14)` base in `blockMeshDict` (and/or snappy levels), re-run
  the whole pipeline from step (2), then regenerate F.
- **Add a region:** add it to `snappyHexMeshDict` (geometry + refinement), `topoSetDict`,
  `regionProperties`, and create its `constant/<r>/` + `system/<r>/` + `0/<r>/`.

## 8. Top traps (learned the hard way here)
1. **Forget to regenerate F after re-meshing** → radiation uses a stale/wrong view-factor matrix.
2. **`regionProperties` mislabels a region** (fluid vs solid) → solidThermo/fluidThermo construction
   crashes at start.
3. **`faceAgglomerate` with no `patchAgglomeration` block** → no coarsening → giant F matrix, minutes
   per radiation solve. Keep `nFacesInCoarsestLevel` set.
4. **`CGAL ... FPU_get_cw()` assertion printed *after* `End`** is HARMLESS (exit-time check; F valid).
5. **Inconsistent vacuum pressure** (see 5c) → divergence.

---
*Companion files here: `build_pipeline_reference.sh` (the actual end-to-end build script),
`constant/regionProperties` (region list), `system/{blockMeshDict,snappyHexMeshDict,topoSetDict}`
(mesh pipeline), `constant/<region>/*` and `0/<region>/*` (per-region physics),
`log.chtMultiRegionSimpleFoam` (a real solver log to read). Build it once end-to-end and the
structure clicks.*
