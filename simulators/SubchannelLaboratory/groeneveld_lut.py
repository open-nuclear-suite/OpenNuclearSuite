"""Bounded interpolation of the Groeneveld 2006 CHF lookup table."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path

import numpy as np


PRESSURE_MPA = np.array((
    0.10, 0.30, 0.50, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0,
    8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0,
    17.0, 18.0, 19.0, 20.0, 21.0,
))
MASS_FLUX = np.array((
    0, 50, 100, 300, 500, 750, 1000, 1500, 2000, 2500, 3000,
    3500, 4000, 4500, 5000, 5500, 6000, 6500, 7000, 7500, 8000,
), dtype=float)
QUALITY = np.array((
    -0.50, -0.40, -0.30, -0.20, -0.15, -0.10, -0.05, 0.00, 0.05,
    0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60,
    0.70, 0.80, 0.90, 1.00,
))


@dataclass(frozen=True)
class GroeneveldResult:
    chf_W_m2: float
    valid: bool
    detail: str
    uncertainty_class: int = -1
    uncertainty_label: str = "unavailable"
    worst_corner_class: int = -1
    worst_corner_label: str = "unavailable"


DATA_FILENAME = "2006LUTdata.txt"
DATA_SHA256 = "bd113fe78e43697200b7af69151dde4ce159e9b2b8be1f615f7e54778aa0e92c"

# Appendix B cells at G=0 kg/(m2 s), x=-0.50. Spanning the printed,
# non-consecutive planes makes pressure-axis shifts detectable.
PUBLISHED_ANCHORS_KW_M2 = {
    0.10: 8111.0, 0.30: 8027.0, 0.50: 7743.0, 1.00: 7347.0,
    2.00: 7060.0, 3.00: 6741.0, 5.00: 6044.0, 7.00: 5445.0,
    10.00: 4624.0, 12.00: 4070.0, 14.00: 3505.0, 16.00: 2869.0,
    18.00: 2198.0, 20.00: 1654.0, 21.00: 1584.0,
}


@dataclass(frozen=True)
class GroeneveldDataValidation:
    shape: tuple[int, int, int]
    sha256: str
    checksum_matches: bool
    anchors_match: bool

    @property
    def valid(self) -> bool:
        return self.checksum_matches and self.anchors_match


def _data_path() -> Path:
    return Path(__file__).with_name(DATA_FILENAME)


def _load_raw_table() -> np.ndarray:
    raw = np.loadtxt(_data_path())
    required_rows = PRESSURE_MPA.size * MASS_FLUX.size
    if raw.ndim != 2 or raw.shape != (required_rows, QUALITY.size):
        raise RuntimeError(
            f"Groeneveld table has shape {raw.shape}; expected exactly "
            f"({required_rows}, {QUALITY.size})"
        )
    return raw


def validate_groeneveld_data() -> GroeneveldDataValidation:
    raw = _load_raw_table()
    cube = raw.reshape(PRESSURE_MPA.size, MASS_FLUX.size, QUALITY.size)
    digest = hashlib.sha256(_data_path().read_bytes()).hexdigest()
    anchors_match = all(
        cube[int(np.where(PRESSURE_MPA == pressure)[0][0]), 0, 0] == expected
        for pressure, expected in PUBLISHED_ANCHORS_KW_M2.items()
    )
    return GroeneveldDataValidation(
        tuple(int(value) for value in cube.shape), digest,
        digest == DATA_SHA256, anchors_match,
    )


def _load_table() -> np.ndarray:
    raw = _load_raw_table()
    return raw.reshape(PRESSURE_MPA.size, MASS_FLUX.size, QUALITY.size) * 1000.0


TABLE_W_M2 = _load_table()


def _bracket(axis: np.ndarray, value: float) -> tuple[int, int, float]:
    upper = int(np.searchsorted(axis, value, side="right"))
    upper = min(max(upper, 1), axis.size - 1)
    lower = upper - 1
    weight = (value - axis[lower]) / (axis[upper] - axis[lower])
    return lower, upper, float(weight)


def _uncertainty_for_interpolation(
    ip0: int, ip1: int, wp: float,
    ig0: int, ig1: int, wg: float,
    ix0: int, ix1: int, wx: float,
) -> tuple[int, str, int, str, str]:
    from .groeneveld_uncertainty import UNCERTAINTY_LABELS, UNCERTAINTY_MASK

    class_weights = np.zeros(len(UNCERTAINTY_LABELS), dtype=float)
    contributors: list[tuple[int, float]] = []
    for ip, fp in ((ip0, 1.0 - wp), (ip1, wp)):
        for ig, fg in ((ig0, 1.0 - wg), (ig1, wg)):
            for ix, fx in ((ix0, 1.0 - wx), (ix1, wx)):
                weight = fp * fg * fx
                if weight <= 1.0e-12:
                    continue
                uncertainty_class = int(UNCERTAINTY_MASK[ip, ig, ix])
                class_weights[uncertainty_class] += weight
                contributors.append((uncertainty_class, weight))
    maximum_weight = float(class_weights.max())
    # On a tie, report the more cautionary class.
    dominant_class = max(int(index) for index in np.where(
        np.isclose(class_weights, maximum_weight, atol=1.0e-12)
    )[0])
    worst_class = max(item[0] for item in contributors)
    contribution_text = ", ".join(
        f"C{uncertainty_class}:{weight:.3g}"
        for uncertainty_class, weight in contributors
    )
    return (
        dominant_class, UNCERTAINTY_LABELS[dominant_class],
        worst_class, UNCERTAINTY_LABELS[worst_class], contribution_text,
    )


def interpolate_groeneveld_2006(
    pressure_mpa: float,
    mass_flux_kg_m2_s: float,
    quality: float,
    hydraulic_diameter_m: float,
    rod_pitch_m: float,
    rod_outer_diameter_m: float,
    heated_length_m: float,
    rho_l: float,
    rho_g: float,
    *,
    diameter_correction: bool = True,
    bundle_correction: bool = False,
    heated_length_correction: bool = False,
) -> GroeneveldResult:
    inside = (
        PRESSURE_MPA[0] <= pressure_mpa <= PRESSURE_MPA[-1]
        and MASS_FLUX[0] <= mass_flux_kg_m2_s <= MASS_FLUX[-1]
        and QUALITY[0] <= quality <= QUALITY[-1]
        and 0.002 <= hydraulic_diameter_m <= 0.025
    )
    if not inside:
        return GroeneveldResult(float("nan"), False, "outside bounded LUT/domain; no extrapolation")
    ip0, ip1, wp = _bracket(PRESSURE_MPA, pressure_mpa)
    ig0, ig1, wg = _bracket(MASS_FLUX, mass_flux_kg_m2_s)
    ix0, ix1, wx = _bracket(QUALITY, quality)
    uncertainty = _uncertainty_for_interpolation(
        ip0, ip1, wp, ig0, ig1, wg, ix0, ix1, wx
    )
    value = 0.0
    for ip, fp in ((ip0, 1.0 - wp), (ip1, wp)):
        for ig, fg in ((ig0, 1.0 - wg), (ig1, wg)):
            for ix, fx in ((ix0, 1.0 - wx), (ix1, wx)):
                value += fp * fg * fx * TABLE_W_M2[ip, ig, ix]

    factors: list[tuple[str, float]] = []
    if diameter_correction:
        k1 = math.sqrt(0.008 / hydraulic_diameter_m)
        factors.append(("K1 diameter", k1))
        value *= k1
    if bundle_correction:
        gap = rod_pitch_m - rod_outer_diameter_m
        effective_quality = max(0.0, quality)
        k2 = min(1.0, (0.5 + 2.0 * gap / rod_outer_diameter_m)
                 * math.exp(-(effective_quality ** (1.0 / 3.0)) / 2.0))
        factors.append(("K2 bundle", k2))
        value *= k2
    if heated_length_correction:
        if quality < 0.0:
            homogeneous_void = 0.0
        else:
            homogeneous_void = quality * rho_l / (
                quality * rho_l + (1.0 - quality) * rho_g
            )
        k4 = (math.exp(hydraulic_diameter_m / heated_length_m
                       * math.exp(2.0 * homogeneous_void))
              if heated_length_m / hydraulic_diameter_m >= 5.0 else 1.0)
        factors.append(("K4 heated length", k4))
        value *= k4
    factor_text = ", ".join(f"{name}={factor:.5g}" for name, factor in factors) or "no K factors"
    detail = (
        f"P[{PRESSURE_MPA[ip0]:g},{PRESSURE_MPA[ip1]:g}] w={wp:.5g}; "
        f"G[{MASS_FLUX[ig0]:g},{MASS_FLUX[ig1]:g}] w={wg:.5g}; "
        f"x[{QUALITY[ix0]:g},{QUALITY[ix1]:g}] w={wx:.5g}; {factor_text}; "
        f"uncertainty=C{uncertainty[0]} {uncertainty[1]}; "
        f"worst corner=C{uncertainty[2]} {uncertainty[3]}; "
        f"corner class weights={uncertainty[4]}"
    )
    return GroeneveldResult(
        float(value), True, detail,
        uncertainty[0], uncertainty[1], uncertainty[2], uncertainty[3],
    )
