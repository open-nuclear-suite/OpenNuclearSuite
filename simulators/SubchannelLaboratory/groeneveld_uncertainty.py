"""Validated categorical uncertainty mask for the Groeneveld 2006 LUT."""

from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
from pathlib import Path

import numpy as np

from .groeneveld_lut import MASS_FLUX, PRESSURE_MPA, QUALITY


MASK_FILENAME = "groeneveld_uncertainty.csv"
MASK_SHA256 = "bba38fa436d9387a1138f8a8b7f6cb3b24d820f480ff9ea24d26e53d05e2b1be"
UNCERTAINTY_LABELS = (
    "direct experimental-data region",
    "calculated/extrapolated region",
    "avoid extrapolation",
    "low-quality region (LQR)",
)
EXPECTED_COUNTS = (4992, 5444, 877, 279)


@dataclass(frozen=True)
class UncertaintyMaskValidation:
    shape: tuple[int, int, int]
    sha256: str
    checksum_matches: bool
    coordinates_match: bool
    class_counts: tuple[int, int, int, int]

    @property
    def valid(self) -> bool:
        return (
            self.checksum_matches
            and self.coordinates_match
            and self.class_counts == EXPECTED_COUNTS
        )


def _mask_path() -> Path:
    return Path(__file__).with_name(MASK_FILENAME)


def _read_mask() -> tuple[np.ndarray, bool]:
    rows: list[list[int]] = []
    coordinates_match = True
    with _mask_path().open(newline="", encoding="utf-8") as stream:
        reader = csv.reader(stream)
        header = next(reader)
        expected_header = [
            "pressure_MPa", "mass_flux_kg_m2_s", *(f"x={quality:g}" for quality in QUALITY)
        ]
        coordinates_match &= header == expected_header
        for row_index, row in enumerate(reader):
            pressure_index, flux_index = divmod(row_index, MASS_FLUX.size)
            if pressure_index >= PRESSURE_MPA.size or len(row) != QUALITY.size + 2:
                coordinates_match = False
                continue
            coordinates_match &= float(row[0]) == PRESSURE_MPA[pressure_index]
            coordinates_match &= float(row[1]) == MASS_FLUX[flux_index]
            rows.append([int(value) for value in row[2:]])
    expected_rows = PRESSURE_MPA.size * MASS_FLUX.size
    if len(rows) != expected_rows:
        raise RuntimeError(f"uncertainty mask has {len(rows)} rows; expected {expected_rows}")
    mask = np.asarray(rows, dtype=np.uint8).reshape(
        PRESSURE_MPA.size, MASS_FLUX.size, QUALITY.size
    )
    if np.any(mask > 3):
        raise RuntimeError("uncertainty mask contains an unknown class")
    return mask, coordinates_match


UNCERTAINTY_MASK, _COORDINATES_MATCH = _read_mask()


def validate_uncertainty_mask() -> UncertaintyMaskValidation:
    digest = hashlib.sha256(_mask_path().read_bytes()).hexdigest()
    counts = tuple(int(value) for value in np.bincount(UNCERTAINTY_MASK.ravel(), minlength=4))
    return UncertaintyMaskValidation(
        tuple(int(value) for value in UNCERTAINTY_MASK.shape), digest,
        digest == MASK_SHA256, _COORDINATES_MATCH, counts,
    )


def uncertainty_label(pressure_index: int, mass_flux_index: int, quality_index: int) -> str:
    return UNCERTAINTY_LABELS[int(UNCERTAINTY_MASK[
        pressure_index, mass_flux_index, quality_index
    ])]
