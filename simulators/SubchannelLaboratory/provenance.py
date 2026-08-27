"""Calculation provenance records for future click/hover explanations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CalculationProvenance:
    quantity: str
    model_key: str
    model_label: str
    citation: str
    note: str = ""
