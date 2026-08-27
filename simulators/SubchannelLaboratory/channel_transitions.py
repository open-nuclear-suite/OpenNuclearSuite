"""Axial interpolation and heated-region classification helpers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BoilingRegions:
    onset_nucleate_boiling_height_m: float
    bulk_boiling_height_m: float
    nonboiling_length_m: float
    subcooled_boiling_length_m: float
    bulk_two_phase_length_m: float


def first_nonnegative_crossing(z_m: np.ndarray, values: np.ndarray) -> float:
    indices = np.flatnonzero(values >= 0.0)
    if indices.size == 0:
        return float("nan")
    index = int(indices[0])
    if index == 0:
        return 0.0
    z0, z1 = float(z_m[index - 1]), float(z_m[index])
    y0, y1 = float(values[index - 1]), float(values[index])
    if y1 == y0:
        return z1
    return z0 + (0.0 - y0) * (z1 - z0) / (y1 - y0)


def classify_boiling_regions(
    z_m: np.ndarray,
    boiling_onset_margin_C: np.ndarray,
    equilibrium_quality: np.ndarray,
    heated_length_m: float,
) -> BoilingRegions:
    onb = first_nonnegative_crossing(z_m, boiling_onset_margin_C)
    bulk = first_nonnegative_crossing(z_m, equilibrium_quality)
    bulk_start = bulk if np.isfinite(bulk) else heated_length_m
    subcooled_start = onb if np.isfinite(onb) else bulk_start
    subcooled_start = min(max(subcooled_start, 0.0), bulk_start)
    return BoilingRegions(
        onset_nucleate_boiling_height_m=onb,
        bulk_boiling_height_m=bulk,
        nonboiling_length_m=subcooled_start,
        subcooled_boiling_length_m=max(bulk_start - subcooled_start, 0.0),
        bulk_two_phase_length_m=(
            max(heated_length_m - bulk_start, 0.0) if np.isfinite(bulk) else 0.0
        ),
    )
