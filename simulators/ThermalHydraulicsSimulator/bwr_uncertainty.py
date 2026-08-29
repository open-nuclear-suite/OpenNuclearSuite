"""R8 numerical-robustness and local-sensitivity tools for the BWR surrogate.

The calculations are deterministic one-at-a-time screens.  They identify
parameters worth replacing with better data; they are not probabilistic safety
analysis and the perturbation bands are not statistical uncertainties.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping

from bwr_calibration import snapshot
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
    absolute_mass_residual_kg: float
    absolute_energy_residual_MJ: float


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


# Screening bands are engineering perturbations around generic teaching values,
# not claims about actual component uncertainty.
R8_SENSITIVITY_SPECS = (
    SensitivitySpec("alpha_void", "RECIRC_TRIP", 15.0),
    SensitivitySpec("bwr_core_friction_head_ref_m", "RECIRC_TRIP", 15.0),
    SensitivitySpec("bwr_srv_capacity_kg_s", "TURBINE_TRIP", 15.0),
    SensitivitySpec("bwr_break_discharge_coefficient", "SBLOCA", 30.0),
    SensitivitySpec("bwr_rcic_capacity_kg_s", "SBLOCA", 30.0),
    SensitivitySpec("bwr_reference_leg_sensitivity", "LOFW", 30.0),
)


def run_transient(
    scenario: str,
    duration_s: float,
    *,
    timestep_s: float = 0.05,
    parameter_overrides: Mapping[str, float] | None = None,
) -> TransientResult:
    """Run one deterministic transient and collect extrema/closure measures."""
    if timestep_s <= 0.0 or duration_s <= 0.0:
        raise ValueError("duration and timestep must be positive")
    steps = round(duration_s / timestep_s)
    if abs(steps * timestep_s - duration_s) > 1e-9:
        raise ValueError("duration must be an integer multiple of timestep")

    backend = ThermalHydraulicsGUIBackend()
    backend.select_plant("BWR")
    backend.select_scenario(scenario)
    for name, value in (parameter_overrides or {}).items():
        if not hasattr(backend.sim.c, name):
            raise ValueError(f"Unknown BWR parameter: {name}")
        setattr(backend.sim.c, name, float(value))

    state = backend.state
    peak_pressure = state.P
    minimum_inventory = state.M
    peak_clad = state.Tcl
    trip_time = 0.0 if state.trip else None
    mass_residual_integral = 0.0
    energy_residual_integral = 0.0
    for _ in range(steps):
        backend.sim.step_model(timestep_s)
        peak_pressure = max(peak_pressure, state.P)
        minimum_inventory = min(minimum_inventory, state.M)
        peak_clad = max(peak_clad, state.Tcl)
        if trip_time is None and state.trip:
            trip_time = state.t
        mass_residual_integral += abs(state.bwr_mass_balance_residual_kg_s) * timestep_s
        energy_residual_integral += abs(state.bwr_energy_balance_residual_MW) * timestep_s

    values = snapshot(state)
    if not all(isfinite(value) for value in values.values()):
        raise RuntimeError(f"Non-finite result in {scenario}")
    return TransientResult(
        scenario, duration_s, timestep_s, values, peak_pressure,
        minimum_inventory, peak_clad, trip_time,
        mass_residual_integral, energy_residual_integral,
    )


def _response_metrics(result: TransientResult) -> dict[str, float]:
    return {
        "final_power": result.endpoint["power"],
        "final_pressure": result.endpoint["pressure"],
        "final_inventory": result.endpoint["inventory"],
        "final_flow": result.endpoint["flow"],
        "peak_pressure": result.peak_pressure_mpa,
        "minimum_inventory": result.minimum_inventory,
        "peak_clad_temperature": result.peak_clad_temperature_C,
        "trip_time": (
            result.trip_time_s if result.trip_time_s is not None else result.duration_s
        ),
    }


def local_sensitivity(spec: SensitivitySpec, *, timestep_s: float = 0.05) -> SensitivityResult:
    """Return dimensionless central sensitivities for a single parameter."""
    baseline = run_transient(spec.scenario, spec.duration_s, timestep_s=timestep_s)
    backend = ThermalHydraulicsGUIBackend(); backend.select_plant("BWR")
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
    base_metrics = _response_metrics(baseline)
    low_metrics = _response_metrics(low)
    high_metrics = _response_metrics(high)
    floors = {
        "final_power": 0.02, "final_pressure": 1.0, "final_inventory": 0.1,
        "final_flow": 0.1, "peak_pressure": 1.0, "minimum_inventory": 0.1,
        "peak_clad_temperature": 100.0,
        "trip_time": max(1.0, baseline.duration_s),
    }
    sensitivities = {
        name: (high_metrics[name] - low_metrics[name])
        / (2.0 * band * max(abs(base_metrics[name]), floors[name]))
        for name in base_metrics
    }
    return SensitivityResult(
        spec, sensitivities, max(abs(value) for value in sensitivities.values())
    )


def ranked_sensitivities(
    specs: tuple[SensitivitySpec, ...] = R8_SENSITIVITY_SPECS,
    *, timestep_s: float = 0.05,
) -> tuple[SensitivityResult, ...]:
    return tuple(sorted(
        (local_sensitivity(spec, timestep_s=timestep_s) for spec in specs),
        key=lambda result: result.maximum_absolute_sensitivity,
        reverse=True,
    ))


def timestep_difference(
    scenario: str, duration_s: float, coarse_s: float = 0.05, fine_s: float = 0.025,
) -> dict[str, float]:
    """Return normalized endpoint differences for a transient timestep pair."""
    coarse = run_transient(scenario, duration_s, timestep_s=coarse_s)
    fine = run_transient(scenario, duration_s, timestep_s=fine_s)
    floors = {"power": 0.02, "pressure": 1.0, "inventory": 0.1, "flow": 0.1}
    return {
        key: abs(coarse.endpoint[key] - fine.endpoint[key])
        / max(abs(fine.endpoint[key]), floor)
        for key, floor in floors.items()
    }
