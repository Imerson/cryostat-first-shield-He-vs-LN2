# Notes for readers (consistency with the paper)

- **View-factor levels.** The `GATE_CHECK_full.txt` files for the Stage-2
  cases report radiative loads at the *coarse* view-factor agglomeration
  level (5.29 mW / 29.7 mW). The production (medium, nFaces=250) values
  used in the paper are 3.44 mW / ~19.3 mW; see
  `cascade_GCI/cascade_convergence.csv` for the full sweep and the
  analytic anchors. Stage-1 gate checks are at the production level.
- **Harness calibration.** The per-bundle kappa_eff(T) fit is a
  fifth-order polynomial (max fit error 0.43%, see gate G3.4), matching
  the paper's "<0.5%" statement.
