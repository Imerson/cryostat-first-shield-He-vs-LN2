# Response matrix — Cryogenics rejection → TSEP resubmission

Legend: **R1–R4** reviewer; **Action** what v2 does; **Where** section/figure/table in v2; **Status** ☐ open ☑ done.

## A. Framing, objectives, novelty (R1, R2-Q1, R3, R4-Q1/Q6/Q8)

| # | Comment (condensed) | Action | Where | Status |
|---|---|---|---|---|
| A1 | R4, R1: title/abstract/intro oversell "superconducting-qubit dilution refrigerator"; model covers 300 K → 50/77 K → 4 K only, not the dilution unit, mixture pre-cooling or qubit-count scaling | Full reframe: **first-shield pre-cooling of a 4 K cryostat, circulated helium gas vs liquid nitrogen**. Quantum platforms appear once as the motivating use-case; dilution unit explicitly out of scope; no claims about qubit-system energy | Title, Abstract, §1, §6 | ☐ |
| A2 | R2-Q1: three distinct questions are mixed (passive shield-T penalty; active coolant performance; refrigerator-route selection) | Paper restructured as **Q1 / Q2 / Q3** with one section, one figure set and one conclusion per question; a roadmap paragraph closes §1 | §1 end, §3, §4, §5 | ☐ |
| A3 | R1: "cold He gas vs LN2 shield is an uncommon scenario" | Show it is the norm outside the dilution-fridge community: ITER thermal shield (80 K He gas, 18 bar), LHC thermal shield (50–75 K He gas), fusion/accelerator cryostats; LN2 shields in MRI/large magnets. Gives the He pressure series its physical anchor (1, 5, 18 bar) | §1 ¶2, Table 1, §4 | ☐ |
| A4 | R4-Q6.2, R1, R3: CFD reproduces closed-form to 0.5 %, so CFD adds nothing / analysis is elementary | (i) State honestly that the **stage-integrated loads** are analytic-verifiable and that this agreement is the model's *verification*, not its result; (ii) the CFD contribution is what the closed form cannot give: spatial flux maps, per-bundle conduction split, wall-temperature distributions, developing-flow Nu vs Re maps, turbulent transition, pressure series, and the coupled cold-plate temperature field; (iii) new parametric campaign (14 runs) delivers operating maps and optimal points that no single correlation gives across laminar/transitional/turbulent regimes | §2.4 "What the 3-D model adds", §4 | ☐ |
| A5 | R4-Q1.2: 50 K vs 77 K pre-cooling gives no unexpected conclusions | Lead with the non-obvious results: (a) the penalty is *conductive* and therefore a harness property; (b) He-gas cold plate floats ~20 K above its nominal temperature at low Re, erasing the 50/77 K distinction; (c) corrected He properties change the He/LN2 ranking magnitude; (d) real-COP ledger reverses the ideal ledger; (e) matched-Re and matched-pumping-power rankings differ | Abstract, §5 | ☐ |

## B. Reproducibility & documentation (R2-Q2, R3)

| # | Comment | Action | Where | Status |
|---|---|---|---|---|
| B1 | R2: table of design details (geometry, BCs, reference pressures, radiation settings, emissivities, contact assumptions, channel length, property sources) | New **Table 2 (enclosure)** and **Table 3 (cold plate)** with every numerical input; property sources = CoolProp/NIST REFPROP, table in SI | §2, SI Tables S1–S3 | ☐ |
| B2 | R2: cable cross-sectional fractions, conductivity integrals, polynomial coefficients, mapping of 65 lines → 4 cylinders | New **Table S4**: per-component areas (SS304 outer 1.585 mm², PTFE 2.001 mm², SS304 centre 0.205 mm²), NIST k(T) fits, the k_eff(T) definition, calibrated A_model per case, kappaCoeffs<8> per bundle per case | §2.1 Eq. (3)–(4), SI §S1 | ☐ |
| B3 | R2: grid independence for the *helium* compressible solver too | New 3-mesh GCI on He (86k/292k/984k, Celik 2008) with corrected properties; reported alongside LN2 GCI | §2.5, Table 5, Fig. GCI | ☐ (running) |
| B4 | R2: why retain the production radiation solution 19 % above the analytic anchor | New view-factor agglomeration refinement (250/400/800 coarse faces) with VF-closure metric; report the converged value, use anchor-corrected loads in the ledger, keep production as spatial-field source only | §2.1, Table S5, Fig. 3 | ☐ (running) |
| B5 | R3: governing equations missing | New §2.0 with the multi-region energy equation, radiosity (view-factor) system, solid conduction with k(T), compressible steady RANS/laminar equations for the channel, Boussinesq form for LN2, k–ω SST reference | §2 | ☐ |
| B6 | R3: replicability | Open repository restructured: one folder per case in the paper, `manifest.json`, run scripts, metrics CSVs, figure scripts; Zenodo DOI on acceptance | Data availability, repo README | ☐ |

## C. Verification / uncertainty (R2-Q3, R2-Q5.5)

| # | Comment | Action | Where | Status |
|---|---|---|---|---|
| C1 | Stronger numerical verification and uncertainty analysis | Emissivity ±50 % enclosure runs → uncertainty bands on every load and on the ledger; GCI bands on Nu, f; property-uncertainty statement | §2.6, Fig. 8 bands | ☐ (running) |
| C0 | (found in revision) energy-balance closure was 2–10 % because the outlet mixing-cup temperature used weightedAreaAverage (area counted twice on the graded mesh); corrected to weightedAverage, closure now <0.1 %; wall-flux delivery verified with the solver-native wallHeatFlux function object | §2.3, Table 4 | ☑ |
| C2 | Establish that the LN2 flow stays single phase before drawing LN2 conclusions | LN2 loop specified at **3 bar abs** (T_sat = 87.9 K); wall-temperature maximum reported for every run; saturation margin column in Table 4; runs with margin < 2 K flagged | §2.3, Table 4 | ☐ |
| C3 | He property error (found in revision) | Corrected to NIST/CoolProp (μ 6.36 µPa s, k 0.0467 W m⁻¹K⁻¹ at 50 K); disclosed explicitly | §2.3 footnote, SI | ☐ |

## D. Figures & tables (R2-Q4, R4-Q4)

| # | Comment | Action | Where | Status |
|---|---|---|---|---|
| D1 | System schematic distinguishing PTR route, circulated He-gas cold plate, LN2 route; where passive/active domains connect; which loads enter the ledger | New **Fig. 1** schematic (three columns, loads labelled) | §1/§2 | ☐ |
| D2 | Fig. 8 with uncertainty/sensitivity bands and an insulated-shield case | New ledger figure: bare vs MLI-equivalent shield, ideal vs real-COP, ε ±50 % bands | §5 | ☐ |
| D3 | Expand Table 2: ṁ, volumetric flow, p_in/p_out, Δp, T_in/T_out, mean properties, saturation margin, channel length, heated area, matched-pumping-power comparison | New **Table 4** (design point) + **Table S6** (all 14 runs) | §4 | ☐ |
| D4 | Mesh-independent line profiles / wall-temperature distributions instead of stepped contours | New **Fig. 6**: heated-wall centreline T(x) and cross-channel T(y) for He and LN2 at three Re; contours moved to SI | §4 | ☐ |
| D5 | R4: more flow states; identify optimal operating conditions for each fluid before comparing | Re sweep 500–10⁴ (laminar → SST), He pressure series → **operating maps**: wall superheat vs pumping power (Pareto), h vs Re, saturation margin; optimum defined as min pumping power subject to T_wall ≤ limit | §4.2–4.3, Figs. 5, 7 | ☐ |

## E. Interpretation / over-claims (R2-Q5, R4-Q5, R1)

| # | Comment | Action | Where | Status |
|---|---|---|---|---|
| E1 | "entire penalty is conductive" → "predominantly" | Adopted; radiation share quantified (16 mW ≈ 1.2 W ideal wall power) | §3, §6 | ☐ |
| E2 | Qualify "nitrogen outperforms helium on every physically decisive metric" | Ranking stated per basis (matched Re, matched ṁ, matched pumping power), per regime, with the ε–NTU exception explained; He wins effectiveness and, at 18 bar, pumping power | §4.4, §6 | ☐ |
| E3 | Do not transfer the ~74 K He-cooled wall to a conductively coupled PTR stage | Explicit: result belongs to the circulated-gas architecture; PTR stage handled separately in the ledger | §4.2, §5 | ☐ |
| E4 | Support "helium route prevails in practice" with measured COP data, or state as expectation | Real-COP ledger built from published hardware: PT415 (1.5 W @ 4.2 K + 40 W @ 45 K, 10.5 kW), Radebaugh %-Carnot map, LN2 plant specific energy 0.5–0.7 kWh kg⁻¹ (ideal 0.21) → real multipliers with ranges | §5.2, Table 6 | ☐ |
| E5 | Re-assess LN2 conclusions after single-phase check | Done with C2 | §4 | ☐ |
| E6 | R1: 74× Carnot multiplier is not the practical context; no real-world LN2/He supply efficiency | Real multipliers reported next to ideal: 4 K stage ~1–2 % Carnot (×4000–7000), He first stage ~10–15 % (×35–50), LN2 supply η ≈ 0.3 (×9); ledger recomputed | §5.2 | ☐ |
| E7 | R4: differences in phase state, operating temperature, whole architecture not explained; report ṁ, velocity, pressure, property ranges in §2.2 first paragraph; same Re ≠ same capacity or cost | §2.3 opens with a **basis-of-comparison** paragraph and Table 4 gives all operating quantities; three bases compared | §2.3, §4.4 | ☐ |

## F. Language & structure (R2-Q8, R3, R4-Q9)

| # | Comment | Action | Status |
|---|---|---|---|
| F1 | Simpler, compact language | Shorter sentences, no em-dash chains, one idea per paragraph, jargon defined once, ≤ 8000 words main text | ☐ |
| F2 | Component performance vs ideal thermodynamics vs practical hardware must govern the narrative | Q1/Q2/Q3 structure + §5 split into 5.1 ideal, 5.2 real | ☐ |
| F3 | Language editing | Full pass at the end; consistent SI, symbols, tense | ☐ |
