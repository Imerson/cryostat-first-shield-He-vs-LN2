#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analytical.py -- closed-form references the gates compare the CFD against.

Everything here is independent of OpenFOAM so it can serve as ground truth.
"""

import math

SIGMA = 5.670374419e-8       # Stefan-Boltzmann  [W/m^2/K^4]
R_UNIV = 8.314462618         # universal gas constant [J/mol/K]
K_BOLTZ = 1.380649e-23       # [J/K]


# --------------------------------------------------------------------------- #
# radiation
# --------------------------------------------------------------------------- #
def two_surface_radiation(eps_h, A_h, T_h, eps_c, A_c, T_c, F_hc=1.0):
    """Net radiative heat from hot surface h to cold surface c in a grey-diffuse
    two-surface enclosure (W). General form:

        Q = sigma (T_h^4 - T_c^4) /
            [ (1-eps_h)/(eps_h A_h) + 1/(A_h F_hc) + (1-eps_c)/(eps_c A_c) ]

    For concentric/closely-spaced surfaces F_hc ~ 1. Reduces to the standard
    coaxial-cylinder / parallel-plate cryogenic radiation formula."""
    denom = ((1 - eps_h) / (eps_h * A_h)
             + 1.0 / (A_h * F_hc)
             + (1 - eps_c) / (eps_c * A_c))
    return SIGMA * (T_h ** 4 - T_c ** 4) / denom


def radiation_floor(eps_h, A_h, T_h, T_c):
    """Black-body-limited single-surface emission band, used as a loose upper
    bound: Q_max = eps_h sigma A_h (T_h^4 - T_c^4)."""
    return eps_h * SIGMA * A_h * (T_h ** 4 - T_c ** 4)


# --------------------------------------------------------------------------- #
# gas state and flow-regime numbers
# --------------------------------------------------------------------------- #
def gas_density(p_Pa, T, molWeight_gmol):
    """Ideal-gas density [kg/m^3]. molWeight in g/mol (OpenFOAM convention)."""
    M = molWeight_gmol * 1e-3
    return p_Pa * M / (R_UNIV * T)


def mean_free_path(p_Pa, T, d_molecule=2.18e-10):
    """Kinetic-theory mean free path [m]. Default collision diameter ~He."""
    if p_Pa <= 0:
        return float("inf")
    return K_BOLTZ * T / (math.sqrt(2.0) * math.pi * d_molecule ** 2 * p_Pa)


def knudsen(p_Pa, T, L_char, d_molecule=2.18e-10):
    return mean_free_path(p_Pa, T, d_molecule) / L_char


def rayleigh(p_Pa, T_hot, T_cold, L_char, mu, Cp, kappa, molWeight_gmol, g=9.81):
    """Rayleigh number for a gas-filled gap.
        Ra = g beta dT L^3 / (nu alpha)
    beta = 1/T_film (ideal gas), nu = mu/rho, alpha = kappa/(rho Cp).
    rho at the film temperature and the field pressure."""
    T_film = 0.5 * (T_hot + T_cold)
    rho = gas_density(p_Pa, T_film, molWeight_gmol)
    if rho <= 0 or mu <= 0 or kappa <= 0:
        return 0.0
    beta = 1.0 / T_film
    nu = mu / rho
    alpha = kappa / (rho * Cp)
    dT = abs(T_hot - T_cold)
    return g * beta * dT * L_char ** 3 / (nu * alpha)


def kappa_from_mu_pr(mu, Cp, Pr):
    """Gas thermal conductivity implied by mu, Cp, Pr: kappa = Cp mu / Pr."""
    return Cp * mu / Pr


def continuum_gas_conduction(kappa, area, gap, dT):
    """Fourier gas conduction across a gap (W). This is the spurious term the
    vacuum model tries to keep negligible: q = kappa A dT / gap."""
    if gap <= 0:
        return 0.0
    return kappa * area * dT / gap


def free_molecular_conduction(p_Pa, T_gas, dT, area, gamma, molWeight_gmol,
                              accommodation=0.5):
    """Free-molecular (Kennard) heat conduction between surfaces, valid when
    Kn >> 1. q/A = alpha * (gamma+1)/(gamma-1) * 0.5 * sqrt(R/(8 pi M T)) * p * dT.
    Scales with PRESSURE, not with a Fourier kappa. Returns Q [W]."""
    M = molWeight_gmol * 1e-3
    Lam = ((gamma + 1) / (gamma - 1)) * 0.5 * math.sqrt(
        R_UNIV / (8 * math.pi * M * T_gas))
    return accommodation * Lam * p_Pa * dT * area


def peclet(rho, U, Cp, kappa, L):
    """Cell/region thermal Peclet number Pe = rho U Cp L / kappa. Pe<<1 means the
    energy field is conduction-set (well posed) rather than advection-driven."""
    if kappa <= 0:
        return float("inf")
    return rho * abs(U) * Cp * L / kappa
