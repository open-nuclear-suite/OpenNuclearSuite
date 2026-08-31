"""Reduced-order one-dimensional representative PWR hot-channel model."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from steam_properties import PropertyRangeError, SteamTables


@dataclass(frozen=True)
class HotChannelGeometry:
    node_count: int = 20
    heated_length_m: float = 3.66
    rod_outer_diameter_m: float = 0.00950
    clad_inner_diameter_m: float = 0.00836
    fuel_diameter_m: float = 0.00819
    rod_pitch_m: float = 0.01260
    nominal_mass_flow_kg_s: float = 0.38
    nominal_average_linear_heat_W_m: float = 18_000.0
    radial_hot_channel_factor: float = 1.15
    nominal_pressure_drop_mpa: float = 0.20
    clad_conductivity_W_mK: float = 16.0
    fuel_conductivity_W_mK: float = 4.0
    gap_conductance_W_m2K: float = 10_000.0
    nominal_coolant_htc_W_m2K: float = 25_000.0

    def __post_init__(self) -> None:
        if self.node_count < 4:
            raise ValueError("node_count must be at least four")
        positive = (
            self.heated_length_m, self.rod_outer_diameter_m,
            self.clad_inner_diameter_m, self.fuel_diameter_m,
            self.rod_pitch_m, self.nominal_mass_flow_kg_s,
            self.nominal_average_linear_heat_W_m,
        )
        if any(value <= 0.0 for value in positive):
            raise ValueError("hot-channel dimensions and reference values must be positive")
        if not self.fuel_diameter_m < self.clad_inner_diameter_m < self.rod_outer_diameter_m:
            raise ValueError("fuel and cladding diameters are inconsistent")

    @property
    def flow_area_m2(self) -> float:
        return self.rod_pitch_m**2 - math.pi * self.rod_outer_diameter_m**2 / 4.0

    @property
    def wetted_perimeter_m(self) -> float:
        return math.pi * self.rod_outer_diameter_m

    @property
    def hydraulic_diameter_m(self) -> float:
        return 4.0 * self.flow_area_m2 / self.wetted_perimeter_m


@dataclass(frozen=True)
class HotChannelResult:
    z_m: np.ndarray
    bulk_temperature_C: np.ndarray
    saturation_temperature_C: np.ndarray
    clad_surface_temperature_C: np.ndarray
    fuel_centerline_temperature_C: np.ndarray
    pressure_mpa: np.ndarray
    enthalpy_kj_kg: np.ndarray
    density_kg_m3: np.ndarray
    mass_flux_kg_m2_s: np.ndarray
    quality: np.ndarray
    linear_heat_W_m: np.ndarray
    surface_heat_flux_W_m2: np.ndarray
    equilibrium_quality: np.ndarray
    critical_heat_flux_W_m2: np.ndarray
    dnbr: np.ndarray
    chf_correlation_valid: np.ndarray
    inlet_enthalpy_kj_kg: float
    outlet_enthalpy_kj_kg: float
    deposited_power_W: float
    phase_warning: str

    @property
    def peak_fuel_index(self) -> int:
        return int(np.nanargmax(self.fuel_centerline_temperature_C))

    @property
    def peak_clad_index(self) -> int:
        return int(np.nanargmax(self.clad_surface_temperature_C))

    @property
    def outlet_temperature_C(self) -> float:
        return float(self.bulk_temperature_C[-1])

    @property
    def minimum_dnbr_index(self) -> int | None:
        if np.all(np.isnan(self.dnbr)):
            return None
        return int(np.nanargmin(self.dnbr))

    @property
    def minimum_dnbr(self) -> float:
        index = self.minimum_dnbr_index
        return float("nan") if index is None else float(self.dnbr[index])


def w3_critical_heat_flux_W_m2(
    pressure_mpa: float,
    mass_flux_kg_m2_s: float,
    equilibrium_quality: float,
    hydraulic_diameter_m: float,
    saturated_minus_inlet_enthalpy_kj_kg: float,
) -> float:
    """Return the Tong W-3 uniform-flux CHF estimate, or NaN out of range.

    The published correlation uses psia, lb/(h ft2), inches, and Btu/lb and
    returns millions of Btu/(h ft2). No extrapolation is performed. This is a
    screening implementation: bundle/grid and non-uniform-flux corrections are
    not applied.
    """
    pressure_psia = pressure_mpa * 145.0377377
    mass_flux_imperial = mass_flux_kg_m2_s * 737.338112
    diameter_in = hydraulic_diameter_m * 39.37007874
    inlet_subcooling_btu_lb = saturated_minus_inlet_enthalpy_kj_kg * 0.429922614
    if not (
        1000.0 <= pressure_psia <= 2300.0
        and 1.0e6 <= mass_flux_imperial <= 5.0e6
        and -0.25 <= equilibrium_quality <= 0.15
        and 0.2 <= diameter_in <= 0.7
        and inlet_subcooling_btu_lb >= 0.0
    ):
        return float("nan")

    x = equilibrium_quality
    p = pressure_psia
    g = mass_flux_imperial / 1.0e6
    first = (2.022 - 0.0004302 * p) + (
        0.1722 - 0.0000984 * p
    ) * math.exp((18.177 - 0.004129 * p) * x)
    second = (0.1484 - 1.596 * x + 0.1729 * x * abs(x)) * g + 1.037
    third = 1.157 - 0.869 * x
    diameter_factor = 0.2664 + 0.8357 * math.exp(-3.151 * diameter_in)
    inlet_factor = 0.8258 + 0.000794 * inlet_subcooling_btu_lb
    chf_million_btu_h_ft2 = first * second * third * diameter_factor * inlet_factor
    return max(0.0, chf_million_btu_h_ft2) * 3.15459075e6


class HotChannelModel:
    def __init__(
        self, properties: SteamTables, geometry: HotChannelGeometry | None = None,
    ) -> None:
        self.properties = properties
        self.geometry = geometry or HotChannelGeometry()

    def solve(
        self,
        power_fraction: float,
        inlet_pressure_mpa: float,
        inlet_temperature_C: float,
        flow_fraction: float,
        axial_power_fractions: np.ndarray | None = None,
    ) -> HotChannelResult:
        g = self.geometry
        count = g.node_count
        dz = g.heated_length_m / count
        z = (np.arange(count, dtype=float) + 0.5) * dz
        if axial_power_fractions is None:
            shape = np.sin(math.pi * z / g.heated_length_m)
            shape /= float(np.mean(shape))
        else:
            coarse = np.maximum(np.asarray(axial_power_fractions, dtype=float), 0.0)
            if coarse.size < 2 or float(np.sum(coarse)) <= 0.0:
                raise ValueError("axial_power_fractions must contain positive zone shares")
            coarse /= float(np.sum(coarse))
            coarse_z = (np.arange(coarse.size, dtype=float) + 0.5) / coarse.size
            shape = np.interp(z / g.heated_length_m, coarse_z, coarse,
                              left=coarse[0], right=coarse[-1])
            shape /= float(np.mean(shape))

        power_scale = max(0.0, power_fraction)
        linear_heat = (
            g.nominal_average_linear_heat_W_m
            * g.radial_hot_channel_factor
            * power_scale
            * shape
        )
        deposited_power = float(np.sum(linear_heat) * dz)
        effective_flow = max(0.05, flow_fraction)
        mass_flow = g.nominal_mass_flow_kg_s * effective_flow
        mass_flux = mass_flow / g.flow_area_m2

        inlet = self.properties.state_pt(inlet_pressure_mpa, inlet_temperature_C)
        boundary_enthalpy = np.empty(count + 1)
        boundary_enthalpy[0] = inlet.enthalpy_kj_kg
        for index in range(count):
            boundary_enthalpy[index + 1] = (
                boundary_enthalpy[index]
                + linear_heat[index] * dz / mass_flow / 1000.0
            )
        enthalpy = 0.5 * (boundary_enthalpy[:-1] + boundary_enthalpy[1:])
        pressure = inlet_pressure_mpa - g.nominal_pressure_drop_mpa * z / g.heated_length_m

        bulk_temperature = np.empty(count)
        saturation_temperature = np.empty(count)
        density = np.empty(count)
        quality = np.full(count, np.nan)
        equilibrium_quality = np.empty(count)
        critical_heat_flux = np.full(count, np.nan)
        phases: list[str] = []
        for index in range(count):
            try:
                state = self.properties.state_ph(float(pressure[index]), float(enthalpy[index]))
            except PropertyRangeError as error:
                raise PropertyRangeError(f"hot-channel node {index + 1}: {error}") from error
            bulk_temperature[index] = state.temperature_C
            saturation_temperature[index] = self.properties.saturation_temperature(
                float(pressure[index])
            )
            density[index] = state.density_kg_m3
            if state.quality is not None:
                quality[index] = state.quality
            saturation = self.properties.saturation_at_pressure(float(pressure[index]))
            equilibrium_quality[index] = (
                enthalpy[index] - saturation.hf_kj_kg
            ) / saturation.latent_heat_kj_kg
            critical_heat_flux[index] = w3_critical_heat_flux_W_m2(
                float(pressure[index]), mass_flux, float(equilibrium_quality[index]),
                g.hydraulic_diameter_m,
                saturation.hf_kj_kg - inlet.enthalpy_kj_kg,
            )
            phases.append(state.phase)

        heat_flux = linear_heat / (math.pi * g.rod_outer_diameter_m)
        dnbr = np.divide(
            critical_heat_flux, heat_flux,
            out=np.full(count, np.nan), where=heat_flux > 0.0,
        )
        correlation_valid = np.isfinite(critical_heat_flux)
        coolant_htc = g.nominal_coolant_htc_W_m2K * math.sqrt(effective_flow)
        clad_surface = bulk_temperature + heat_flux / max(coolant_htc, 1.0)
        clad_resistance = math.log(
            g.rod_outer_diameter_m / g.clad_inner_diameter_m
        ) / (2.0 * math.pi * g.clad_conductivity_W_mK)
        gap_resistance = 1.0 / (
            math.pi * g.fuel_diameter_m * g.gap_conductance_W_m2K
        )
        fuel_resistance = 1.0 / (4.0 * math.pi * g.fuel_conductivity_W_mK)
        fuel_centerline = clad_surface + linear_heat * (
            clad_resistance + gap_resistance + fuel_resistance
        )

        two_phase_nodes = [str(i + 1) for i, phase in enumerate(phases) if phase == "two-phase"]
        warning = ""
        if two_phase_nodes:
            warning = (
                "Two-phase state reached at node(s) " + ", ".join(two_phase_nodes)
                + "."
            )
        invalid_nodes = np.flatnonzero(~correlation_valid) + 1
        if invalid_nodes.size:
            prefix = " " if warning else ""
            warning += (
                prefix + "W-3 CHF is unavailable outside its published range at node(s) "
                + ", ".join(str(node) for node in invalid_nodes) + "."
            )

        return HotChannelResult(
            z, bulk_temperature, saturation_temperature, clad_surface,
            fuel_centerline, pressure, enthalpy, density,
            np.full(count, mass_flux), quality, linear_heat, heat_flux,
            equilibrium_quality, critical_heat_flux, dnbr, correlation_valid,
            inlet.enthalpy_kj_kg, float(boundary_enthalpy[-1]), deposited_power,
            warning,
        )
