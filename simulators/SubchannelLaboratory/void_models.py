"""Selectable equilibrium-quality-to-void-fraction teaching models."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class VoidFractionResult:
    void_fraction: float
    slip_ratio: float
    valid: bool
    message: str = ""


@dataclass(frozen=True)
class VoidFractionModel:
    key: str
    label: str
    citation: str
    evaluate: Callable[..., VoidFractionResult]
    note: str


def _phase_boundary(quality: float) -> VoidFractionResult | None:
    if quality <= 0.0:
        return VoidFractionResult(0.0, 1.0, True, "Single-phase liquid boundary")
    if quality >= 1.0:
        return VoidFractionResult(1.0, 1.0, True, "Single-phase vapor boundary")
    return None


def _alpha_from_slip(quality: float, rho_l: float, rho_g: float, slip: float) -> float:
    return 1.0 / (
        1.0 + ((1.0 - quality) / quality) * (rho_g / rho_l) * slip
    )


def homogeneous_void(*, quality: float, rho_l: float, rho_g: float, **_: float) -> VoidFractionResult:
    boundary = _phase_boundary(quality)
    if boundary is not None:
        return boundary
    return VoidFractionResult(_alpha_from_slip(quality, rho_l, rho_g, 1.0), 1.0, True)


def zivi_void(*, quality: float, rho_l: float, rho_g: float, **_: float) -> VoidFractionResult:
    boundary = _phase_boundary(quality)
    if boundary is not None:
        return boundary
    slip = (rho_l / rho_g) ** (1.0 / 3.0)
    return VoidFractionResult(_alpha_from_slip(quality, rho_l, rho_g, slip), slip, True)


def smith_void(*, quality: float, rho_l: float, rho_g: float, **_: float) -> VoidFractionResult:
    boundary = _phase_boundary(quality)
    if boundary is not None:
        return boundary
    entrainment = 0.4
    liquid_to_vapor_mass = (1.0 - quality) / quality
    slip = entrainment + (1.0 - entrainment) * math.sqrt(
        (rho_l / rho_g + entrainment * liquid_to_vapor_mass)
        / (1.0 + entrainment * liquid_to_vapor_mass)
    )
    return VoidFractionResult(_alpha_from_slip(quality, rho_l, rho_g, slip), slip, True)


def zuber_findlay_void(
    *, quality: float, rho_l: float, rho_g: float, mass_flux: float,
    surface_tension: float, inclination_degrees: float, **_: float,
) -> VoidFractionResult:
    boundary = _phase_boundary(quality)
    if boundary is not None:
        return boundary
    j_g = mass_flux * quality / rho_g
    j_l = mass_flux * (1.0 - quality) / rho_l
    distribution = 1.2
    drift_velocity = 1.53 * (
        9.80665 * surface_tension * (rho_l - rho_g) / rho_l**2
    ) ** 0.25
    alpha = j_g / (distribution * (j_g + j_l) + drift_velocity)
    alpha = min(max(alpha, 1.0e-9), 1.0 - 1.0e-9)
    vapor_velocity = j_g / alpha
    liquid_velocity = j_l / (1.0 - alpha)
    slip = vapor_velocity / max(liquid_velocity, 1.0e-12)
    valid = inclination_degrees >= 60.0 and rho_l > rho_g > 0.0
    message = "" if valid else "Zuber-Findlay teaching constants are limited to upward near-vertical flow"
    return VoidFractionResult(alpha, slip, valid, message)


VOID_FRACTION_MODELS = {
    "homogeneous": VoidFractionModel(
        "homogeneous", "Homogeneous equilibrium (S = 1)",
        "Homogeneous no-slip relation", homogeneous_void,
        "Baseline with equal phase velocities.",
    ),
    "zivi": VoidFractionModel(
        "zivi", "Zivi minimum-entropy slip",
        "Zivi, Journal of Heat Transfer 86 (1964) 247-252", zivi_void,
        "Slip ratio S = (rho_l/rho_g)^(1/3).",
    ),
    "smith": VoidFractionModel(
        "smith", "Smith equal-velocity-head",
        "Smith, Proc. IMechE 184 (1969) 647-664", smith_void,
        "Separated-flow model with the recommended entrainment fraction e = 0.4.",
    ),
    "zuber_findlay": VoidFractionModel(
        "zuber_findlay", "Zuber-Findlay drift flux",
        "Zuber and Findlay, US AEC report GEAP-4592 (1964)", zuber_findlay_void,
        "Teaching form uses C0 = 1.2 and the 1.53 drift-velocity coefficient; upward near-vertical flow only.",
    ),
}
