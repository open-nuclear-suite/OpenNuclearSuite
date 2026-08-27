"""Selectable two-phase frictional pressure-drop teaching models."""

from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class TwoPhaseFrictionResult:
    pressure_drop_kpa: float
    multiplier: float
    liquid_reynolds: float
    vapor_reynolds: float
    valid: bool
    message: str = ""
    detail: str = ""


@dataclass(frozen=True)
class TwoPhaseFrictionModel:
    key: str
    label: str
    citation: str
    note: str
    evaluate: Callable[..., TwoPhaseFrictionResult]


def _single_phase(
    baseline_dp_kpa: float, reynolds: float,
) -> TwoPhaseFrictionResult:
    return TwoPhaseFrictionResult(baseline_dp_kpa, 1.0, reynolds, 0.0, True)


def homogeneous_friction(
    *, baseline_dp_kpa: float, reynolds: float, **_: float,
) -> TwoPhaseFrictionResult:
    return _single_phase(baseline_dp_kpa, reynolds)


def lockhart_martinelli_chisholm(
    *, quality: float, mass_flux: float, diameter: float, length: float,
    rho_l: float, rho_g: float, mu_l: float, mu_g: float,
    friction_evaluator: Callable[[float], float], baseline_dp_kpa: float,
    reynolds: float, **_: float,
) -> TwoPhaseFrictionResult:
    if not 0.0 < quality < 1.0:
        return _single_phase(baseline_dp_kpa, reynolds)
    g_l = mass_flux * (1.0 - quality)
    g_g = mass_flux * quality
    re_l = g_l * diameter / mu_l
    re_g = g_g * diameter / mu_g
    f_l = 64.0 / re_l if re_l < 2000.0 else friction_evaluator(re_l)
    f_g = 64.0 / re_g if re_g < 2000.0 else friction_evaluator(re_g)
    dp_l = f_l * length / diameter * g_l**2 / (2.0 * rho_l) / 1000.0
    dp_g = f_g * length / diameter * g_g**2 / (2.0 * rho_g) / 1000.0
    x_lm = math.sqrt(max(dp_l, 1.0e-30) / max(dp_g, 1.0e-30))
    liquid_turbulent = re_l >= 2000.0
    vapor_turbulent = re_g >= 2000.0
    if liquid_turbulent and vapor_turbulent:
        chisholm_c = 20.0
    elif liquid_turbulent:
        chisholm_c = 10.0
    elif vapor_turbulent:
        chisholm_c = 12.0
    else:
        chisholm_c = 5.0
    phi_l_squared = 1.0 + chisholm_c / x_lm + 1.0 / x_lm**2
    valid = re_l > 0.0 and re_g > 0.0
    return TwoPhaseFrictionResult(
        phi_l_squared * dp_l, phi_l_squared, re_l, re_g, valid,
        "" if valid else "Lockhart-Martinelli phase Reynolds number is non-positive",
    )


def friedel_friction(
    *, quality: float, mass_flux: float, diameter: float, length: float,
    rho_l: float, rho_g: float, mu_l: float, mu_g: float,
    surface_tension: float, inclination_degrees: float,
    friction_evaluator: Callable[[float], float], baseline_dp_kpa: float,
    reynolds: float, **_: float,
) -> TwoPhaseFrictionResult:
    if not 0.0 < quality < 1.0:
        return _single_phase(baseline_dp_kpa, reynolds)
    re_lo = mass_flux * diameter / mu_l
    re_go = mass_flux * diameter / mu_g
    f_lo = friction_evaluator(re_lo)
    f_go = friction_evaluator(re_go)
    density_h = 1.0 / ((1.0 - quality) / rho_l + quality / rho_g)
    e_term = (1.0 - quality) ** 2 + quality**2 * (rho_l * f_go) / (rho_g * f_lo)
    f_term = quality**0.78 * (1.0 - quality) ** 0.224
    viscosity_ratio = mu_g / mu_l
    h_term = (
        (rho_l / rho_g) ** 0.91
        * viscosity_ratio**0.19
        * max(1.0 - viscosity_ratio, 1.0e-12) ** 0.7
    )
    froude = mass_flux**2 / (9.80665 * diameter * density_h**2)
    weber = mass_flux**2 * diameter / (density_h * surface_tension)
    phi_lo_squared = e_term + 3.24 * f_term * h_term / (
        froude**0.045 * weber**0.035
    )
    dp_lo = f_lo * length / diameter * mass_flux**2 / (2.0 * rho_l) / 1000.0
    valid = (
        mu_l / mu_g < 1000.0
        and mass_flux <= 2000.0
        and inclination_degrees >= 0.0
        and diameter >= 0.004
    )
    message = "" if valid else (
        "Friedel outside teaching limits: mu_l/mu_g < 1000, G <= 2000 kg/m2-s, "
        "D >= 4 mm, and horizontal/upflow"
    )
    return TwoPhaseFrictionResult(
        phi_lo_squared * dp_lo, phi_lo_squared, re_lo, re_go, valid, message,
    )


MARTINELLI_NELSON_PRESSURES_MPA = (
    0.101, 0.689, 3.44, 6.89, 10.3, 13.8, 17.2, 20.7, 22.1,
)
MARTINELLI_NELSON_QUALITIES = (
    0.00, 0.01, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00,
)
MARTINELLI_NELSON_PHI_LO_SQUARED = (
    (1.0, 5.6, 30.0, 69.0, 150.0, 245.0, 350.0, 450.0, 545.0, 625.0, 685.0, 720.0, 525.0),
    (1.0, 3.5, 15.0, 28.0, 56.0, 83.0, 115.0, 145.0, 174.0, 199.0, 216.0, 210.0, 130.0),
    (1.0, 1.8, 5.3, 8.9, 16.2, 23.0, 29.2, 34.9, 40.0, 44.6, 48.6, 48.0, 30.0),
    (1.0, 1.6, 3.6, 5.4, 8.6, 11.6, 14.4, 17.0, 19.4, 21.4, 22.9, 22.3, 15.0),
    (1.0, 1.35, 2.4, 3.4, 5.1, 6.8, 8.4, 9.9, 11.1, 12.1, 12.8, 13.0, 8.6),
    (1.0, 1.2, 1.75, 2.45, 3.25, 4.04, 4.82, 5.59, 6.34, 7.05, 7.70, 7.95, 5.90),
    (1.0, 1.1, 1.43, 1.75, 2.19, 2.62, 3.02, 3.38, 3.70, 3.96, 4.15, 4.20, 3.70),
    (1.0, 1.05, 1.17, 1.30, 1.51, 1.68, 1.83, 1.97, 2.10, 2.23, 2.35, 2.38, 2.15),
    (1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
)


def _bracket(values: tuple[float, ...], target: float) -> tuple[int, int, float]:
    upper = min(max(bisect_right(values, target), 1), len(values) - 1)
    lower = upper - 1
    fraction = (target - values[lower]) / (values[upper] - values[lower])
    return lower, upper, fraction


def martinelli_nelson_friction(
    *, quality: float, pressure_mpa: float, mass_flux: float, diameter: float,
    length: float, rho_l: float, mu_l: float,
    friction_evaluator: Callable[[float], float], baseline_dp_kpa: float,
    reynolds: float, **_: float,
) -> TwoPhaseFrictionResult:
    if quality < 0.0:
        return _single_phase(baseline_dp_kpa, reynolds)
    if not MARTINELLI_NELSON_PRESSURES_MPA[0] <= pressure_mpa <= MARTINELLI_NELSON_PRESSURES_MPA[-1]:
        return TwoPhaseFrictionResult(
            baseline_dp_kpa, 1.0, reynolds, 0.0, False,
            "Martinelli-Nelson pressure outside 0.101-22.1 MPa; homogeneous fallback used",
            "No table extrapolation",
        )
    if quality > 1.0:
        return TwoPhaseFrictionResult(
            baseline_dp_kpa, 1.0, reynolds, 0.0, False,
            "Martinelli-Nelson quality above 1; homogeneous fallback used",
            "No table extrapolation",
        )
    p0, p1, wp = _bracket(MARTINELLI_NELSON_PRESSURES_MPA, pressure_mpa)
    x0, x1, wx = _bracket(MARTINELLI_NELSON_QUALITIES, quality)
    table = MARTINELLI_NELSON_PHI_LO_SQUARED
    phi_p0 = table[p0][x0] + wx * (table[p0][x1] - table[p0][x0])
    phi_p1 = table[p1][x0] + wx * (table[p1][x1] - table[p1][x0])
    multiplier = phi_p0 + wp * (phi_p1 - phi_p0)
    re_lo = mass_flux * diameter / mu_l
    f_lo = friction_evaluator(re_lo)
    dp_lo = f_lo * length / diameter * mass_flux**2 / (2.0 * rho_l) / 1000.0
    detail = (
        f"bilinear table bracket: P={MARTINELLI_NELSON_PRESSURES_MPA[p0]:g}-"
        f"{MARTINELLI_NELSON_PRESSURES_MPA[p1]:g} MPa; "
        f"x={MARTINELLI_NELSON_QUALITIES[x0]:g}-"
        f"{MARTINELLI_NELSON_QUALITIES[x1]:g}"
    )
    return TwoPhaseFrictionResult(
        multiplier * dp_lo, multiplier, re_lo, 0.0, True, "", detail,
    )


TWO_PHASE_FRICTION_MODELS = {
    "homogeneous": TwoPhaseFrictionModel(
        "homogeneous", "Homogeneous mixture",
        "Homogeneous-equilibrium Darcy teaching model",
        "Uses the selected void model's mixture density with no separated-flow multiplier.",
        homogeneous_friction,
    ),
    "lockhart_chisholm": TwoPhaseFrictionModel(
        "lockhart_chisholm", "Lockhart-Martinelli / Chisholm",
        "Lockhart and Martinelli (1949); Chisholm (1967)",
        "Applies phi_l^2 = 1 + C/X + 1/X^2 using phase-flow pressure gradients.",
        lockhart_martinelli_chisholm,
    ),
    "friedel": TwoPhaseFrictionModel(
        "friedel", "Friedel",
        "Friedel, European Two-Phase Flow Group Meeting, Ispra (1979)",
        "Applies Friedel's liquid-only multiplier for horizontal and upward flow.",
        friedel_friction,
    ),
    "martinelli_nelson": TwoPhaseFrictionModel(
        "martinelli_nelson", "Martinelli-Nelson steam-water",
        "Martinelli and Nelson, Trans. ASME 70 (1948) 695-702",
        "Bilinear interpolation of the published pressure-quality liquid-only multiplier table; no extrapolation.",
        martinelli_nelson_friction,
    ),
}
