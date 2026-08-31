"""P2-1 numerical-robustness and local-sensitivity tools for the PWR surrogate.

The calculations are deterministic one-at-a-time screens. They prioritize
generic parameters for better data; they are not statistical uncertainties,
component tolerances, failure probabilities, or probabilistic safety analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping

from pwr_calibration import snapshot
from thermal_hydraulics_gui_backend import ThermalHydraulicsGUIBackend


@dataclass(frozen=True)
class TransientResult:
    scenario: str
    duration_s: float
    timestep_s: float
    endpoint: Mapping[str, float]
    peak_pressure_mpa: float
    minimum_inventory: float
    peak_clad_temperature_C: float
    trip_time_s: float | None
    absolute_mass_residual_fraction: float
    absolute_energy_residual_MJ: float
    absolute_projection_mass_fraction: float
    absolute_projection_energy_MJ: float
    absolute_secondary_mass_residual_kg: float
    absolute_secondary_energy_residual_MJ: float


@dataclass(frozen=True)
class SensitivitySpec:
    parameter: str
    scenario: str
    duration_s: float
    fractional_band: float = 0.20


@dataclass(frozen=True)
class SensitivityResult:
    spec: SensitivitySpec
    metric_sensitivities: Mapping[str, float]
    maximum_absolute_sensitivity: float


P2_SENSITIVITY_SPECS = (
    SensitivitySpec("break_coeff", "SBLOCA", 30.0),
    SensitivitySpec("pwr_rcp_shutoff_head_m", "LOFA", 15.0),
    SensitivitySpec("pwr_loop_loss_head_m", "LOFA", 15.0),
    SensitivitySpec("pwr_hpsi_runout_fraction_s", "SBLOCA", 30.0),
    SensitivitySpec("pwr_lpsi_runout_fraction_s", "LBLOCA", 30.0),
    SensitivitySpec("pressurizer_tau", "LOHS", 30.0),
    SensitivitySpec("pwr_secondary_pressure_energy_capacity_MJ_MPa", "SBLOCA", 30.0),
    SensitivitySpec("pwr_axial_void_reactivity_pcm_per_fraction", "SBO", 30.0),
)


def run_transient(
    scenario: str,
    duration_s: float,
    *,
    timestep_s: float = 0.05,
    parameter_overrides: Mapping[str, float] | None = None,
) -> TransientResult:
    if timestep_s <= 0.0 or duration_s <= 0.0:
        raise ValueError("duration and timestep must be positive")
    steps = round(duration_s / timestep_s)
    if abs(steps * timestep_s - duration_s) > 1.0e-9:
        raise ValueError("duration must be an integer multiple of timestep")

    backend = ThermalHydraulicsGUIBackend()
    backend.select_scenario(scenario)
    for name, value in (parameter_overrides or {}).items():
        if not hasattr(backend.sim.c, name):
            raise ValueError(f"Unknown PWR parameter: {name}")
        descriptor = getattr(type(backend.sim.c), name, None)
        if isinstance(descriptor, property) and descriptor.fset is None:
            raise ValueError(f"PWR parameter is derived and cannot be overridden: {name}")
        setattr(backend.sim.c, name, float(value))

    state = backend.state
    peak_pressure = state.P
    minimum_inventory = state.M
    peak_clad = state.Tcl
    trip_time = 0.0 if state.trip else None
    mass_residual = energy_residual = 0.0
    projection_mass = projection_energy = 0.0
    secondary_mass = secondary_energy = 0.0
    for _ in range(steps):
        backend.sim.step_model(timestep_s)
        peak_pressure = max(peak_pressure, state.P)
        minimum_inventory = min(minimum_inventory, state.M)
        peak_clad = max(peak_clad, state.Tcl)
        if trip_time is None and state.trip:
            trip_time = state.t
        mass_residual += abs(state.pwr_mass_balance_residual_fraction_s) * timestep_s
        energy_residual += abs(state.pwr_energy_balance_residual_MW) * timestep_s
        projection_mass += abs(state.pwr_projection_mass_correction_fraction_s) * timestep_s
        projection_energy += abs(state.pwr_projection_energy_correction_MW) * timestep_s
        secondary_mass += abs(state.pwr_secondary_mass_residual_kg_s) * timestep_s
        secondary_energy += abs(state.pwr_secondary_energy_residual_MW) * timestep_s

    values = snapshot(state)
    if not all(isfinite(value) for value in values.values()):
        raise RuntimeError(f"Non-finite result in {scenario}")
    return TransientResult(
        scenario, duration_s, timestep_s, values, peak_pressure,
        minimum_inventory, peak_clad, trip_time, mass_residual,
        energy_residual, projection_mass, projection_energy,
        secondary_mass, secondary_energy,
    )


def _response_metrics(result: TransientResult) -> dict[str, float]:
    return {
        "final_power": result.endpoint["power"],
        "final_pressure": result.endpoint["pressure"],
        "final_inventory": result.endpoint["inventory"],
        "final_flow": result.endpoint["flow"],
        "final_void": result.endpoint["void"],
        "final_secondary_pressure": result.endpoint["secondary_pressure"],
        "peak_pressure": result.peak_pressure_mpa,
        "minimum_inventory": result.minimum_inventory,
        "peak_clad_temperature": result.peak_clad_temperature_C,
        "trip_time": result.trip_time_s if result.trip_time_s is not None else result.duration_s,
    }


def local_sensitivity(
    spec: SensitivitySpec, *, timestep_s: float = 0.05,
) -> SensitivityResult:
    baseline = run_transient(spec.scenario, spec.duration_s, timestep_s=timestep_s)
    backend = ThermalHydraulicsGUIBackend()
    nominal = float(getattr(backend.sim.c, spec.parameter))
    band = spec.fractional_band
    low = run_transient(
        spec.scenario, spec.duration_s, timestep_s=timestep_s,
        parameter_overrides={spec.parameter: nominal * (1.0 - band)},
    )
    high = run_transient(
        spec.scenario, spec.duration_s, timestep_s=timestep_s,
        parameter_overrides={spec.parameter: nominal * (1.0 + band)},
    )
    base = _response_metrics(baseline)
    low_metrics = _response_metrics(low)
    high_metrics = _response_metrics(high)
    floors = {
        "final_power": 0.02, "final_pressure": 1.0,
        "final_inventory": 0.1, "final_flow": 0.1, "final_void": 0.05,
        "final_secondary_pressure": 0.5, "peak_pressure": 1.0,
        "minimum_inventory": 0.1, "peak_clad_temperature": 100.0,
        "trip_time": max(1.0, baseline.duration_s),
    }
    sensitivities = {
        name: (high_metrics[name] - low_metrics[name])
        / (2.0 * band * max(abs(base[name]), floors[name]))
        for name in base
    }
    return SensitivityResult(
        spec, sensitivities, max(abs(value) for value in sensitivities.values())
    )


def ranked_sensitivities(
    specs: tuple[SensitivitySpec, ...] = P2_SENSITIVITY_SPECS,
    *, timestep_s: float = 0.05,
) -> tuple[SensitivityResult, ...]:
    return tuple(sorted(
        (local_sensitivity(spec, timestep_s=timestep_s) for spec in specs),
        key=lambda result: result.maximum_absolute_sensitivity,
        reverse=True,
    ))


def timestep_difference(
    scenario: str, duration_s: float,
    coarse_s: float = 0.05, fine_s: float = 0.025,
) -> dict[str, float]:
    coarse = run_transient(scenario, duration_s, timestep_s=coarse_s)
    fine = run_transient(scenario, duration_s, timestep_s=fine_s)
    floors = {
        "power": 0.02, "pressure": 1.0, "inventory": 0.1,
        "flow": 0.1, "void": 0.05, "secondary_pressure": 0.5,
    }
    return {
        key: abs(coarse.endpoint[key] - fine.endpoint[key])
        / max(abs(fine.endpoint[key]), floor)
        for key, floor in floors.items()
    }
