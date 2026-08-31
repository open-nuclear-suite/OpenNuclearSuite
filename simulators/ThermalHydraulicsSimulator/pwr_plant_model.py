"""Dedicated PWR plant-model contract for the teaching simulator.

P0-1 intentionally preserves the established reduced-order equations while
giving subsequent PWR work a plant-specific module and stable public types.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

import numpy as np

from thermal_hydraulics_engine import (
    PWRControlInputs,
    PWRStepDiagnostics,
    ThermalHydraulicsEngine,
)


class PWRPlantModel(ThermalHydraulicsEngine):
    """Reduced-order PWR engine behind the common plant-model boundary."""

    def initialize_state(self, state: Any) -> None:
        """Initialize the resolved primary-loop and steam-generator stores."""
        c = self.c
        state.pwr_core_inventory_fraction = c.pwr_core_inventory_share * state.M
        state.pwr_hot_leg_inventory_fraction = c.pwr_hot_leg_inventory_share * state.M
        state.pwr_cold_leg_inventory_fraction = c.pwr_cold_leg_inventory_share * state.M
        prz = c.pwr_pressurizer_inventory_share * state.M
        state.pwr_pressurizer_liquid_inventory_fraction = 0.875 * prz
        state.pwr_pressurizer_steam_inventory_fraction = 0.125 * prz
        state.pwr_core_temperature_C = state.Tc
        state.pwr_hot_leg_temperature_C = state.Tc + 0.5 * c.pwr_nominal_core_delta_C
        state.pwr_cold_leg_temperature_C = state.Tc - 0.5 * c.pwr_nominal_core_delta_C
        state.pwr_primary_flow_fraction = 1.0
        state.pwr_pump_head_m = c.pwr_rcp_shutoff_head_m
        state.pwr_buoyancy_head_m = 0.0
        state.pwr_loop_loss_head_m = c.pwr_loop_loss_head_m
        state.pwr_secondary_mass_kg = c.pwr_secondary_inventory_kg
        state.pwr_secondary_pressure_mpa = c.pwr_secondary_reference_pressure_mpa
        sat = self.properties.saturation_at_pressure(state.pwr_secondary_pressure_mpa)
        quality = c.pwr_secondary_vapor_mass_fraction
        state.pwr_secondary_energy_MJ = state.pwr_secondary_mass_kg * (
            (1.0 - quality) * sat.uf_kj_kg + quality * sat.ug_kj_kg
        ) / 1000.0
        self._publish_primary_component_energy(state)
        if c.pwr_axial_node_count != 4:
            raise ValueError("the reduced PWR axial model requires four zones")
        z = (np.arange(c.pwr_axial_node_count, dtype=float) + 0.5) / c.pwr_axial_node_count
        base = np.sin(math.pi * z)
        state.pwr_axial_power_fraction = base / np.sum(base)
        vapor = np.cumsum(state.pwr_axial_power_fraction)
        state.pwr_axial_vapor_fraction = vapor / np.sum(vapor)
        state.pwr_axial_void_fraction = self._axial_voids(
            state.void_fraction, state.pwr_axial_vapor_fraction
        )
        state.pwr_axial_peak_node = int(np.argmax(state.pwr_axial_power_fraction)) + 1
        state.pwr_axial_spatial_void_signal = self._spatial_void_signal(
            state.pwr_axial_void_fraction
        )
        state.pwr_components_initialized = True

    @staticmethod
    def _normalized(values: Any) -> Any:
        values = np.maximum(np.asarray(values, dtype=float), 1.0e-12)
        return values / float(np.sum(values))

    def _axial_voids(self, total_void: float, vapor_fraction: Any) -> Any:
        shares = self._normalized(vapor_fraction)
        local = np.maximum(0.0, float(total_void)) * shares * shares.size
        return np.clip(local, 0.0, 0.95)

    @staticmethod
    def _spatial_void_signal(axial_void: Any) -> float:
        importance = np.array([0.55, 1.00, 1.00, 0.55], dtype=float)
        return float(np.dot(importance, axial_void) / np.sum(importance))

    def _advance_axial_state(
        self, state: Any, rod_pct: float, dt: float,
    ) -> None:
        c = self.c
        power = self._normalized(state.pwr_axial_power_fraction)
        vapor = self._normalized(state.pwr_axial_vapor_fraction)
        axial_void = self._axial_voids(state.void_fraction, vapor)
        z = (np.arange(c.pwr_axial_node_count, dtype=float) + 0.5) / c.pwr_axial_node_count
        base = np.sin(math.pi * z)
        base /= np.sum(base)
        rod = self.clamp(float(rod_pct) / 100.0, 0.0, 1.0)
        top_entry_weight = np.array([0.10, 0.35, 0.70, 1.00], dtype=float)
        target = base * (1.0 - 0.85 * rod * top_entry_weight)
        target *= np.exp(-c.pwr_axial_void_shape_feedback * axial_void)
        target = self._normalized(target)
        power_alpha = 1.0 - math.exp(-dt / c.pwr_axial_power_shape_tau_s)
        power = self._normalized(power + power_alpha * (target - power))
        vapor_target = self._normalized(np.cumsum(power))
        transport_tau = c.pwr_axial_void_transport_tau_s / max(
            state.pwr_primary_flow_fraction, 0.08
        )
        vapor_alpha = 1.0 - math.exp(-dt / transport_tau)
        vapor = self._normalized(vapor + vapor_alpha * (vapor_target - vapor))
        state.pwr_axial_power_fraction = power
        state.pwr_axial_vapor_fraction = vapor
        state.pwr_axial_void_fraction = self._axial_voids(state.void_fraction, vapor)
        state.pwr_axial_peak_node = int(np.argmax(power)) + 1
        state.pwr_axial_spatial_void_signal = self._spatial_void_signal(
            state.pwr_axial_void_fraction
        )

    def _publish_primary_component_energy(self, state: Any) -> None:
        """Partition aggregate primary energy without creating or losing energy."""
        c = self.c
        reference = c.coolant_energy_reference_C
        masses = (
            state.pwr_core_inventory_fraction,
            state.pwr_hot_leg_inventory_fraction,
            state.pwr_cold_leg_inventory_fraction,
            state.pwr_pressurizer_liquid_inventory_fraction,
            state.pwr_pressurizer_steam_inventory_fraction,
        )
        temperatures = (
            state.pwr_core_temperature_C,
            state.pwr_hot_leg_temperature_C,
            state.pwr_cold_leg_temperature_C,
            state.Tc,
            state.Tc + c.latent_heat_equiv_C,
        )
        raw = [c.Ccool * mass * max(temp - reference, 1.0e-6)
               for mass, temp in zip(masses, temperatures)]
        scale = state.Ucool / max(sum(raw), 1.0e-12)
        names = (
            "pwr_core_energy_MJ", "pwr_hot_leg_energy_MJ",
            "pwr_cold_leg_energy_MJ", "pwr_pressurizer_liquid_energy_MJ",
            "pwr_pressurizer_steam_energy_MJ",
        )
        for name, energy in zip(names, raw):
            setattr(state, name, energy * scale)

    def _advance_loop_flow(self, state: Any, pump_pct: float, dt: float) -> None:
        c = self.c
        speed = self.clamp(float(pump_pct) / 100.0, 0.0, 1.2)
        flow = self.clamp(state.pwr_primary_flow_fraction, 0.025, 1.4)
        pump_head = c.pwr_rcp_shutoff_head_m * speed * speed
        delta_t = state.pwr_hot_leg_temperature_C - state.pwr_cold_leg_temperature_C
        buoyancy_head = c.pwr_natural_circulation_head_per_C_m * max(
            delta_t - c.pwr_nominal_core_delta_C, 0.0
        )
        loss_head = c.pwr_loop_loss_head_m * flow * flow
        acceleration = (pump_head + buoyancy_head - loss_head) / (
            c.pwr_rcp_shutoff_head_m * c.pwr_loop_flow_tau_s
        )
        state.pwr_primary_flow_fraction = self.clamp(flow + acceleration * dt, 0.025, 1.4)
        state.pwr_pump_head_m = pump_head
        state.pwr_buoyancy_head_m = buoyancy_head
        state.pwr_loop_loss_head_m = loss_head

    def _advance_primary_components(self, state: Any, old_prz: float, dt: float) -> None:
        c = self.c
        prz_target = self.clamp(
            c.pwr_pressurizer_inventory_share * state.M
            + 0.012 * (state.M - c.Mref) + 0.0015 * (state.P - c.Pref),
            0.025 * state.M, 0.14 * state.M,
        )
        vapor_share = self.clamp(0.125 - 0.01 * (state.P - c.Pref), 0.03, 0.30)
        remaining = max(state.M - prz_target, 0.0)
        base = c.pwr_core_inventory_share + c.pwr_hot_leg_inventory_share + c.pwr_cold_leg_inventory_share
        targets = [
            remaining * c.pwr_core_inventory_share / base,
            remaining * c.pwr_hot_leg_inventory_share / base,
            remaining * c.pwr_cold_leg_inventory_share / base,
            prz_target * (1.0 - vapor_share), prz_target * vapor_share,
        ]
        names = [
            "pwr_core_inventory_fraction", "pwr_hot_leg_inventory_fraction",
            "pwr_cold_leg_inventory_fraction", "pwr_pressurizer_liquid_inventory_fraction",
            "pwr_pressurizer_steam_inventory_fraction",
        ]
        alpha = self.clamp(dt / c.pwr_component_inventory_tau_s, 0.0, 1.0)
        values = [getattr(state, name) + alpha * (target - getattr(state, name))
                  for name, target in zip(names, targets)]
        scale = state.M / max(sum(values), 1.0e-12)
        for name, value in zip(names, values):
            setattr(state, name, max(0.0, value * scale))
        new_prz = (state.pwr_pressurizer_liquid_inventory_fraction
                   + state.pwr_pressurizer_steam_inventory_fraction)
        state.pwr_surge_flow_fraction_s = (new_prz - old_prz) / dt

        rise = c.pwr_nominal_core_delta_C * state.n / max(
            state.pwr_primary_flow_fraction, 0.10
        )
        temp_targets = (state.Tc + rise / 3.0, state.Tc + rise / 2.0, state.Tc - rise / 2.0)
        temp_names = ("pwr_core_temperature_C", "pwr_hot_leg_temperature_C", "pwr_cold_leg_temperature_C")
        for name, target in zip(temp_names, temp_targets):
            setattr(state, name, getattr(state, name) + alpha * (target - getattr(state, name)))
        self._publish_primary_component_energy(state)

    def _advance_secondary(self, state: Any, controls: PWRControlInputs, dt: float) -> None:
        c = self.c
        old_mass = state.pwr_secondary_mass_kg
        old_energy = state.pwr_secondary_energy_MJ
        sat = self.properties.saturation_at_pressure(state.pwr_secondary_pressure_mpa)
        sg = self.clamp(controls.sg_pct / 100.0, 0.0, 1.4)
        afw = self.clamp(controls.afw_pct / 100.0, 0.0, 1.0)
        secondary_demand = sg + 0.65 * afw
        q_sg = max(0.0, c.Ksg_nom * secondary_demand
                   * (0.20 + 0.80 * state.pwr_primary_flow_fraction)
                   * max(0.05, min(1.2, state.M)) * (state.Tc - c.Tsink))
        nominal_steam = c.Pnom_MW * 1000.0 / max(sat.latent_heat_kj_kg, 1.0)
        pressure_factor = math.sqrt(max(state.pwr_secondary_pressure_mpa, 0.1)
                                    / c.pwr_secondary_reference_pressure_mpa)
        steam = nominal_steam * secondary_demand * pressure_factor
        normal_feed = nominal_steam * sg
        auxiliary_feed = 0.65 * nominal_steam * afw
        feed = normal_feed + auxiliary_feed
        auxiliary_feed_h = max(100.0, sat.hf_kj_kg - 450.0)
        mass_rate = feed - steam
        energy_rate = (
            q_sg + normal_feed * sat.hf_kj_kg / 1000.0
            + auxiliary_feed * auxiliary_feed_h / 1000.0
            - steam * sat.hg_kj_kg / 1000.0
        )
        state.pwr_secondary_mass_kg = self.clamp(
            old_mass + mass_rate * dt, 0.20 * c.pwr_secondary_inventory_kg,
            1.30 * c.pwr_secondary_inventory_kg,
        )
        state.pwr_secondary_energy_MJ = max(1.0, old_energy + energy_rate * dt)
        quality = c.pwr_secondary_vapor_mass_fraction
        equilibrium = state.pwr_secondary_mass_kg * (
            (1.0 - quality) * sat.uf_kj_kg + quality * sat.ug_kj_kg
        ) / 1000.0
        pressure_rate = (state.pwr_secondary_energy_MJ - equilibrium) / max(
            c.pwr_secondary_pressure_energy_capacity_MJ_MPa * 5.0, 1.0
        )
        state.pwr_secondary_pressure_mpa = self.clamp(
            state.pwr_secondary_pressure_mpa + pressure_rate * dt, 0.1, 10.0
        )
        state.pwr_secondary_steam_flow_kg_s = steam
        state.pwr_secondary_feedwater_flow_kg_s = feed
        state.pwr_secondary_heat_transfer_MW = q_sg
        state.pwr_secondary_mass_residual_kg_s = (
            (state.pwr_secondary_mass_kg - old_mass) / dt - mass_rate
        )
        state.pwr_secondary_energy_residual_MW = (
            (state.pwr_secondary_energy_MJ - old_energy) / dt - energy_rate
        )

    def evaluate_protection(
        self, state: Any, dt: float, pump_pct: float,
        thermal_limit_enabled: bool = True,
    ) -> tuple[bool, str]:
        """Advance independent teaching-scale PWR trip-channel timers."""
        if not math.isfinite(dt) or dt <= 0.0:
            raise ValueError("dt must be finite and positive")
        c = self.c
        pump = max(0.0, float(pump_pct) / 100.0)
        natural_circulation = 0.035 + 0.08 * self.clamp(state.M, 0.0, 1.0)
        flow_fraction = max(
            natural_circulation, pump * math.sqrt(max(state.M, 0.02))
        )
        thermal_signal = thermal_limit_enabled and (
            state.Tcl >= c.pwr_rps_high_clad_C
            or (
                math.isfinite(state.hot_peak_clad_C)
                and state.hot_peak_clad_C >= c.pwr_rps_high_clad_C
            )
            or (
                state.hot_dnbr_valid_nodes > 0
                and math.isfinite(state.hot_min_dnbr)
                and state.hot_min_dnbr <= c.pwr_rps_low_dnbr
            )
        )
        channels = (
            ("high_flux", state.n >= c.pwr_rps_high_flux_fraction,
             c.pwr_rps_high_flux_delay_s, "High neutron flux"),
            ("high_pressure", state.P >= c.pwr_rps_high_pressure_mpa,
             c.pwr_rps_high_pressure_delay_s, "High primary pressure"),
            ("low_inventory", state.M <= c.pwr_rps_low_inventory_fraction,
             c.pwr_rps_low_inventory_delay_s, "Low primary inventory"),
            ("low_flow", (
                flow_fraction <= c.pwr_rps_low_flow_fraction
                and state.n >= c.pwr_rps_low_flow_power_permissive
            ), c.pwr_rps_low_flow_delay_s, "Low primary flow"),
            ("thermal", thermal_signal,
             c.pwr_rps_thermal_delay_s, "Fuel thermal limit"),
        )
        causes = []
        active = []
        for name, signal, delay, cause in channels:
            timer_name = f"pwr_rps_{name}_timer_s"
            timer = getattr(state, timer_name) + dt if signal else 0.0
            setattr(state, timer_name, timer)
            if signal:
                active.append(cause)
            if timer >= delay:
                causes.append(cause)
        state.pwr_active_protection_channels = " / ".join(active) if active else "None"
        state.pwr_protection_demand = bool(causes)
        if causes and state.pwr_trip_cause == "None":
            state.pwr_trip_cause = " / ".join(causes)
        return bool(causes), " / ".join(causes) if causes else "None"

    def _effective_safety_controls(
        self, state: Any, controls: PWRControlInputs, dt: float,
    ) -> PWRControlInputs:
        """Advance automatic injection timers/latches once per completed step."""
        automatic_enabled = controls.auto_eccs
        if automatic_enabled:
            demand = (
                (math.isfinite(controls.auto_eccs_demand)
                 and controls.auto_eccs_demand > 0.0)
                or (state.P < 12.0 and state.M < 0.92)
                or state.Tcl > 450.0
                or (math.isfinite(state.hot_peak_clad_C)
                    and state.hot_peak_clad_C > 450.0)
                or (state.hot_dnbr_valid_nodes > 0
                    and math.isfinite(state.hot_min_dnbr)
                    and state.hot_min_dnbr <= 1.0)
            )
            signals = {
                "hpsi": demand and state.P < self.c.pwr_hpsi_shutoff_pressure_mpa,
                "lpsi": demand and state.P < self.c.pwr_lpsi_shutoff_pressure_mpa,
                "recirculation": (
                    demand and state.P < self.c.pwr_recirculation_shutoff_pressure_mpa
                    and controls.break_pct > 0.0 and state.M < 0.85
                ),
            }
            delays = {
                "hpsi": self.c.pwr_hpsi_start_delay_s,
                "lpsi": self.c.pwr_lpsi_start_delay_s,
                "recirculation": self.c.pwr_recirculation_start_delay_s,
            }
            for name, signal in signals.items():
                timer_name = f"pwr_{name}_demand_timer_s"
                timer = getattr(state, timer_name) + dt if signal else 0.0
                setattr(state, timer_name, timer)
                if timer >= delays[name]:
                    setattr(state, f"pwr_{name}_latched", True)

            recovered = (
                controls.break_pct <= 0.0
                and state.M >= self.c.pwr_safety_reset_inventory_fraction
                and state.Tcl < 450.0
            )
            state.pwr_safety_reset_timer_s = (
                state.pwr_safety_reset_timer_s + dt if recovered else 0.0
            )
            if state.pwr_safety_reset_timer_s >= self.c.pwr_safety_reset_delay_s:
                state.pwr_hpsi_latched = False
                state.pwr_lpsi_latched = False
                state.pwr_recirculation_latched = False

        # Automatic demand has now been converted to component latches. Disable
        # the legacy RHS auto path so it cannot bypass the declared delays.
        return replace(
            controls,
            hpsi_pct=max(
                controls.hpsi_pct,
                100.0 if automatic_enabled and state.pwr_hpsi_latched else 0.0,
            ),
            lpsi_pct=max(
                controls.lpsi_pct,
                100.0 if automatic_enabled and state.pwr_lpsi_latched else 0.0,
            ),
            recirculation_pct=max(
                controls.recirculation_pct,
                100.0 if automatic_enabled and state.pwr_recirculation_latched else 0.0,
            ),
            accumulator_inventory_fraction=state.pwr_accumulator_inventory_fraction,
            auto_eccs=False,
            auto_eccs_demand=float("nan"),
        )

    def step(
        self, state: Any, controls: PWRControlInputs, dt: float,
    ) -> PWRStepDiagnostics:
        if not state.pwr_components_initialized:
            self.initialize_state(state)
        self._advance_loop_flow(state, controls.pump_pct, dt)
        self._advance_axial_state(state, controls.rod_pct, dt)
        old_prz = (state.pwr_pressurizer_liquid_inventory_fraction
                   + state.pwr_pressurizer_steam_inventory_fraction)
        secondary_available = self.clamp(
            (state.pwr_secondary_mass_kg / self.c.pwr_secondary_inventory_kg - 0.20) / 0.60,
            0.0, 1.0,
        )
        hydraulic = replace(
            controls,
            trim_pcm=controls.trim_pcm + self.c.pwr_axial_void_reactivity_pcm_per_fraction * (
                state.pwr_axial_spatial_void_signal - state.void_fraction
            ),
            sg_pct=controls.sg_pct * secondary_available,
            afw_pct=controls.afw_pct * secondary_available,
        )
        effective = self._effective_safety_controls(state, hydraulic, dt)
        diagnostics = super().step(state, effective, dt)
        capacity = max(
            self.c.pwr_accumulator_inventory_fraction_of_primary, 1.0e-12
        )
        state.pwr_accumulator_inventory_fraction = self.clamp(
            state.pwr_accumulator_inventory_fraction
            - diagnostics.pwr_accumulator_in_fraction_s * dt / capacity,
            0.0, 1.0,
        )
        self._advance_primary_components(state, old_prz, dt)
        self._advance_secondary(state, effective, dt)
        return diagnostics


__all__ = ["PWRControlInputs", "PWRPlantModel", "PWRStepDiagnostics"]
