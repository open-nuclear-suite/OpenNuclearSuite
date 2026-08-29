"""GUI-independent lumped thermal-hydraulics equations and RK4 integrator."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Tuple

import numpy as np

from steam_properties import SteamTables


@dataclass(frozen=True)
class ControlInputs:
    rod_pct: float = 0.0
    trim_pcm: float = 0.0
    boron_ppm: float = 1000.0
    pump_pct: float = 100.0
    sg_pct: float = 100.0
    break_pct: float = 0.0
    eccs_pct: float = 0.0
    afw_pct: float = 0.0
    porv_pct: float = 0.0
    spray_pct: float = 0.0
    heater_pct: float = 0.0
    rhr_pct: float = 0.0
    auto_eccs: bool = True
    auto_eccs_demand: float = float("nan")
    hot_channel_coupling: bool = False
    hot_channel_peak_clad_C: float = float("nan")
    hot_channel_min_dnbr: float = float("nan")


@dataclass(frozen=True)
class StepDiagnostics:
    decay_fraction: float
    rho_total: float
    flow_effective: float
    boiling_regime: str
    chf_ratio: float
    eccs_fraction: float
    break_out: float
    porv_out: float
    evaporation_out: float


class ThermalHydraulicsEngine:
    """Pure equations plus a projected classical fourth-order Runge--Kutta step."""

    N_PRECURSORS = 6
    N_DECAY_GROUPS = 3
    I_N = 0
    I_CI = slice(1, 7)
    I_DI = slice(7, 10)
    I_TF = 10
    I_TCL = 11
    I_UCOOL = 12
    I_M = 13
    I_VOID = 14
    I_TPRZ = 15

    def __init__(self, constants: Any, properties: SteamTables | None = None) -> None:
        self.c = constants
        self.properties = properties or SteamTables()
        self.minimum_pressurizer_temperature = self.properties.saturation_temperature(0.10)
        self.maximum_pressurizer_temperature = self.properties.saturation_temperature(17.50)

    @staticmethod
    def clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def pressure_eccs_factor(self, pressure: float) -> float:
        if pressure > 14.0:
            factor = 0.05
        elif pressure > 8.0:
            factor = 0.05 + 0.65 * (14.0 - pressure) / 6.0
        elif pressure > 2.0:
            factor = 0.70 + 0.30 * (8.0 - pressure) / 6.0
        else:
            factor = 1.0
        return self.clamp(factor, 0.05, 1.0)

    def pack(self, state: Any) -> np.ndarray:
        return np.concatenate(
            (
                np.array([state.n]), state.Ci, state.Di,
                np.array([state.Tf, state.Tcl, state.Ucool, state.M,
                          state.void_fraction, state.Tprz]),
            )
        ).astype(float)

    def unpack_derived(self, vector: np.ndarray) -> Tuple[float, float, float, float]:
        c = self.c
        mass = self.clamp(float(vector[self.I_M]), 0.05, 1.20)
        energy = max(0.0, float(vector[self.I_UCOOL]))
        coolant_temperature = c.coolant_energy_reference_C + energy / (c.Ccool * mass)
        coolant_temperature = self.clamp(coolant_temperature, 20.0, 650.0)
        pressurizer_temperature = self.clamp(
            float(vector[self.I_TPRZ]),
            self.minimum_pressurizer_temperature,
            self.maximum_pressurizer_temperature,
        )
        pressure = self.properties.saturation_pressure(pressurizer_temperature)
        void = self.clamp(float(vector[self.I_VOID]), 0.0, 0.95)
        return mass, coolant_temperature, pressure, void

    def boiling_heat_transfer(
        self, vector: np.ndarray, flow_effective: float, coverage: float,
        hot_channel_min_dnbr: float = float("nan"),
    ) -> Tuple[float, float, str, float]:
        c = self.c
        _, coolant_temperature, pressure, _ = self.unpack_derived(vector)
        clad_temperature = float(vector[self.I_TCL])
        saturation_temperature = self.properties.saturation_temperature(pressure)
        wall_superheat = max(0.0, clad_temperature - saturation_temperature)
        base = c.Kcc_nom * coverage * (0.20 + 0.80 * flow_effective)

        if wall_superheat <= 3.0:
            multiplier, regime = 1.0, "single-phase"
        elif wall_superheat <= 25.0:
            multiplier = 1.0 + 1.8 * (wall_superheat - 3.0) / 22.0
            regime = "nucleate boiling"
        else:
            multiplier, regime = 2.8, "nucleate boiling"

        candidate = max(0.0, base * multiplier * (clad_temperature - coolant_temperature))
        pressure_factor = self.clamp(0.55 + 0.035 * pressure, 0.55, 1.15)
        chf_limit = 4300.0 * coverage * pressure_factor * (
            0.30 + 0.70 * math.sqrt(max(flow_effective, 0.0))
        )
        chf_ratio = candidate / max(chf_limit, 1.0)
        if np.isfinite(hot_channel_min_dnbr) and hot_channel_min_dnbr > 0.0:
            # The axial channel supplies a local W-3 margin. A one-step-lagged
            # value is held fixed through all RK stages, keeping the RHS pure.
            chf_ratio = max(chf_ratio, 1.0 / hot_channel_min_dnbr)
        if chf_ratio > 1.0:
            film_fraction = self.clamp((chf_ratio - 1.0) / 0.6, 0.0, 1.0)
            multiplier *= 1.0 - 0.86 * film_fraction
            regime = "transition boiling" if film_fraction < 0.95 else "film boiling"

        conductance = max(1.5, base * multiplier)
        demand = (
            max(0.0, conductance * (clad_temperature - coolant_temperature))
            if coolant_temperature >= saturation_temperature - 8.0 else 0.0
        )
        return conductance, demand, regime, chf_ratio

    def rhs(
        self, _time_s: float, vector: np.ndarray, controls: ControlInputs,
    ) -> Tuple[np.ndarray, StepDiagnostics]:
        c = self.c
        y = np.asarray(vector, dtype=float)
        n = max(0.0, float(y[self.I_N]))
        precursors = np.maximum(y[self.I_CI], 0.0)
        decay_groups = np.maximum(y[self.I_DI], 0.0)
        fuel_temperature = self.clamp(float(y[self.I_TF]), 20.0, 2800.0)
        clad_temperature = self.clamp(float(y[self.I_TCL]), 20.0, 2200.0)
        mass, coolant_temperature, pressure, void = self.unpack_derived(y)

        rho_rods = -(c.rod_worth_pcm * controls.rod_pct / 100.0) * 1.0e-5
        rho_trim = controls.trim_pcm * 1.0e-5
        rho_boron = c.boron_worth * (controls.boron_ppm - c.boron_ref)
        rho_fuel = c.alpha_f * (fuel_temperature - c.TrefFuel)
        rho_moderator = c.alpha_m * (coolant_temperature - c.TrefCool)
        rho_total = self.clamp(
            rho_rods + rho_trim + rho_boron + rho_fuel + rho_moderator,
            -0.12, 0.012,
        )

        derivatives = np.zeros_like(y)
        derivatives[self.I_N] = (
            ((rho_total - c.beta) / c.Lambda) * n
            + float(np.sum(c.lambda_i * precursors))
        )
        derivatives[self.I_CI] = (c.beta_i / c.Lambda) * n - c.lambda_i * precursors
        derivatives[self.I_DI] = c.decay_frac * n - c.decay_lambda * decay_groups

        decay_fraction = float(np.sum(c.decay_lambda * decay_groups))
        generated_power = c.Pnom_MW * (c.prompt_frac * n + decay_fraction)

        pump = max(0.0, controls.pump_pct / 100.0)
        natural_circulation = 0.035 + 0.08 * self.clamp(mass, 0.0, 1.0)
        flow_effective = max(natural_circulation, pump * math.sqrt(max(mass, 0.02)))
        if mass >= 0.75:
            coverage = 1.0
        elif mass >= 0.35:
            coverage = 0.20 + 0.80 * (mass - 0.35) / 0.40
        else:
            coverage = max(0.04, 0.20 * mass / 0.35)

        Kcc, boiling_demand, regime, chf_ratio = self.boiling_heat_transfer(
            y, flow_effective, coverage,
            controls.hot_channel_min_dnbr if controls.hot_channel_coupling else float("nan"),
        )
        Qfc = c.Kfc * (fuel_temperature - clad_temperature)
        Qcc = Kcc * (clad_temperature - coolant_temperature)

        sg = max(0.0, controls.sg_pct / 100.0)
        afw = max(0.0, controls.afw_pct / 100.0)
        sg_effective = min(1.40, sg + 0.65 * afw)
        Ksg = c.Ksg_nom * sg_effective * (0.20 + 0.80 * flow_effective) * max(
            0.05, min(1.2, mass)
        )
        Qsg = max(0.0, Ksg * (coolant_temperature - c.Tsink))

        automatic_eccs = 0.0
        thermal_limit_temperature = clad_temperature
        if controls.hot_channel_coupling and np.isfinite(controls.hot_channel_peak_clad_C):
            thermal_limit_temperature = max(
                thermal_limit_temperature, controls.hot_channel_peak_clad_C
            )
        if controls.auto_eccs:
            if np.isfinite(controls.auto_eccs_demand):
                automatic_eccs = self.clamp(controls.auto_eccs_demand, 0.0, 1.0)
            else:
                if (pressure < 12.0 and mass < 0.92) or thermal_limit_temperature > 450.0:
                    automatic_eccs = max(automatic_eccs, 0.35)
                if (
                    controls.hot_channel_coupling
                    and np.isfinite(controls.hot_channel_min_dnbr)
                    and controls.hot_channel_min_dnbr <= 1.0
                ):
                    automatic_eccs = max(automatic_eccs, 0.85)
                if pressure < 4.5 and mass < 1.05:
                    automatic_eccs = max(automatic_eccs, 0.85)
                if pressure < 2.0 and mass < 1.10:
                    automatic_eccs = 1.0
        eccs = max(controls.eccs_pct / 100.0, automatic_eccs)

        break_fraction = max(0.0, controls.break_pct / 100.0)
        porv_fraction = max(0.0, controls.porv_pct / 100.0)
        pressure_head = math.sqrt(max(pressure - 0.10, 0.0))
        break_out = c.break_coeff * break_fraction * pressure_head
        porv_out = c.porv_coeff * porv_fraction * pressure_head
        saturation_temperature = self.properties.saturation_temperature(pressure)
        boiling_fraction = self.clamp(
            (coolant_temperature - (saturation_temperature - 5.0)) / 15.0, 0.0, 1.0
        )
        evaporation_power = boiling_fraction * max(
            0.0, min(boiling_demand, Qcc - 0.5 * Qsg)
        )
        evaporation_out = evaporation_power / (c.Ccool * c.latent_heat_equiv_C)
        eccs_in = c.eccs_coeff * eccs * self.pressure_eccs_factor(pressure)

        total_out = break_out + porv_out + evaporation_out
        if mass <= 0.05 and eccs_in < total_out:
            scale = eccs_in / max(total_out, 1.0e-12)
            break_out *= scale
            porv_out *= scale
            evaporation_out *= scale
            total_out = eccs_in
        elif mass >= 1.20 and eccs_in > total_out:
            eccs_in = total_out

        rhr = max(0.0, controls.rhr_pct / 100.0)
        rhr_available = self.clamp((3.5 - pressure) / 2.5, 0.0, 1.0)
        Qrhr = 1800.0 * rhr * rhr_available * max(
            0.0, (coolant_temperature - 60.0) / 280.0
        )

        derivatives[self.I_TF] = (generated_power - Qfc) / c.Cfuel
        derivatives[self.I_TCL] = (Qfc - Qcc) / c.Cclad
        liquid_h = c.Ccool * max(0.0, coolant_temperature - c.coolant_energy_reference_C)
        injection_h = c.Ccool * max(
            0.0, c.eccs_temp_C - c.coolant_energy_reference_C
        )
        flash_quality = self.clamp(void + boiling_fraction * 0.20, 0.0, 1.0)
        discharge_h = liquid_h + c.Ccool * c.latent_heat_equiv_C * flash_quality
        steam_h = liquid_h + c.Ccool * c.latent_heat_equiv_C
        derivatives[self.I_UCOOL] = (
            Qcc - Qsg - Qrhr + eccs_in * injection_h
            - (break_out + porv_out) * discharge_h
            - evaporation_out * steam_h
        )
        derivatives[self.I_M] = eccs_in - break_out - porv_out - evaporation_out

        equilibrium_void = boiling_fraction * self.clamp(
            evaporation_power / max(Qcc, 1.0), 0.0, 0.85
        )
        derivatives[self.I_VOID] = (equilibrium_void - void) / 2.5

        target_prz = c.pressure_reference_temperature_C + 0.55 * (
            coolant_temperature - c.TrefCool
        ) + 45.0 * (mass - 1.0)
        derivatives[self.I_TPRZ] = (
            (target_prz - float(y[self.I_TPRZ])) / c.pressurizer_tau
            - 18.0 * break_fraction * pressure_head
            - 28.0 * porv_fraction * pressure_head
            - 13.0 * max(0.0, controls.spray_pct / 100.0)
            + 7.0 * max(0.0, controls.heater_pct / 100.0)
            + 12.0 * eccs_in
        )

        return derivatives, StepDiagnostics(
            decay_fraction, rho_total, flow_effective, regime, chf_ratio, eccs,
            break_out, porv_out, evaporation_out,
        )

    def project(self, vector: np.ndarray) -> np.ndarray:
        c = self.c
        y = np.asarray(vector, dtype=float).copy()
        y[self.I_N] = self.clamp(float(y[self.I_N]), 0.0, 2.5)
        y[self.I_CI] = np.maximum(y[self.I_CI], 0.0)
        y[self.I_DI] = np.maximum(y[self.I_DI], 0.0)
        y[self.I_TF] = self.clamp(float(y[self.I_TF]), 20.0, 2800.0)
        y[self.I_TCL] = self.clamp(float(y[self.I_TCL]), 20.0, 2200.0)
        y[self.I_M] = self.clamp(float(y[self.I_M]), 0.05, 1.20)
        y[self.I_VOID] = self.clamp(float(y[self.I_VOID]), 0.0, 0.95)
        y[self.I_TPRZ] = self.clamp(
            float(y[self.I_TPRZ]),
            self.minimum_pressurizer_temperature,
            self.maximum_pressurizer_temperature,
        )
        y[self.I_UCOOL] = max(0.0, float(y[self.I_UCOOL]))
        mass, temperature, _, _ = self.unpack_derived(y)
        y[self.I_UCOOL] = c.Ccool * mass * (temperature - c.coolant_energy_reference_C)
        return y

    def step(self, state: Any, controls: ControlInputs, dt: float) -> StepDiagnostics:
        if not np.isfinite(dt) or dt <= 0.0:
            raise ValueError("dt must be finite and positive")
        y0 = self.pack(state)
        k1, _ = self.rhs(state.t, y0, controls)
        k2, _ = self.rhs(state.t + 0.5 * dt, y0 + 0.5 * dt * k1, controls)
        k3, _ = self.rhs(state.t + 0.5 * dt, y0 + 0.5 * dt * k2, controls)
        k4, _ = self.rhs(state.t + dt, y0 + dt * k3, controls)
        final = self.project(y0 + dt * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0)
        _, diagnostics = self.rhs(state.t + dt, final, controls)

        state.n = float(final[self.I_N])
        state.Ci = final[self.I_CI].copy()
        state.Di = final[self.I_DI].copy()
        state.Tf = float(final[self.I_TF])
        state.Tcl = float(final[self.I_TCL])
        state.Ucool = float(final[self.I_UCOOL])
        state.M = float(final[self.I_M])
        state.void_fraction = float(final[self.I_VOID])
        state.Tprz = float(final[self.I_TPRZ])
        _, state.Tc, state.P, _ = self.unpack_derived(final)
        state.boiling_regime = diagnostics.boiling_regime
        state.chf_ratio = diagnostics.chf_ratio
        state.t += dt
        return diagnostics
