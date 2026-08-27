"""Declared teaching cladding materials for radial temperature comparisons."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CladdingMaterial:
    key: str
    label: str
    conductivity_W_mK: float
    color: str
    note: str


CLADDING_MATERIALS = {
    item.key: item for item in (
        CladdingMaterial(
            "zircaloy4", "Zircaloy-4", 16.0, "#9aa4b2",
            "Representative constant conductivity; temperature and irradiation dependence omitted.",
        ),
        CladdingMaterial(
            "stainless304", "304 stainless steel", 15.0, "#c9d1d9",
            "Representative constant conductivity for comparison.",
        ),
        CladdingMaterial(
            "fecral", "FeCrAl (generic)", 12.0, "#b87333",
            "Generic educational FeCrAl value, not a qualified alloy model.",
        ),
        CladdingMaterial(
            "silicon_carbide", "SiC composite (effective)", 8.0, "#6e7681",
            "Illustrative effective through-thickness conductivity; anisotropy omitted.",
        ),
    )
}
