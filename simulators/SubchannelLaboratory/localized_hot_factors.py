"""Localized axial hot-factor definitions and combination rules."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class LocalizedPowerFactor:
    location_fraction: float = 0.5
    magnitude: float = 1.10
    width_fraction: float = 0.10
    shape: str = "gaussian"
    enabled: bool = True


LOCAL_FACTOR_SHAPES = ("gaussian", "triangular", "rectangular")
HOT_FACTOR_COMBINATION_METHODS = ("multiplicative", "statistical_rss")


def localized_factor_profile(
    z_m: np.ndarray, heated_length_m: float, factor: LocalizedPowerFactor,
) -> np.ndarray:
    if factor.shape not in LOCAL_FACTOR_SHAPES:
        raise ValueError(f"unknown localized factor shape: {factor.shape}")
    location = float(np.clip(factor.location_fraction, 0.0, 1.0))
    width = max(float(factor.width_fraction), 1.0e-6)
    distance = abs(z_m / heated_length_m - location)
    if factor.shape == "gaussian":
        sigma = width / 2.355  # width is interpreted as FWHM
        kernel = np.exp(-0.5 * (distance / sigma)**2)
    elif factor.shape == "triangular":
        kernel = np.maximum(1.0 - 2.0 * distance / width, 0.0)
    else:
        kernel = (distance <= width / 2.0).astype(float)
    return 1.0 + (factor.magnitude - 1.0) * kernel


def combine_localized_power_factors(
    z_m: np.ndarray, heated_length_m: float,
    factors: tuple[LocalizedPowerFactor, ...],
) -> np.ndarray:
    combined = np.ones_like(z_m, dtype=float)
    for factor in factors:
        if factor.enabled:
            combined *= localized_factor_profile(z_m, heated_length_m, factor)
    return combined


def combine_power_hot_factors(
    z_m: np.ndarray,
    heated_length_m: float,
    factors: tuple[LocalizedPowerFactor, ...],
    global_factor: float,
    method: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Return the localized-only and global-plus-local hot factors.

    Statistical RSS treats deviations from unity as independent, unsigned
    uncertainties. The physical axial heat shape is deliberately not included.
    """
    if method not in HOT_FACTOR_COMBINATION_METHODS:
        raise ValueError(f"unknown hot-factor combination method: {method}")
    enabled_profiles = [
        localized_factor_profile(z_m, heated_length_m, factor)
        for factor in factors if factor.enabled
    ]
    if method == "multiplicative":
        localized = np.ones_like(z_m, dtype=float)
        for profile in enabled_profiles:
            localized *= profile
        return localized, float(global_factor) * localized

    squared_deviation = np.zeros_like(z_m, dtype=float)
    for profile in enabled_profiles:
        squared_deviation += (profile - 1.0) ** 2
    localized = 1.0 + np.sqrt(squared_deviation)
    overall = 1.0 + np.sqrt((float(global_factor) - 1.0) ** 2 + squared_deviation)
    return localized, overall
