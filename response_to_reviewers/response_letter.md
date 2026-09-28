# Changes relative to the previously reviewed version

Manuscript: *Helium gas or liquid nitrogen for the first thermal shield of a 4 K cryostat: conjugate heat-transfer budget, coolant operating maps and work ledger* (submitted to Thermal Science and Engineering Progress)

An earlier version of this work was reviewed at *Cryogenics* under the title *Pre-cooling a superconducting-qubit dilution refrigerator: cascade heat-budget penalty and helium-versus-nitrogen cold-plate coolant selection by CFD*. The present manuscript is a substantial revision. For the editor's convenience, the reviewers' points and the corresponding changes are listed below. Reviewer numbering follows the original reports.

## 1. Scope, objectives and novelty

**R1, R4-1, R4-8: the title, abstract and introduction oversold a "superconducting-qubit dilution refrigerator" that the model does not contain (no dilution unit, mixture pre-cooling or qubit scaling).**
The paper is reframed as the first thermal shield of a 4 K cryostat cooled by circulated helium gas or by liquid nitrogen. Quantum platforms appear as one motivating application in the introduction; the dilution unit is explicitly out of scope (Fig. 1, Section 1). No claim is made about qubit-system energy consumption.

**R2-1: three distinct questions were mixed.**
The manuscript is now organised as Q1 (passive penalty, Section 3), Q2 (coolant performance, Section 4) and Q3 (work ledger, Section 5), each with its own model, figures and conclusion, and the roadmap is stated at the end of Section 1.

**R1: cold helium gas versus LN2 for a shield is an uncommon scenario.**
Section 1 now documents that circulated helium gas is the standard for large cryostat shields (ITER at 80 K and 1.8 MPa, DTT, LHD, LHC at 50–75 K) and that LN2 shields are standard for magnet cryostats; the helium pressure series (1, 5, 18 bar) is anchored to these loops. The literature review identifies the gap explicitly: no prior work joins a resolved radiation-plus-harness enclosure model, a like-for-like coolant comparison, and an ideal-plus-hardware ledger.

**R4-6.2, R1, R3: the CFD reproduces closed-form results to 0.5 %, so it adds nothing; the analysis is elementary.**
We now state plainly that the stage-integrated loads are analytic-verifiable and that their agreement is the model's verification, not its result (Section 2.2). The model's contribution is what closed forms cannot give and what the revision adds: (i) the view-factor closure behaviour of low-emissivity enclosures and its correction (Section 3.1), (ii) the spatial flux and per-bundle conduction split (Section 3.3), (iii) operating maps over laminar-to-turbulent flow and three helium pressures with wall-temperature distributions (Section 4), and (iv) the buoyancy sensitivity that shows nitrogen's mixed convection to be unsteady (Section 4.5). The campaign grew from two cold-plate runs to 22.

**R4-1.2: 50 K versus 77 K gives no unexpected conclusions.**
Non-obvious results now lead: the penalty is conductive and therefore a harness property; a helium-cooled plate at 1 bar floats above 77 K below Re ≈ 1400; the ranking changes with the basis of comparison and inverts on pumping power at 18 bar; the ideal and hardware ledgers give opposite verdicts, reconciled by an explicit break-even (Eq. 8).

## 2. Reproducibility and documentation

**R2-2.1: table of design details.** Tables 1 and 2 list geometry, boundary conditions, reference pressures, radiation settings, emissivities, contact assumptions, channel length and property sources; Supplementary Tables S1–S4 give the region and patch definitions and the harness data.

**R2-2.2: cable fractions, conductivity integrals, polynomial coefficients, mapping to four cylinders.** Section 2.2 and Fig. 3 describe the mapping; Supplementary Table S3 gives the component areas and line counts, Table S4 the fifth-order polynomial coefficients of the effective conductivity for every bundle and span.

**R2-2.3: grid independence for the helium solver.** A three-grid study with the compressible helium solver is added (Table 4; Supplementary Table S8): GCI 0.7 % on Nu and 2.5 % on f. The nitrogen study is repeated with corrected properties (2.2 % and 1.6 %).

**R2-2.4: why retain a radiation solution 19 % above the analytic anchor.** The excess is now explained and removed. The view-factor matrix as generated does not close (row sums 0.50–1.13) and the low emissivities amplify the leak; refinement worsens it (Fig. 6). Row normalisation recovers the closed form to 4 % at the first stage and 0.5 % at the 4 K stage; all loads and the ledger use the normalised values, with the production values as an upper band (Section 3.1; Supplementary Table S5).

**R3: governing equations missing.** Section 2.1 gives the solid conduction, radiosity, continuity, momentum and energy equations, the ideal-gas and Boussinesq closures and the turbulence model.

**R3: replicability.** The repository is restructured (release v2): one folder per case, run scripts, metrics CSVs, figure scripts and a manifest.

## 3. Verification and uncertainty (R2-3, R2-5.5)

Emissivity ±50 % runs give the uncertainty band on every load and on the ledger (Fig. 7, Table 3, Fig. 12). Energy-balance closure is below 0.2 % for every forced-convection run (Supplementary Table S7); the 2–10 % closures of the earlier version are traced to an error in the mixing-cup temperature evaluation on a graded mesh and corrected. The delivered wall heat flux is verified with the solver-native function object. The nitrogen loop is specified at 3 bar and the saturation margin reported for every run (2.2–10.6 K); at 1 bar the wall would exceed saturation in every laminar run, which is now stated.

**Property correction (found in revision).** The helium transport properties of the earlier version corresponded to helium near 15 K; all helium runs now use 50 K values from NIST/CoolProp, and the change is disclosed (Section 2.3, Supplementary Section S2).

## 4. Figures and tables (R2-4, R4-4)

- System schematic distinguishing the PTR route, the circulated-gas cold plate and the LN2 route, with the model domains and the loads entering the ledger: Figs. 1 and 2.
- Ledger with uncertainty bands and an insulated-shield case: Fig. 12 and Table 6 (bare and MLI-equivalent shields, emissivity and efficiency ranges).
- Expanded operating table: Table 5 gives mass flow, volumetric flow, velocity, inlet and outlet temperatures, pressure drop, pumping power, wall temperatures, saturation margin, buoyancy parameter and closure; Supplementary Table S7 gives all 18 runs.
- Wall-temperature profiles instead of stepped contours: Fig. 10 (centreline and cross-channel profiles at three Reynolds numbers).
- More flow states and optimal operating conditions (R4): the Reynolds sweep 500–10 000 and the pressure series (Figs. 9 and 11) identify, for each fluid, the flow needed to hold the plate below a given temperature and the pumping power it costs.

## 5. Interpretation and over-claims (R2-5, R4-5, R1)

- "Entire penalty is conductive" → "86 % conductive", with the radiative share quantified (15 mW, 1.1 W ideal wall power).
- "Nitrogen outperforms helium on every physically decisive metric" → the ranking is stated per basis and per regime (Section 4.4); helium wins effectiveness and, at 18 bar, pumping power.
- The ~74 K helium-cooled wall is stated to belong to the circulated-gas architecture and not to a conductively coupled PTR stage (Section 6).
- "Helium prevails in practice" is now supported by a hardware-based ledger built from published data (PT415 capacity and input power, Radebaugh's fraction-of-Carnot survey, nitrogen-plant specific energy) with ranges, and by the break-even condition of Eq. (8).
- All LN2 conclusions are drawn after establishing single-phase operation by margin.
- R1's point on the 74× multiplier and on real supply efficiency: Section 5 now carries ideal and real multipliers side by side; the real 4 K multiplier is 4900–9300 and dominates the ledger.
- R4-5: Section 2.3 opens with a basis-of-comparison paragraph that reports mass flow, velocity, pressure and property ranges for both fluids and explains why equal Reynolds number is neither equal capacity nor equal cost.

## 6. Structure and language (R2-8, R3, R4-9)

The narrative is governed by the distinction between component performance (Q2), ideal thermodynamics (Q3, ideal ledger) and practical hardware (Q3, real ledger). Sentences are shorter and jargon is defined once. Limitations are collected in a single paragraph at the end of Section 6.

## Corrections the authors found during revision

1. Helium transport properties corrected from ~15 K to 50 K values.
2. Cold-plate comparison re-based on forced convection with buoyancy reported as a sensitivity; the earlier nitrogen result was buoyancy-assisted.
3. Mixing-cup outlet temperature corrected (mass-flux weighting without an extra area factor); energy closure improved from 2–10 % to below 0.2 %.
4. View-factor matrices row-normalised; the 19 % radiation excess removed.
5. Pressure-solver settings changed for the nitrogen cases; no effect on results, threefold faster convergence.
