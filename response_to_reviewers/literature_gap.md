# Literature map and the gap this paper fills (Consensus search, 2026-09-27)

## Strand 1 — How first thermal shields are cooled in practice
- Large fusion/accelerator cryostats circulate **pressurised helium gas** through shield cooling tubes: ITER (80 K, 1.8 MPa), DTT (1.8 MPa, 80–100 K; ANSYS + RELAP5 module analysis) [Barone 2020], LHD (gaseous He, parallel paths) [Imagawa 2002], LHC (50–75 K) [Lebrun 2000].
- Shield **design-temperature optimisation** is done with lumped static heat-load budgets and refrigeration-power minimisation: DEMO thermal shields [Končar; Groth 2024], multi-stage shields for SC transmission-line cryostats [Miles 2008], Lagrange-multiplier optimisation of **LN2/neon vs He-gas intercepts** for SMES magnets and helium dewars [Li 1990 a,b].
- Li et al. (1990) state the practical case for nitrogen explicitly: a boiling cryogen holds the shield temperature constant and provides stored reserve, whereas a helium-gas shield warms immediately when refrigeration stops. This is the closest prior comparison of the two routes, and it is lumped and 1-D.
- Dry laboratory cryostats (dilution refrigerators) use a PTR first stage at 40–50 K [Uhlig 2004; Krinner 2019]; design reviews of advanced cryostats collate MLI performance and optimal Carnot power vs intercept temperature [Shu 2024]; a single intermediate radiation layer alone cuts the cold-wall load by ~57 % in a GERDA-scale cryostat [Singh 2025].

## Strand 2 — Wiring heat loads and their modelling
- Harness loads are measured and modelled per cable: stainless and NbTi coax [Krinner 2019]; SC-086 cupronickel k(T) measured and fitted, qubit-count limits derived from a 1-D stage budget [Raicu 2025]; regenerator intercepts for cable arrays [Snodgrass 2022]; heat sinking of coax in dilution refrigerators [Klostermann 1991].
- These are 1-D conduction integrals or stage-budget models: they give the total per stage, not the distribution over the shield or among cable families, and they do not couple the harness to the radiation field.

## Strand 3 — CFD of radiation-dominated cryogenic enclosures
- View-factor / surface-to-surface radiation in CFD codes must be validated on enclosure benchmarks with analytical solutions before use in fusion vacuum vessels [Končar 2018]; OpenFOAM viewFactor vs fvDOM vs CFX agree to ~0.25 K in buoyant enclosures [Haskell 2021]; Monte-Carlo view factors for UHV chambers reach ~1 % of analytical [Cogger 2024].
- No published multi-region CHT model couples enclosure view-factor radiation with temperature-dependent harness conduction for a cryostat first shield, nor examines the non-monotonic behaviour of agglomerated view-factor matrices in that setting.

## Strand 4 — Cryogenic coolant / heat-exchanger performance
- Entropy-generation minimisation is established for cryogenic counter-flow and plate-fin exchangers [Lerou 2005; Wilhelmsen 2018; Hånde 2019]; LN2-cooled terminals with integrated heat exchangers have been modelled with analytical + CFD + semi-empirical frameworks, showing that axial redistribution changes the cold-end load by an order of magnitude and that CFD-calibrated Pr_t is needed [Gačnik 2025].
- No study ranks **helium gas against liquid nitrogen as a forced-convection first-shield coolant** on a common duty across laminar-to-turbulent regimes and pressures, with heat-transfer, hydraulic, effectiveness and second-law metrics reported together, and with the single-phase margin of the nitrogen verified.

## Strand 5 — Energy cost of the cryogenic plant
- Cryogenic plant is identified as a dominant energy cost of scaled quantum platforms [DeMichielis 2025; Martin 2021; PRX Quantum 2022]; cryocooler efficiencies are ~1 % of Carnot at 4 K and 10–15 % at 80 K [Radebaugh 2009]; LHC exergy analysis quantifies distribution-system losses [Claudet 2010]; nitrogen liquefaction exergy efficiency ~36 % in real plants [Karabuğa 2018].
- Ideal Carnot ledgers and hardware-efficiency ledgers give different verdicts on the shield route; no prior work reconciles them for the He-gas vs LN2 shield choice with an explicit break-even condition.

## The gap (one paragraph, as used in the Introduction)
The two shield-cooling routes have been compared only with lumped one-dimensional budgets (Li 1990; Končar; Miles 2008), the harness only with per-cable integrals (Krinner 2019; Raicu 2025), the radiation only in isolation (Končar 2018), and the coolants only in unrelated exchanger geometries (Lerou 2005; Gačnik 2025). Nothing joins them: a spatially resolved conjugate model of shield radiation and harness conduction, a like-for-like helium-gas vs liquid-nitrogen cold-plate comparison across regimes and pressures, and a work ledger that distinguishes ideal from hardware efficiency. This paper supplies the three pieces on one geometry and one duty, and states the conditions under which each route wins.

## Consensus references used
- Raicu et al. 2025, EPJ Quantum Technology — https://consensus.app/papers/details/86505accc6985808b0599f5bca8d10b1/
- Krinner et al. 2018/2019, EPJ Quantum Technology — https://consensus.app/papers/details/4b6c67370c61596f88273cce3acda85e/
- Gačnik et al. 2025, Applied Thermal Engineering — https://consensus.app/papers/details/b5ed5c5e90da5f7782c4f9ccc0c366c5/
- Snodgrass et al. 2022, IOP CS:MSE — https://consensus.app/papers/details/6f268d6e183f5b789ea46ab0b86a7955/
- Klostermann et al. 1991 — https://consensus.app/papers/details/e658e331e1f35a04b675fa557b742353/
- Shu et al. 2024, IOP CS:MSE — https://consensus.app/papers/details/7e0979c1e1c054448c3fd09ddd9d376f/
- Končar et al., DEMO thermal shields — https://consensus.app/papers/details/6949f7914787518abc6628eeea31238b/
- Zhang et al. 2024, Energy — https://consensus.app/papers/details/c932d9dd6eca58319f316233afae8447/
- Li et al. 1990, SMES intercepts — https://consensus.app/papers/details/dde72b2fbb8f5d4683fa1e22cdb3ef72/
- Li et al. 1990, helium dewar intercepts — https://consensus.app/papers/details/6066fe96763f51aca32646252ed5377f/
- Singh et al. 2025, IJHMT — https://consensus.app/papers/details/5405df235dee5c23b1a2aab48fbd863b/
- Barone et al. 2020, Fusion Eng. Des. — https://consensus.app/papers/details/410a4217547d564d97b232b393cae6f6/
- Miles et al. 2008 — https://consensus.app/papers/details/f561968432d65ecfa8a1f4be4e0c17d4/
- Lerou et al. 2005, Cryogenics — https://consensus.app/papers/details/ce722dda8acc5d2b903f3ddade44e667/
- Wilhelmsen et al. 2018, IJHE — https://consensus.app/papers/details/c0f7ebe5c40a5a0780879bf620e3791d/
- Hånde et al. 2019, IJHE — https://consensus.app/papers/details/8bbdf56747a353908391700e6034af2e/
- Končar et al. 2018, CFD radiation validation — https://consensus.app/papers/details/1e77092a96cf5c5c93ac46a0648eba19/
- Haskell et al. 2021, OpenFOAM radiation BC — https://consensus.app/papers/details/a20e3ba710ca5b4fa501efa59ec6101d/
- Cogger et al. 2024, UHV view factors — https://consensus.app/papers/details/7f300ae6bb3653f38af3a09edfc3034f/
