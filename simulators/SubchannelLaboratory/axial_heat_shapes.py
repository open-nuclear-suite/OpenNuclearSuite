"""Normalized axial linear-heat-rate shapes for teaching comparisons."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np


@dataclass(frozen=True)
class AxialHeatShape:
    key: str
    label: str
    note: str
    evaluate: Callable[[np.ndarray, float, float], np.ndarray]


def _normalize(shape: np.ndarray) -> np.ndarray:
    clipped = np.maximum(np.asarray(shape, dtype=float), 0.0)
    mean = float(np.mean(clipped))
    if not np.isfinite(mean) or mean <= 0.0:
        raise ValueError("axial heat shape must contain positive finite values")
    return clipped / mean


def _uniform(z_m: np.ndarray, heated_length_m: float, parameter: float) -> np.ndarray:
    del heated_length_m, parameter
    return np.ones_like(z_m)


def _sinusoidal(z_m: np.ndarray, heated_length_m: float, parameter: float) -> np.ndarray:
    del parameter
    return _normalize(np.sin(np.pi * z_m / heated_length_m))


def _chopped_cosine(z_m: np.ndarray, heated_length_m: float, parameter: float) -> np.ndarray:
    del parameter
    u = z_m / heated_length_m
    return _normalize(0.8187458177 + 0.6812541823 * np.cos(2.0 * 2.436354311 * (u - 0.5)))


def _offset_cosine(z_m: np.ndarray, heated_length_m: float, parameter: float) -> np.ndarray:
    u = z_m / heated_length_m
    offset = float(np.clip(parameter, -0.35, 0.35))
    return _normalize(0.8187458177 + 0.6812541823 * np.cos(
        2.0 * 2.436354311 * (u - 0.5 - offset)
    ))


def _skewed_sine(z_m: np.ndarray, heated_length_m: float, parameter: float) -> np.ndarray:
    u = z_m / heated_length_m
    skew = float(np.clip(parameter, -1.0, 1.0))
    return _normalize(np.sin(np.pi * u) * np.exp(3.0 * skew * (u - 0.5)))


def _piecewise_linear(z_m: np.ndarray, heated_length_m: float, parameter: float) -> np.ndarray:
    del parameter
    u = z_m / heated_length_m
    locations = np.array((0.0, 0.2, 0.5, 0.8, 1.0))
    factors = np.array((0.35, 0.85, 1.35, 1.05, 0.45))
    return _normalize(np.interp(u, locations, factors))


AXIAL_HEAT_SHAPES = {
    "uniform": AxialHeatShape(
        "uniform", "Uniform", "Constant linear heat rate over the heated length.", _uniform,
    ),
    "sinusoidal": AxialHeatShape(
        "sinusoidal", "Normalized sinusoidal",
        "Sine shape evaluated at cell centers and normalized to unit discrete mean.",
        _sinusoidal,
    ),
    "chopped_cosine": AxialHeatShape(
        "chopped_cosine", "Chopped cosine",
        "Standard positive chopped-cosine teaching profile; normalized to unit discrete mean.",
        _chopped_cosine,
    ),
    "offset_cosine": AxialHeatShape(
        "offset_cosine", "Chopped cosine with offset",
        "Shape parameter shifts the chopped-cosine peak by a fraction of heated length.",
        _offset_cosine,
    ),
    "skewed_sine": AxialHeatShape(
        "skewed_sine", "Adjustably skewed sine",
        "Negative/positive shape parameter skews power toward inlet/outlet.", _skewed_sine,
    ),
    "piecewise_linear": AxialHeatShape(
        "piecewise_linear", "Piecewise-linear teaching profile",
        "Five-point asymmetric profile, interpolated at cell centers and normalized.",
        _piecewise_linear,
    ),
}
