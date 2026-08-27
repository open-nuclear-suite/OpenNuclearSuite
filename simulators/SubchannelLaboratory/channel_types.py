"""Shared immutable records for the single-channel teaching model."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .provenance import CalculationProvenance
from .localized_hot_factors import LocalizedPowerFactor


@dataclass(frozen=True)
class ChannelGeometry:
    node_count: int = 30
    heated_length_m: float = 3.66
    unheated_inlet_length_m: float = 0.0
    unheated_outlet_length_m: float = 0.0
    rod_outer_diameter_m: float = 0.00950
    clad_inner_diameter_m: float = 0.00836
    rod_pitch_m: float = 0.01260
    roughness_m: float = 1.5e-6

    def __post_init__(self) -> None:
        if self.node_count < 4:
            raise ValueError("node_count must be at least four")
        if self.heated_length_m <= 0.0:
            raise ValueError("heated length must be positive")
        if self.unheated_inlet_length_m < 0.0 or self.unheated_outlet_length_m < 0.0:
            raise ValueError("unheated channel lengths cannot be negative")
        if not self.rod_pitch_m > self.rod_outer_diameter_m > self.clad_inner_diameter_m > 0.0:
            raise ValueError("rod pitch must exceed the positive rod diameter")

    @property
    def flow_area_m2(self) -> float:
        return self.rod_pitch_m**2 - math.pi * self.rod_outer_diameter_m**2 / 4.0

    @property
    def wetted_perimeter_m(self) -> float:
        return math.pi * self.rod_outer_diameter_m

    @property
    def hydraulic_diameter_m(self) -> float:
        return 4.0 * self.flow_area_m2 / self.wetted_perimeter_m

    @property
    def total_channel_length_m(self) -> float:
        return self.unheated_inlet_length_m + self.heated_length_m + self.unheated_outlet_length_m


@dataclass(frozen=True)
class ChannelInputs:
    inlet_pressure_mpa: float = 15.5
    inlet_temperature_C: float = 290.0
    mass_flow_kg_s: float = 0.38
    average_linear_heat_W_m: float = 18_000.0
    power_factor: float = 1.15
    flow_factor: float = 1.0
    friction_key: str = "haaland"
    heat_transfer_key: str = "gnielinski"
    boiling_key: str = "chen"
    cladding_key: str = "zircaloy4"
    inclination_degrees: float = 90.0
    void_model_key: str = "homogeneous"
    two_phase_friction_key: str = "homogeneous"
    heat_shape_key: str = "sinusoidal"
    heat_shape_parameter: float = 0.0
    localized_power_factors: tuple[LocalizedPowerFactor, ...] = ()
    preserve_power_with_local_factors: bool = True
    hot_factor_combination_method: str = "multiplicative"
    chf_key: str = "tong_w3"
    groeneveld_k1: bool = True
    groeneveld_k2: bool = False
    groeneveld_k4: bool = False


@dataclass(frozen=True)
class ChannelResult:
    z_m: np.ndarray
    pressure_mpa: np.ndarray
    bulk_temperature_C: np.ndarray
    saturation_temperature_C: np.ndarray
    wall_temperature_C: np.ndarray
    inner_clad_temperature_C: np.ndarray
    enthalpy_kj_kg: np.ndarray
    equilibrium_quality: np.ndarray
    void_fraction: np.ndarray
    slip_ratio: np.ndarray
    void_model_valid: np.ndarray
    mass_flux_kg_m2_s: np.ndarray
    velocity_m_s: np.ndarray
    liquid_velocity_m_s: np.ndarray
    vapor_velocity_m_s: np.ndarray
    reynolds: np.ndarray
    prandtl: np.ndarray
    nusselt: np.ndarray
    viscosity_Pa_s: np.ndarray
    conductivity_W_mK: np.ndarray
    surface_tension_N_m: np.ndarray
    friction_factor: np.ndarray
    two_phase_friction_multiplier: np.ndarray
    liquid_reynolds: np.ndarray
    vapor_reynolds: np.ndarray
    two_phase_friction_valid: np.ndarray
    two_phase_friction_detail: tuple[str, ...]
    mixture_density_kg_m3: np.ndarray
    friction_pressure_drop_kpa: np.ndarray
    gravity_pressure_drop_kpa: np.ndarray
    acceleration_pressure_drop_kpa: np.ndarray
    total_pressure_drop_kpa: np.ndarray
    cumulative_friction_pressure_drop_kpa: np.ndarray
    cumulative_gravity_pressure_drop_kpa: np.ndarray
    cumulative_acceleration_pressure_drop_kpa: np.ndarray
    cumulative_pressure_drop_kpa: np.ndarray
    heat_transfer_coefficient_W_m2K: np.ndarray
    surface_heat_flux_W_m2: np.ndarray
    linear_heat_rate_W_m: np.ndarray
    base_linear_heat_rate_W_m: np.ndarray
    axial_heat_shape_factor: np.ndarray
    base_axial_heat_shape_factor: np.ndarray
    localized_power_factor: np.ndarray
    combined_power_factor: np.ndarray
    boiling_onset_margin_C: np.ndarray
    critical_heat_flux_W_m2: np.ndarray
    dnbr: np.ndarray
    chf_correlation_valid: np.ndarray
    chf_predictions_W_m2: dict[str, np.ndarray]
    chf_validity: dict[str, np.ndarray]
    chf_interpolation_detail: dict[str, tuple[str, ...]]
    selected_chf_key: str
    nucleate_boiling_active: np.ndarray
    wall_heat_transfer_mode: tuple[str, ...]
    flow_regime: tuple[str, ...]
    validity_messages: tuple[str, ...]
    inlet_enthalpy_kj_kg: float
    outlet_enthalpy_kj_kg: float
    outlet_pressure_mpa: float
    outlet_temperature_C: float
    outlet_equilibrium_quality: float
    outlet_void_fraction: float
    outlet_flow_regime: str
    deposited_power_W: float
    heated_surface_area_m2: float
    heat_shape_key: str
    heat_shape_parameter: float
    preserve_power_with_local_factors: bool
    hot_factor_combination_method: str
    onset_nucleate_boiling_height_m: float
    bulk_boiling_height_m: float
    nonboiling_length_m: float
    subcooled_boiling_length_m: float
    bulk_two_phase_length_m: float
    provenance: tuple[CalculationProvenance, ...]

    @property
    def minimum_dnbr(self) -> float:
        return float("nan") if np.all(np.isnan(self.dnbr)) else float(np.nanmin(self.dnbr))

    @property
    def peak_wall_temperature_C(self) -> float:
        return float(np.nanmax(self.wall_temperature_C))

    @property
    def node_pressure_drop_kpa(self) -> np.ndarray:
        return self.total_pressure_drop_kpa

    @property
    def total_heated_pressure_drop_kpa(self) -> float:
        return 0.0 if self.cumulative_pressure_drop_kpa.size == 0 else float(self.cumulative_pressure_drop_kpa[-1])

    @property
    def total_friction_pressure_drop_kpa(self) -> float:
        return float(np.sum(self.friction_pressure_drop_kpa))

    @property
    def total_gravity_pressure_drop_kpa(self) -> float:
        return float(np.sum(self.gravity_pressure_drop_kpa))

    @property
    def total_acceleration_pressure_drop_kpa(self) -> float:
        return float(np.sum(self.acceleration_pressure_drop_kpa))

    @property
    def average_surface_heat_flux_W_m2(self) -> float:
        return self.deposited_power_W / self.heated_surface_area_m2


@dataclass(frozen=True)
class StatisticalSettings:
    sample_count: int = 250
    seed: int = 2026
    power_sigma_fraction: float = 0.03
    flow_sigma_fraction: float = 0.02
    pitch_sigma_fraction: float = 0.001
    diameter_sigma_fraction: float = 0.001


@dataclass(frozen=True)
class StatisticalResult:
    peak_wall_temperature_C: np.ndarray
    minimum_dnbr: np.ndarray
    power_factors: np.ndarray
    flow_factors: np.ndarray
