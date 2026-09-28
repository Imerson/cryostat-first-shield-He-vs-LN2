# v2 (Thermal Science and Engineering Progress submission) — support material

Companion to *Helium gas or liquid nitrogen for the first thermal shield of a 4 K cryostat: conjugate heat-transfer budget, coolant operating maps and work ledger* (2026). This folder supersedes the v1 material in the parent directories for every number quoted in the v2 manuscript.

| Folder | Contents |
|---|---|
| `hx_sweep/` | 22 cold-plate cases (OpenFOAM v2412): laminar Re 500–2300, SST Re 5000/10 000, He at 1/5/18 bar, LN2 at 3 bar, three-grid GCI for both fluids, gravity-on sensitivity (`_gON`). Each case: `0/`, `constant/`, `system/` (incl. `metricConstants`, `postProcess_metrics.sh`, `sampleWall`), `postProcessing/` (function objects, wall-line samples), `metrics.csv`, `Nu_f_report.txt`, `GATE_CHECK.txt`, `yplus_summary.txt` (turbulent), solver log (gz). Field data of the final time step omitted for size; regenerate with `blockMesh` + the solver named in `controlDict`. |
| `enclosure_variants/` | Enclosure CHT variants: MLI-equivalent, emissivity ±50 %, view-factor agglomeration 400/800, and row-normalised view factors (`*_norm250`). Each: `0/`, `constant/` (without meshes and F matrices), `system/`, `postProcessing/heatLoadSummary`, `heat_loads_*.csv`, gate checks, `finalize_case.py`, `extract_heat_loads.py`, `harness_kappa.py`, `normalise_F.py` (norm cases). Baseline production cases are in `../enclosure_CHT/`. |
| `scripts/` | `gen_hx_sweep.py` (builds the sweep with NIST/CoolProp properties), `run_hx_case.sh`, `queue_worker.sh`, `gen_enclosure_variants.sh`, `run_norm_variants.sh`, `normalise_F.py`, `hx_analysis.py`, `enclosure_collect.py`, `ledger.py`, `fig_schematic.py`, `fig_illustrations.py`, `fluid_properties.py`, `pull_results.sh`. |
| `data/` | `hx_sweep_all.csv`, `table_S6_all_runs.csv`, `hx_design_point.csv`, `hx_matched_pumping.csv`, `hx_gci_He.txt`, `enclosure_loads.csv`, `ledger.csv`, `fluid_properties.csv`. |
| `figures/` | All manuscript figures (PNG, 300 dpi). |
| `manuscript/` | LaTeX sources, bibliography, supplementary table source, cover letter. |
| `response_to_reviewers/` | Point-by-point changes relative to the previously reviewed version, literature map. |

Reproduce a cold-plate case: `cd hx_sweep/<case> && blockMesh && <application> && bash system/postProcess_metrics.sh`.
Reproduce an enclosure variant: copy the mesh from `../enclosure_CHT/<baseline>/constant/*/polyMesh`, run `faceAgglomerate -region <r>` and `viewFactorsGen -region <r>` for `domain0`, `domain1`, optionally `python3 normalise_F.py`, then `chtMultiRegionSimpleFoam` and `python3 finalize_case.py`.
