"""Fast table-based water and steam properties for the teaching simulator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import numpy as np


TABLE_PATH = Path(__file__).resolve().parent / "data" / "if97_ph_table.npz"


class PropertyRangeError(ValueError):
    """Raised when a requested state lies outside the bundled table."""


@dataclass(frozen=True)
class SaturationState:
    pressure_mpa: float
    temperature_C: float
    hf_kj_kg: float
    hg_kj_kg: float
    vf_m3_kg: float
    vg_m3_kg: float
    uf_kj_kg: float
    ug_kj_kg: float
    cpf_kj_kgK: float
    cpg_kj_kgK: float

    @property
    def latent_heat_kj_kg(self) -> float:
        return self.hg_kj_kg - self.hf_kj_kg


@dataclass(frozen=True)
class WaterState:
    pressure_mpa: float
    enthalpy_kj_kg: float
    temperature_C: float
    density_kg_m3: float
    internal_energy_kj_kg: float
    cp_kj_kgK: float
    quality: float | None
    phase: str


@dataclass(frozen=True)
class TransportState:
    viscosity_Pa_s: float
    conductivity_W_mK: float
    surface_tension_N_m: float
    basis: str


class SteamTables:
    """Bilinear pressure-enthalpy interpolation over bundled IF97 values."""

    def __init__(self, path: Path = TABLE_PATH) -> None:
        with np.load(path, allow_pickle=False) as data:
            self.pressures = data["pressure_mpa"]
            self.enthalpies = data["enthalpy_kj_kg"]
            self.temperature = data["temperature_C"]
            self.volume = data["specific_volume_m3_kg"]
            self.internal_energy = data["internal_energy_kj_kg"]
            self.cp = data["cp_kj_kgK"]
            self.viscosity = data["viscosity_Pa_s"] if "viscosity_Pa_s" in data else None
            self.conductivity = (
                data["conductivity_W_mK"] if "conductivity_W_mK" in data else None
            )
            self.sat_temperature = data["sat_temperature_C"]
            self.sat_hf = data["sat_hf"]
            self.sat_hg = data["sat_hg"]
            self.sat_vf = data["sat_vf"]
            self.sat_vg = data["sat_vg"]
            self.sat_uf = data["sat_uf"]
            self.sat_ug = data["sat_ug"]
            self.sat_cpf = data["sat_cpf"]
            self.sat_cpg = data["sat_cpg"]
            self.sat_muf = data["sat_muf_Pa_s"] if "sat_muf_Pa_s" in data else None
            self.sat_mug = data["sat_mug_Pa_s"] if "sat_mug_Pa_s" in data else None
            self.sat_kf = data["sat_kf_W_mK"] if "sat_kf_W_mK" in data else None
            self.sat_kg = data["sat_kg_W_mK"] if "sat_kg_W_mK" in data else None
            self.sat_surface_tension = (
                data["sat_surface_tension_N_m"]
                if "sat_surface_tension_N_m" in data else None
            )
            self.source = str(data["source"])
            self.formulation = str(data["formulation"])
            self.generator_version = str(data["generator_version"])

    @property
    def pressure_range_mpa(self) -> Tuple[float, float]:
        return float(self.pressures[0]), float(self.pressures[-1])

    @property
    def enthalpy_range_kj_kg(self) -> Tuple[float, float]:
        return float(self.enthalpies[0]), float(self.enthalpies[-1])

    @staticmethod
    def _check(value: float, grid: np.ndarray, name: str) -> float:
        if not np.isfinite(value) or value < grid[0] or value > grid[-1]:
            raise PropertyRangeError(
                f"{name}={value:g} outside [{grid[0]:g}, {grid[-1]:g}]"
            )
        return float(value)

    @staticmethod
    def _bracket(grid: np.ndarray, value: float) -> Tuple[int, float]:
        upper = int(np.searchsorted(grid, value, side="right"))
        lower = max(0, min(upper - 1, grid.size - 2))
        fraction = (value - grid[lower]) / (grid[lower + 1] - grid[lower])
        return lower, float(fraction)

    @classmethod
    def _linear(cls, grid: np.ndarray, values: np.ndarray, value: float) -> float:
        index, fraction = cls._bracket(grid, value)
        return float(values[index] * (1.0 - fraction) + values[index + 1] * fraction)

    def _bilinear(self, values: np.ndarray, pressure: float, enthalpy: float) -> float:
        pi, pf = self._bracket(self.pressures, pressure)
        hi, hf = self._bracket(self.enthalpies, enthalpy)
        low = values[pi, hi] * (1.0 - hf) + values[pi, hi + 1] * hf
        high = values[pi + 1, hi] * (1.0 - hf) + values[pi + 1, hi + 1] * hf
        return float(low * (1.0 - pf) + high * pf)

    def _at_pressure(self, values: np.ndarray, pressure: float) -> np.ndarray:
        index, fraction = self._bracket(self.pressures, pressure)
        return values[index] * (1.0 - fraction) + values[index + 1] * fraction

    def saturation_at_pressure(self, pressure_mpa: float) -> SaturationState:
        pressure = self._check(pressure_mpa, self.pressures, "pressure_mpa")
        interpolate = lambda values: self._linear(self.pressures, values, pressure)
        return SaturationState(
            pressure, interpolate(self.sat_temperature), interpolate(self.sat_hf),
            interpolate(self.sat_hg), interpolate(self.sat_vf), interpolate(self.sat_vg),
            interpolate(self.sat_uf), interpolate(self.sat_ug),
            interpolate(self.sat_cpf), interpolate(self.sat_cpg),
        )

    def saturation_temperature(self, pressure_mpa: float) -> float:
        return self.saturation_at_pressure(pressure_mpa).temperature_C

    def saturation_pressure(self, temperature_C: float) -> float:
        temperature = self._check(temperature_C, self.sat_temperature, "temperature_C")
        return self._linear(self.sat_temperature, self.pressures, temperature)

    def transport_ph(
        self, pressure_mpa: float, enthalpy_kj_kg: float,
        two_phase_basis: str = "saturated-liquid",
    ) -> TransportState:
        """Return bounded IF97-backend transport properties.

        Two-phase mixture viscosity and conductivity are not uniquely defined;
        callers must use the saturated-liquid or saturated-vapor phase basis.
        """
        if self.viscosity is None or self.conductivity is None:
            raise PropertyRangeError("transport-property arrays are not present in this table")
        pressure = self._check(pressure_mpa, self.pressures, "pressure_mpa")
        enthalpy = self._check(enthalpy_kj_kg, self.enthalpies, "enthalpy_kj_kg")
        saturation = self.saturation_at_pressure(pressure)
        surface_tension = self._linear(
            self.pressures, self.sat_surface_tension, pressure
        )
        if saturation.hf_kj_kg <= enthalpy <= saturation.hg_kj_kg:
            if two_phase_basis not in ("saturated-liquid", "saturated-vapor"):
                raise ValueError("two_phase_basis must be saturated-liquid or saturated-vapor")
            liquid = two_phase_basis == "saturated-liquid"
            viscosity_values = self.sat_muf if liquid else self.sat_mug
            conductivity_values = self.sat_kf if liquid else self.sat_kg
            return TransportState(
                self._linear(self.pressures, viscosity_values, pressure),
                self._linear(self.pressures, conductivity_values, pressure),
                surface_tension,
                two_phase_basis,
            )
        viscosity = self._bilinear(self.viscosity, pressure, enthalpy)
        conductivity = self._bilinear(self.conductivity, pressure, enthalpy)
        if not np.isfinite(viscosity) or not np.isfinite(conductivity):
            # A rectangular p-h interpolation stencil may straddle the curved
            # saturation boundary even though the requested state is single
            # phase. Transport properties approach their phase saturation
            # values continuously, so use that bounded one-sided limit.
            liquid = enthalpy < saturation.hf_kj_kg
            viscosity_values = self.sat_muf if liquid else self.sat_mug
            conductivity_values = self.sat_kf if liquid else self.sat_kg
            viscosity = self._linear(self.pressures, viscosity_values, pressure)
            conductivity = self._linear(self.pressures, conductivity_values, pressure)
            basis = "compressed-liquid-saturation-limit" if liquid else "superheated-vapor-saturation-limit"
            return TransportState(viscosity, conductivity, surface_tension, basis)
        basis = "compressed-liquid" if enthalpy < saturation.hf_kj_kg else "superheated-vapor"
        return TransportState(viscosity, conductivity, surface_tension, basis)

    def state_ph(self, pressure_mpa: float, enthalpy_kj_kg: float) -> WaterState:
        pressure = self._check(pressure_mpa, self.pressures, "pressure_mpa")
        enthalpy = self._check(enthalpy_kj_kg, self.enthalpies, "enthalpy_kj_kg")
        saturation = self.saturation_at_pressure(pressure)

        if saturation.hf_kj_kg <= enthalpy <= saturation.hg_kj_kg:
            quality = (enthalpy - saturation.hf_kj_kg) / saturation.latent_heat_kj_kg
            volume = saturation.vf_m3_kg + quality * (
                saturation.vg_m3_kg - saturation.vf_m3_kg
            )
            internal_energy = saturation.uf_kj_kg + quality * (
                saturation.ug_kj_kg - saturation.uf_kj_kg
            )
            return WaterState(
                pressure, enthalpy, saturation.temperature_C, 1.0 / volume,
                internal_energy, float("nan"), quality, "two-phase",
            )

        phase = "compressed liquid" if enthalpy < saturation.hf_kj_kg else "superheated vapor"
        cp = self._bilinear(self.cp, pressure, enthalpy)
        if not np.isfinite(cp):
            cp = saturation.cpf_kj_kgK if phase == "compressed liquid" else saturation.cpg_kj_kgK
        return WaterState(
            pressure, enthalpy,
            self._bilinear(self.temperature, pressure, enthalpy),
            1.0 / self._bilinear(self.volume, pressure, enthalpy),
            self._bilinear(self.internal_energy, pressure, enthalpy),
            cp, None, phase,
        )

    def enthalpy_pt(self, pressure_mpa: float, temperature_C: float) -> float:
        """Invert the table for a single-phase pressure-temperature state."""
        pressure = self._check(pressure_mpa, self.pressures, "pressure_mpa")
        saturation = self.saturation_at_pressure(pressure)
        if abs(temperature_C - saturation.temperature_C) < 1.0e-9:
            raise ValueError("saturation temperature requires quality or enthalpy")

        temperatures = self._at_pressure(self.temperature, pressure)
        if temperature_C < saturation.temperature_C:
            mask = self.enthalpies < saturation.hf_kj_kg
            phase_name = "compressed-liquid"
        else:
            mask = self.enthalpies > saturation.hg_kj_kg
            phase_name = "superheated-vapor"
        phase_h = self.enthalpies[mask]
        phase_t = temperatures[mask]
        if phase_h.size < 2 or temperature_C < phase_t[0] or temperature_C > phase_t[-1]:
            raise PropertyRangeError(
                f"temperature_C={temperature_C:g} outside tabulated {phase_name} range "
                f"at {pressure:g} MPa"
            )
        return float(np.interp(temperature_C, phase_t, phase_h))

    def state_pt(self, pressure_mpa: float, temperature_C: float) -> WaterState:
        return self.state_ph(
            pressure_mpa, self.enthalpy_pt(pressure_mpa, temperature_C)
        )
