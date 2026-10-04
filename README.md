# Helium gas or liquid nitrogen for the first thermal shield of a 4 K cryostat

Support material for:

> I. Joao, *Helium gas or liquid nitrogen for the first thermal shield of a
> 4 K cryostat: conjugate heat-transfer budget, coolant operating maps and work
> ledger*, submitted to **Thermal Science and Engineering Progress** (2026).

This repository holds every OpenFOAM case, script, data table and figure
behind the numbers quoted in that manuscript, plus the manuscript sources. Solution fields of the final time step and the large view-factor
matrices are **not** stored; each case regenerates them from the dictionaries
and scripts provided.


## Requirements

- OpenFOAM **v2412** (OpenCFD/ESI line): `chtMultiRegionSimpleFoam`,
  `buoyantSimpleFoam`, `buoyantBoussinesqSimpleFoam`, `blockMesh`,
  `faceAgglomerate`, `viewFactorsGen`
- Python 3.10+ with `numpy`, `pandas`, `matplotlib`, `CoolProp`
  (fluid properties; see `scripts/fluid_properties.py`)
- ParaView 6.x (optional, field maps and the enclosure cut-away)
- LaTeX with `elsarticle` to compile the manuscript

## Repository layout

| Folder | Contents |
|---|---|
| `manuscript/` | LaTeX sources (`precooling_v2.tex`, `supplementary_v2.tex`, `table_S6.tex`), bibliography, and the compiled draft PDFs. |
| `hx_sweep/` | The 22 cold-plate cases: laminar *Re* 500–2300, SST *Re* 5000 and 10 000, helium at 1, 5 and 18 bar, LN2 at 3 bar, three-grid GCI for both fluids, and gravity-on sensitivity cases (`_gON`). Each case keeps `0/`, `constant/`, `system/` (including `metricConstants`, `postProcess_metrics.sh`, `sampleWall`), `postProcessing/`, `metrics.csv`, `Nu_f_report.txt`, `GATE_CHECK.txt`, `yplus_summary.txt` (turbulent cases) and the solver log (gzipped). |
| `enclosure_CHT/` | The four baseline enclosure cases of the passive study (`stage1_shield_50K_v2`, `stage1_shield_77K_v2`, `stage2_4K_from50K_v2`, `stage2_4K_from77K_v2`) with their converged `postProcessing/` output, the view-factor agglomeration sweep (`cascade_GCI/`) and the closed-form gate-check suite. Start with `enclosure_CHT/README_master.md`. |
| `enclosure_variants/` | Enclosure variants built on those baselines: MLI-equivalent, emissivity ±50 %, agglomeration 400 and 800, and row-normalised view factors (`*_norm250`). Each keeps `0/`, `constant/` (without meshes and F matrices), `system/`, `postProcessing/heatLoadSummary`, `heat_loads_*.csv`, gate checks and the per-case scripts (`finalize_case.py`, `extract_heat_loads.py`, `harness_kappa.py`, `normalise_F.py`). |
| `scripts/` | `gen_hx_sweep.py` (builds the sweep with NIST/CoolProp properties), `run_hx_case.sh`, `queue_worker.sh`, `gen_enclosure_variants.sh`, `run_norm_variants.sh`, `normalise_F.py`, `hx_analysis.py`, `enclosure_collect.py`, `ledger.py`, `fig_schematic.py`, `fig_illustrations.py`, `render_domain_paraview.py`, `fluid_properties.py`, `pull_results.sh`. |
| `data/` | `hx_sweep_all.csv`, `table_S6_all_runs.csv`, `hx_design_point.csv`, `hx_matched_pumping.csv`, `hx_gci_He.txt`, `enclosure_loads.csv`, `ledger.csv`, `fluid_properties.csv`. |
| `figures/` | All manuscript figures (vector PDF at print width, plus PNG). |


## How the paper maps onto this repository

| Paper | Where |
|---|---|
| Question 1, passive penalty of the warmer shield (enclosure CHT, view-factor row normalisation) | `enclosure_CHT/` baselines, `enclosure_variants/*_norm250`, `scripts/normalise_F.py`, `scripts/enclosure_collect.py`, `data/enclosure_loads.csv` |
| Question 2, coolant operating maps in the cold plate (laminar to turbulent, 1–18 bar, GCI) | `hx_sweep/`, `scripts/gen_hx_sweep.py`, `scripts/hx_analysis.py`, `data/hx_sweep_all.csv`, `data/hx_gci_He.txt` |
| Question 3, room-temperature work ledger | `scripts/ledger.py`, `data/ledger.csv` |
| Supplementary table of all runs | `data/table_S6_all_runs.csv`, `manuscript/table_S6.tex` |

## Reproducing the results

Cold-plate case:

```
cd hx_sweep/<case>
blockMesh
<application named in system/controlDict>
bash system/postProcess_metrics.sh
```

Enclosure variant:

```
# copy the mesh from the matching baseline
cp -r enclosure_CHT/<baseline>/constant/*/polyMesh enclosure_variants/<variant>/constant/<region>/
cd enclosure_variants/<variant>
faceAgglomerate -region domain0 && faceAgglomerate -region domain1
viewFactorsGen  -region domain0 && viewFactorsGen  -region domain1
python3 normalise_F.py          # row-normalised cases only
chtMultiRegionSimpleFoam
python3 finalize_case.py
```

Then `python3 scripts/hx_analysis.py`, `python3 scripts/enclosure_collect.py`
and `python3 scripts/ledger.py` rebuild the tables in `data/`, and the
`fig_*.py` scripts redraw the figures. The shell scripts in `scripts/` encode
the queue used on the author's Ubuntu/OpenFOAM machine and contain absolute
paths from that environment; adjust them before reuse.

## Data availability and licence

Code, case dictionaries and data tables are released under the MIT Licence
(see `LICENSE`). If you use this material, please cite the paper above
(`CITATION.cff` carries the machine-readable reference).

## Contact

Imerson Joao, Department of Engineering Science, University of Oxford —
pemb7049@ox.ac.uk
