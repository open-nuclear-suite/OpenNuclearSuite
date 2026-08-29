"""Independent reduced-order BWR vessel model for classroom transients."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from steam_properties import SteamTables
from thermal_hydraulics_engine import StepDiagnostics


@dataclass(frozen=True)
class BWRControlInputs:
    rod_pct: float = 0.0
    trim_pcm: float = 0.0
    recirc_pct: float = 100.0
    feedwater_pct: float = 100.0
    main_steam_pct: float = 100.0
    srv_pct: float = 0.0
    msiv_pct: float = 100.0
    bypass_pct: float = 0.0
    rcic_pct: float = 0.0
    hpci_pct: float = 0.0
    ads_pct: float = 0.0
    lpci_pct: float = 0.0
    core_spray_pct: float = 0.0
    shutdown_cooling_pct: float = 0.0
    bwr_break_pct: float = 0.0
    auto_bwr_safety: bool = True
    rcic_available: bool = True
    hpci_available: bool = True
    ads_available: bool = True
    lpci_available: bool = True
    core_spray_available: bool = True
    critical_power_ratio: float = float("nan")
    critical_power_valid_nodes: int = 0


@dataclass(frozen=True)
class BWRStepDiagnostics(StepDiagnostics):
    """Exact boundary flows and balance closure for one BWR RHS evaluation."""

    steam_generation_kg_s: float
    main_steam_flow_kg_s: float
    bypass_flow_kg_s: float
    srv_flow_kg_s: float
    rcic_steam_use_kg_s: float
    feedwater_flow_kg_s: float
    rcic_flow_kg_s: float
    hpci_flow_kg_s: float
    lpci_flow_kg_s: float
    core_spray_flow_kg_s: float
    break_flow_kg_s: float
    break_critical_pressure_mpa: float
    break_mass_flux_kg_m2_s: float
    break_choked: bool
    rcic_head_margin_mpa: float
    hpci_head_margin_mpa: float
    lpci_head_margin_mpa: float
    core_spray_head_margin_mpa: float
    shutdown_cooling_MW: float
    mass_balance_residual_kg_s: float
    energy_balance_residual_MW: float
    pump_head_m: float
    buoyancy_head_m: float
    friction_head_m: float
    core_friction_head_m: float
    single_phase_loss_head_m: float
    acceleration_head_m: float
    two_phase_friction_multiplier: float
    vessel_pool_mass_residual_kg_s: float
    vessel_pool_energy_residual_MW: float
    core_void_fraction: float
    coolant_heat_transfer_factor: float
    heat_transfer_regime: str
    critical_power_coupled: bool


class BWRPlantModel:
    """Coupled core, downcomer, and saturated steam-dome balance model.

    Liquid and vapor masses and stored energies are integrated explicitly. The
    steam-dome pressure is obtained from total vessel-volume closure and saturated
    vapor specific volume. This remains a reduced-order teaching model, but it
    no longer routes BWR behavior through the PWR pressurizer/steam-generator
    equations.
    """

    N_PRECURSORS = 6
    N_DECAY_GROUPS = 3
    I_N = 0
    I_CI = slice(1, 7)
    I_DI = slice(7, 10)
    I_TF = 10
    I_TCL = 11
    I_MCORE = 12
    I_UCORE = 13
    I_MDC = 14
    I_UDC = 15
    I_MUPPER = 16
    I_UUPPER = 17
    I_MSEPARATOR = 18
    I_USEPARATOR = 19
    I_MCORE_VAPOR = 20
    I_UCORE_VAPOR = 21
    I_MSTEAM = 22
    I_USTEAM = 23
    I_VOID = 24
    I_FLOW = 25
    I_POOL_MASS = 26
    I_POOL_ENERGY = 27
    I_REFLEG_T = 28
    I_AXIAL_POWER = slice(29, 33)
    I_AXIAL_VAPOR = slice(33, 37)

    def __init__(self, constants: Any, properties: SteamTables | None = None) -> None:
        self.c = constants
        self.properties = properties or SteamTables()
        self._p_low, self._p_high = 0.10, 17.50
        self.reference_saturation = self.properties.saturation_at_pressure(constants.Pref)
        # At equilibrium, reactor heat supplies both feedwater sensible heating
        # to saturation and vaporization. This reproduces the benchmark rated
        # steam flow without an independently tuned flow constant.
        self.reference_steam_flow_kg_s = constants.Pnom_MW / (
            (self.reference_saturation.latent_heat_kj_kg
             + constants.bwr_feedwater_subcooling_kJ_kg) / 1000.0
        )
        reference_quality = self.reference_steam_flow_kg_s / constants.bwr_reference_core_flow_kg_s
        self.reference_flow_quality = reference_quality
        sat = self.reference_saturation
        reference_slip = 1.20+0.80*math.sqrt(reference_quality)
        self.reference_void_fraction = (
            reference_quality * sat.vg_m3_kg
            / (reference_quality * sat.vg_m3_kg
               + reference_slip*(1.0-reference_quality) * sat.vf_m3_kg)
        )
        self.reference_quality = reference_quality
        self.reference_two_phase_multiplier = self._lottes_flinn_multiplier(
            reference_quality, self.reference_void_fraction
        )
        if constants.bwr_axial_node_count != 4:
            raise ValueError("the current reduced axial contract requires four nodes")
        z=(np.arange(4,dtype=float)+0.5)/4.0
        base=np.sin(math.pi*z); self.base_axial_power_fraction=base/np.sum(base)
        cumulative=np.cumsum(self.base_axial_power_fraction)
        self.base_axial_vapor_fraction=cumulative/np.sum(cumulative)
        self.axial_importance=np.sin(math.pi*z)
        self.reference_axial_void=np.full(4,self.reference_void_fraction)
        self.reference_spatial_void=self.reference_void_fraction

    @staticmethod
    def clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    @staticmethod
    def _lottes_flinn_multiplier(quality: float, void_fraction: float) -> float:
        """Liquid-only two-phase friction multiplier phi_LO^2."""
        x = max(0.0, min(0.95, quality))
        alpha = max(0.0, min(0.95, void_fraction))
        return max(1.0, (1.0-x)/max(1.0-alpha, 0.05))

    def _recirculation_heads(
        self, flow_fraction: float, speed_fraction: float, void_fraction: float,
        sat: Any, downcomer_density_kg_m3: float,
    ) -> tuple[float, float, float, float, float, float]:
        """Return pump, driving, core, other, acceleration heads and phi_LO^2."""
        c = self.c
        f = max(flow_fraction, 0.0)
        speed = self.clamp(speed_fraction, 0.0, 1.20)
        pump_curve_drop = c.bwr_pump_shutoff_head_m-c.bwr_pump_reference_head_m
        pump_head = max(0.0, c.bwr_pump_shutoff_head_m*speed**2-pump_curve_drop*f**2)

        alpha = self.clamp(void_fraction, 0.0, 0.95)
        rho_l, rho_g = 1.0/sat.vf_m3_kg, 1.0/sat.vg_m3_kg
        mixture_density = (1.0-alpha)*rho_l+alpha*rho_g
        reference_mixture_density = (
            (1.0-self.reference_void_fraction)/self.reference_saturation.vf_m3_kg
            +self.reference_void_fraction/self.reference_saturation.vg_m3_kg
        )
        reference_density_difference = max(
            1.0/self.reference_saturation.vf_m3_kg-reference_mixture_density, 1.0
        )
        effective_elevation = (
            c.bwr_reference_buoyancy_head_m
            *(1.0/self.reference_saturation.vf_m3_kg)/reference_density_difference
        )
        buoyancy_head = max(
            0.0, effective_elevation*(downcomer_density_kg_m3-mixture_density)
            /max(downcomer_density_kg_m3,1.0)
        )

        quality = alpha*rho_g/max(alpha*rho_g+(1.0-alpha)*rho_l, 1.0e-9)
        phi_lo2 = self._lottes_flinn_multiplier(quality, alpha)
        core_friction = (
            c.bwr_core_friction_head_ref_m*f*abs(f)
            *phi_lo2/max(self.reference_two_phase_multiplier,1.0e-9)
            *(1.0/self.reference_saturation.vf_m3_kg)/max(rho_l,1.0)
        )
        single_phase_loss = (
            c.bwr_single_phase_loss_head_ref_m*f*abs(f)
            *(1.0/self.reference_saturation.vf_m3_kg)
            /max(downcomer_density_kg_m3,1.0)
        )
        specific_volume_rise = max(
            0.0, 1.0/max(mixture_density,1.0)-1.0/max(downcomer_density_kg_m3,1.0)
        )
        reference_specific_volume_rise = max(
            1.0/reference_mixture_density-self.reference_saturation.vf_m3_kg, 1.0e-8
        )
        acceleration_head = (
            c.bwr_acceleration_head_ref_m*f*abs(f)
            *specific_volume_rise/reference_specific_volume_rise
        )
        return (pump_head,buoyancy_head,core_friction,single_phase_loss,
                acceleration_head,phi_lo2)

    def _injection_curve(
        self, command: float, runout_flow_kg_s: float,
        shutoff_head_mpa: float, vessel_pressure_mpa: float,
        driver_fraction: float = 1.0,
    ) -> tuple[float, float]:
        """Solve a generic quadratic pump curve against vessel backpressure.

        Delta-p = Delta-p_shutoff * (1 - (Q/Q_runout)^2).  Command represents
        admitted/available capacity; the pressure head remains a pump property.
        """
        suction_pressure = self.c.bwr_suppression_pool_pressure_mpa
        required_head = max(0.0, vessel_pressure_mpa-suction_pressure)
        effective_shutoff = shutoff_head_mpa*self.clamp(driver_fraction, 0.0, 1.0)
        margin = effective_shutoff-required_head
        if command <= 0.0 or margin <= 0.0 or effective_shutoff <= 0.0:
            return 0.0, margin
        flow_fraction = math.sqrt(self.clamp(margin/effective_shutoff, 0.0, 1.0))
        return runout_flow_kg_s*command*flow_fraction, margin

    def _hem_break_flux(
        self, upstream_pressure_mpa: float, downstream_pressure_mpa: float,
        upstream_quality: float = 0.0,
    ) -> tuple[float, float, bool]:
        """Return HEM flashing-nozzle mass flux, critical pressure, and choke flag.

        Saturated phases share velocity and remain in thermal equilibrium.  An
        isentropic expansion is evaluated from stagnation pressure to candidate
        throat pressures; the maximum rho*sqrt(2*(h0-h)) is the critical flux.
        """
        p0 = self.clamp(upstream_pressure_mpa, self._p_low, self._p_high)
        p2 = self.clamp(downstream_pressure_mpa, self._p_low, p0)
        if p0 <= p2+1.0e-9:
            return 0.0, p0, False
        pressures = np.geomspace(p2, p0, 64)
        sats = [self.properties.saturation_at_pressure(float(p)) for p in pressures]
        # Set saturated-liquid entropy at p0 to an arbitrary zero datum, then
        # integrate ds=(dh-v dp)/T along the saturation line.
        sf = np.zeros(len(pressures))
        for i in range(len(pressures)-2, -1, -1):
            lo, hi = sats[i], sats[i+1]
            temperature_k = 0.5*(lo.temperature_C+hi.temperature_C)+273.15
            mean_v = 0.5*(lo.vf_m3_kg+hi.vf_m3_kg)
            dh = lo.hf_kj_kg-hi.hf_kj_kg
            dp_kpa = (lo.pressure_mpa-hi.pressure_mpa)*1000.0
            sf[i] = sf[i+1]+(dh-mean_v*dp_kpa)/temperature_k
        upstream = sats[-1]
        x0 = self.clamp(upstream_quality, 0.0, 1.0)
        s0 = x0*upstream.latent_heat_kj_kg/(upstream.temperature_C+273.15)
        h0 = upstream.hf_kj_kg+x0*upstream.latent_heat_kj_kg
        fluxes = []
        for sat, sf_value in zip(sats, sf):
            sfg = sat.latent_heat_kj_kg/(sat.temperature_C+273.15)
            quality = self.clamp((s0-sf_value)/max(sfg, 1.0e-9), 0.0, 1.0)
            enthalpy = sat.hf_kj_kg+quality*sat.latent_heat_kj_kg
            density = 1.0/(sat.vf_m3_kg+quality*(sat.vg_m3_kg-sat.vf_m3_kg))
            velocity = math.sqrt(max(0.0, 2.0*(h0-enthalpy)*1000.0))
            fluxes.append(density*velocity)
        critical_index = int(np.argmax(fluxes))
        choked = critical_index > 0
        selected_index = critical_index if choked else 0
        return fluxes[selected_index], float(pressures[critical_index]), choked

    def initialize_state(self, state: Any) -> None:
        c, sat = self.c, self.reference_saturation
        state.bwr_core_mass_kg = c.bwr_liquid_inventory_kg * c.bwr_core_inventory_fraction
        state.bwr_downcomer_mass_kg = c.bwr_liquid_inventory_kg * c.bwr_downcomer_inventory_fraction
        state.bwr_upper_plenum_mass_kg = c.bwr_liquid_inventory_kg * c.bwr_upper_plenum_inventory_fraction
        state.bwr_separator_mass_kg = c.bwr_liquid_inventory_kg * c.bwr_separator_inventory_fraction
        state.bwr_core_energy_MJ = state.bwr_core_mass_kg * sat.uf_kj_kg / 1000.0
        downcomer_h = sat.hf_kj_kg
        downcomer_u = sat.uf_kj_kg
        state.bwr_downcomer_energy_MJ = state.bwr_downcomer_mass_kg * downcomer_u / 1000.0
        state.bwr_upper_plenum_energy_MJ = state.bwr_upper_plenum_mass_kg * sat.uf_kj_kg / 1000.0
        state.bwr_separator_energy_MJ = state.bwr_separator_mass_kg * sat.uf_kj_kg / 1000.0
        total_vapor_mass = c.bwr_steam_dome_volume_m3 / sat.vg_m3_kg
        state.bwr_core_vapor_mass_kg = min(
            total_vapor_mass, self.reference_steam_flow_kg_s*c.bwr_core_vapor_residence_s
        )
        state.bwr_steam_mass_kg = total_vapor_mass-state.bwr_core_vapor_mass_kg
        state.bwr_core_vapor_energy_MJ = state.bwr_core_vapor_mass_kg*sat.ug_kj_kg/1000.0
        state.bwr_steam_energy_MJ = state.bwr_steam_mass_kg * sat.ug_kj_kg / 1000.0
        state.bwr_core_flow_fraction = 1.0
        state.bwr_pump_head_m = c.bwr_pump_reference_head_m
        state.bwr_buoyancy_head_m = c.bwr_reference_buoyancy_head_m
        state.bwr_friction_head_m = c.bwr_loop_loss_head_m
        state.bwr_core_friction_head_m = c.bwr_core_friction_head_ref_m
        state.bwr_single_phase_loss_head_m = c.bwr_single_phase_loss_head_ref_m
        state.bwr_acceleration_head_m = c.bwr_acceleration_head_ref_m
        state.bwr_two_phase_friction_multiplier = self.reference_two_phase_multiplier
        state.bwr_axial_power_fraction=self.base_axial_power_fraction.copy()
        state.bwr_axial_vapor_fraction=self.base_axial_vapor_fraction.copy()
        state.bwr_axial_void_fraction=self._axial_voids(
            state.bwr_core_vapor_mass_kg,state.bwr_core_mass_kg,sat,
            state.bwr_axial_vapor_fraction,
        )
        self.reference_axial_void=state.bwr_axial_void_fraction.copy()
        self.reference_spatial_void=self._spatial_void_signal(state.bwr_axial_void_fraction)
        state.bwr_axial_peak_node=int(np.argmax(state.bwr_axial_power_fraction))+1
        state.bwr_steam_flow_kg_s = self.reference_steam_flow_kg_s
        state.bwr_feedwater_flow_kg_s = self.reference_steam_flow_kg_s
        state.bwr_srv_flow_kg_s = 0.0
        state.bwr_liquid_energy_residual_MW = 0.0
        state.bwr_downcomer_temperature_C = sat.temperature_C - (
            sat.hf_kj_kg - downcomer_h
        ) / max(sat.cpf_kj_kgK, 1.0)
        state.bwr_suppression_pool_temperature_C = 35.0
        state.bwr_suppression_pool_mass_kg = c.bwr_pool_mass_kg
        state.bwr_suppression_pool_energy_MJ = c.bwr_pool_mass_kg*c.bwr_pool_cp_kJ_kgK*35.0/1000.0
        state.bwr_collapsed_level_percent = 100.0
        state.bwr_indicated_level_percent = 100.0
        state.bwr_indicated_level_m = c.bwr_level_span_m
        state.bwr_collapsed_level_m = c.bwr_level_span_m
        state.bwr_steam_dome_volume_m3 = c.bwr_steam_dome_volume_m3
        state.bwr_reference_leg_temperature_C = state.bwr_downcomer_temperature_C
        state.M = 1.0
        state.P = c.Pref
        state.Tc = sat.temperature_C
        state.Tprz = sat.temperature_C
        state.void_fraction = (
            state.bwr_core_vapor_mass_kg*sat.vg_m3_kg
            /(state.bwr_core_vapor_mass_kg*sat.vg_m3_kg
              +state.bwr_core_mass_kg*sat.vf_m3_kg)
        )
        self.reference_void_fraction = state.void_fraction
        self.reference_quality = (
            self.reference_void_fraction/sat.vg_m3_kg
            /max(self.reference_void_fraction/sat.vg_m3_kg
                 +(1.0-self.reference_void_fraction)/sat.vf_m3_kg,1.0e-12)
        )
        self.reference_two_phase_multiplier = self._lottes_flinn_multiplier(
            self.reference_quality,self.reference_void_fraction
        )
        state.boiling_regime = "bulk boiling"

    def pressure_from_inventory(self, steam_mass_kg: float, liquid_mass_kg: float) -> float:
        """Solve the saturated vessel volume closure for pressure."""
        vessel_volume = (
            self.c.bwr_steam_dome_volume_m3
            + self.c.bwr_liquid_inventory_kg*self.reference_saturation.vf_m3_kg
        )
        def occupied_volume(pressure: float) -> float:
            sat = self.properties.saturation_at_pressure(pressure)
            return (steam_mass_kg*sat.vg_m3_kg
                    + liquid_mass_kg*self.reference_saturation.vf_m3_kg)
        low, high = self._p_low, self._p_high
        low_residual = occupied_volume(low)-vessel_volume
        if low_residual <= 0.0:
            return low
        if occupied_volume(high)-vessel_volume >= 0.0:
            return high
        for _ in range(36):
            mid = 0.5*(low+high)
            mid_residual = occupied_volume(mid)-vessel_volume
            if low_residual*mid_residual <= 0.0:
                high = mid
            else:
                low, low_residual = mid, mid_residual
        return 0.5*(low+high)

    def equilibrium_from_totals(self, total_mass_kg: float, total_energy_MJ: float):
        """Return the saturated phase split satisfying M, U, and fixed V."""
        c = self.c
        vessel_volume = (
            c.bwr_steam_dome_volume_m3
            + c.bwr_liquid_inventory_kg*self.reference_saturation.vf_m3_kg
        )

        def state_at(pressure: float):
            sat = self.properties.saturation_at_pressure(pressure)
            vapor_mass = (vessel_volume-total_mass_kg*sat.vf_m3_kg)/max(
                sat.vg_m3_kg-sat.vf_m3_kg, 1.0e-12
            )
            vapor_mass = self.clamp(vapor_mass, 0.0, total_mass_kg)
            energy = (
                (total_mass_kg-vapor_mass)*sat.uf_kj_kg
                + vapor_mass*sat.ug_kj_kg
            )/1000.0
            return energy, vapor_mass, sat

        low, high = self._p_low, self._p_high
        low_energy, _, _ = state_at(low)
        high_energy, _, _ = state_at(high)
        if total_energy_MJ <= low_energy:
            pressure = low
        elif total_energy_MJ >= high_energy:
            pressure = high
        else:
            for _ in range(42):
                mid = 0.5*(low+high)
                mid_energy, _, _ = state_at(mid)
                if mid_energy < total_energy_MJ:
                    low = mid
                else:
                    high = mid
            pressure = 0.5*(low+high)
        energy, vapor_mass, sat = state_at(pressure)
        return pressure, sat, total_mass_kg-vapor_mass, vapor_mass, energy-total_energy_MJ

    def equilibrium_from_vector(self, y: np.ndarray):
        mass_indices = (self.I_MCORE, self.I_MDC, self.I_MUPPER, self.I_MSEPARATOR,
                        self.I_MCORE_VAPOR, self.I_MSTEAM)
        energy_indices = (self.I_UCORE, self.I_UDC, self.I_UUPPER, self.I_USEPARATOR,
                          self.I_UCORE_VAPOR, self.I_USTEAM)
        return self.equilibrium_from_totals(
            sum(float(y[index]) for index in mass_indices),
            sum(float(y[index]) for index in energy_indices),
        )

    def pressure_from_steam_mass(self, steam_mass_kg: float) -> float:
        """Compatibility helper at the reference liquid inventory."""
        return self.pressure_from_inventory(steam_mass_kg, self.c.bwr_liquid_inventory_kg)

    def pressure_eccs_factor(self, pressure: float) -> float:
        return self.clamp((8.0 - pressure) / 6.0, 0.05, 1.0)

    def pack(self, state: Any) -> np.ndarray:
        return np.concatenate((
            np.array([state.n]), state.Ci, state.Di,
            np.array([
                state.Tf, state.Tcl,
                state.bwr_core_mass_kg, state.bwr_core_energy_MJ,
                state.bwr_downcomer_mass_kg, state.bwr_downcomer_energy_MJ,
                state.bwr_upper_plenum_mass_kg, state.bwr_upper_plenum_energy_MJ,
                state.bwr_separator_mass_kg, state.bwr_separator_energy_MJ,
                state.bwr_core_vapor_mass_kg, state.bwr_core_vapor_energy_MJ,
                state.bwr_steam_mass_kg, state.bwr_steam_energy_MJ,
                state.void_fraction, state.bwr_core_flow_fraction,
                state.bwr_suppression_pool_mass_kg,
                state.bwr_suppression_pool_energy_MJ,
                state.bwr_reference_leg_temperature_C,
                *state.bwr_axial_power_fraction,
                *state.bwr_axial_vapor_fraction,
            ]),
        )).astype(float)

    def _derived(self, y: np.ndarray):
        pressure, sat, _liquid_mass, _vapor_mass, _residual = self.equilibrium_from_vector(y)
        core_mass = max(float(y[self.I_MCORE]), 1.0)
        dc_mass = max(float(y[self.I_MDC]), 1.0)
        core_u = 1000.0 * float(y[self.I_UCORE]) / core_mass
        dc_u = 1000.0 * float(y[self.I_UDC]) / dc_mass
        core_h = core_u + pressure * 1000.0 * sat.vf_m3_kg
        dc_h = dc_u + pressure * 1000.0 * sat.vf_m3_kg
        dc_temperature = sat.temperature_C - max(0.0, sat.hf_kj_kg - dc_h) / max(sat.cpf_kj_kgK, 1.0)
        return pressure, sat, core_h, dc_h, dc_temperature

    def _axial_voids(
        self, core_vapor_mass: float, core_liquid_mass: float, sat: Any,
        vapor_fractions: np.ndarray,
    ) -> np.ndarray:
        liquid_per_node=max(core_liquid_mass,1.0)/4.0
        vapor=np.maximum(np.asarray(vapor_fractions,dtype=float),0.0)*max(core_vapor_mass,0.0)
        vapor_volume=vapor*sat.vg_m3_kg
        liquid_volume=liquid_per_node*sat.vf_m3_kg
        return np.clip(vapor_volume/np.maximum(vapor_volume+liquid_volume,1.0e-12),0.0,0.95)

    def _spatial_void_signal(self, axial_void: np.ndarray) -> float:
        return float(np.average(axial_void,weights=self.axial_importance))

    def rhs(self, _time_s: float, vector: np.ndarray, controls: BWRControlInputs):
        c = self.c
        y = np.asarray(vector, dtype=float)
        n = max(0.0, float(y[self.I_N]))
        precursors = np.maximum(y[self.I_CI], 0.0)
        decay_groups = np.maximum(y[self.I_DI], 0.0)
        fuel_temperature = self.clamp(float(y[self.I_TF]), 20.0, 2800.0)
        clad_temperature = self.clamp(float(y[self.I_TCL]), 20.0, 2200.0)
        void = self.clamp(float(y[self.I_VOID]), 0.0, 0.90)
        flow_fraction = self.clamp(float(y[self.I_FLOW]), 0.02, 1.20)
        pool_mass = max(float(y[self.I_POOL_MASS]), 1.0)
        pool_temperature = self.clamp(
            1000.0*float(y[self.I_POOL_ENERGY])/(pool_mass*c.bwr_pool_cp_kJ_kgK),
            10.0, 100.0,
        )
        reference_leg_temperature = self.clamp(float(y[self.I_REFLEG_T]), 20.0, 330.0)
        pressure, sat, core_h, dc_h, dc_temperature = self._derived(y)
        axial_power=np.maximum(y[self.I_AXIAL_POWER],0.0)
        axial_power/=max(float(np.sum(axial_power)),1.0e-12)
        axial_vapor=np.maximum(y[self.I_AXIAL_VAPOR],0.0)
        axial_vapor/=max(float(np.sum(axial_vapor)),1.0e-12)
        axial_void=self._axial_voids(
            float(y[self.I_MCORE_VAPOR]),float(y[self.I_MCORE]),sat,axial_vapor
        )
        spatial_void=self._spatial_void_signal(axial_void)

        rho_rods = -(c.rod_worth_pcm * controls.rod_pct / 100.0) * 1.0e-5
        rho_trim = controls.trim_pcm * 1.0e-5
        rho_fuel = c.alpha_f * (fuel_temperature - c.TrefFuel)
        rho_void = c.alpha_void * (spatial_void - self.reference_spatial_void)
        rho_total = self.clamp(rho_rods + rho_trim + rho_fuel + rho_void, -0.12, 0.012)

        d = np.zeros_like(y)
        d[self.I_N] = ((rho_total - c.beta) / c.Lambda) * n + float(np.sum(c.lambda_i * precursors))
        d[self.I_CI] = (c.beta_i / c.Lambda) * n - c.lambda_i * precursors
        d[self.I_DI] = c.decay_frac * n - c.decay_lambda * decay_groups
        decay_fraction = float(np.sum(c.decay_lambda * decay_groups))
        generated_power = c.Pnom_MW * (c.prompt_frac * n + decay_fraction)

        rod_fraction=self.clamp(controls.rod_pct/100.0,0.0,1.0)
        bottom_weight=np.array([1.0,0.70,0.35,0.10])
        shape_target=self.base_axial_power_fraction*(1.0-0.85*rod_fraction*bottom_weight)
        void_departure=axial_void-self.reference_axial_void
        shape_target*=np.exp(-c.bwr_axial_void_shape_feedback*void_departure)
        shape_target=np.maximum(shape_target,1.0e-6); shape_target/=np.sum(shape_target)
        d[self.I_AXIAL_POWER]=(shape_target-axial_power)/c.bwr_axial_power_shape_tau_s
        vapor_target=np.cumsum(axial_power); vapor_target/=np.sum(vapor_target)
        transport_tau=c.bwr_axial_void_transport_tau_s/max(flow_fraction,0.08)
        d[self.I_AXIAL_VAPOR]=(vapor_target-axial_vapor)/transport_tau

        recirc_speed = self.clamp(controls.recirc_pct / 100.0, 0.0, 1.20)
        # A bounded thermal-expansion correction avoids interpolation noise at
        # the saturation boundary while retaining the colder downcomer's
        # greater hydrostatic density.
        dc_density = (1.0/sat.vf_m3_kg)*(1.0+0.001*max(0.0,sat.temperature_C-dc_temperature))
        (pump_head,buoyancy_head,core_friction_head,single_phase_loss_head,
         acceleration_head,two_phase_multiplier) = self._recirculation_heads(
            flow_fraction,recirc_speed,void,sat,dc_density
        )
        friction_head = core_friction_head+single_phase_loss_head+acceleration_head
        net_head = pump_head + buoyancy_head - friction_head
        d[self.I_FLOW] = net_head/(2.0*c.bwr_loop_loss_head_m*max(flow_fraction, 0.08)*c.bwr_recirc_tau_s)
        circulation = c.bwr_reference_core_flow_kg_s * flow_fraction

        # Fuel/clad stored energy remains explicit. Coolant heat removal follows
        # flow and, only when the guarded axial method is valid, boiling crisis.
        fuel_conductance_factor = self.clamp(
            1.0+2.0e-4*(fuel_temperature-c.TrefFuel), 0.75, 1.25
        )
        Kfc = c.Kfc*fuel_conductance_factor
        coolant_factor = 0.35 + 0.65*math.sqrt(flow_fraction)
        cpr_coupled = (
            controls.critical_power_valid_nodes > 0
            and math.isfinite(controls.critical_power_ratio)
        )
        if void < 0.01:
            heat_transfer_regime = "single-phase convection"
        elif not cpr_coupled:
            heat_transfer_regime = "unassessed two-phase"
        elif controls.critical_power_ratio >= 1.0:
            heat_transfer_regime = "nucleate boiling"
        elif controls.critical_power_ratio >= 0.80:
            transition_fraction=(1.0-controls.critical_power_ratio)/0.20
            coolant_factor *= 1.0-0.75*transition_fraction
            heat_transfer_regime = "transition boiling"
        else:
            coolant_factor *= 0.12
            heat_transfer_regime = "film boiling / dryout"
        Kcc = c.Kcc_nom*max(c.bwr_min_coolant_heat_transfer_factor,coolant_factor)
        Qfc = Kfc * (fuel_temperature - clad_temperature)
        Qcc = max(0.0, Kcc * (clad_temperature - sat.temperature_C))
        d[self.I_TF] = (generated_power - Qfc) / c.Cfuel
        d[self.I_TCL] = (Qfc - Qcc) / c.Cclad

        liquid_fraction = (
            float(y[self.I_MCORE])+float(y[self.I_MDC])
            +float(y[self.I_MUPPER])+float(y[self.I_MSEPARATOR])
        )/c.bwr_liquid_inventory_kg
        feedwater_regulator = self.clamp(
            1.0+c.bwr_feedwater_regulator_gain*(1.0-liquid_fraction), 0.0, 1.40
        )
        feedwater = (self.reference_steam_flow_kg_s
                     *self.clamp(controls.feedwater_pct/100.0,0.0,1.40)
                     *feedwater_regulator)
        # The equilibrium vessel contract stores saturated liquid. Account for
        # heating source-basis feedwater to saturation as an explicit internal
        # load before allocating clad heat to vaporization.
        feedwater_preheat = feedwater*c.bwr_feedwater_subcooling_kJ_kg/1000.0
        available_for_boiling = max(
            0.0, Qcc-feedwater_preheat
            +circulation*(dc_h-sat.hf_kj_kg)/1000.0
        )
        steam_generation = available_for_boiling / max(sat.latent_heat_kj_kg / 1000.0, 0.1)
        core_liquid_out = max(0.0, circulation - steam_generation)
        core_vapor_out = max(
            0.0, float(y[self.I_MCORE_VAPOR])/c.bwr_core_vapor_residence_s*flow_fraction
        )
        upper_liquid_out = max(0.0, float(y[self.I_MUPPER]) / c.bwr_upper_plenum_residence_s)
        separator_liquid_out = max(0.0, float(y[self.I_MSEPARATOR]) / c.bwr_separator_residence_s)

        msiv = self.clamp(controls.msiv_pct/100.0, 0.0, 1.0)
        pressure_regulator = self.clamp(
            1.0+c.bwr_pressure_regulator_gain*(pressure/c.Pref-1.0), 0.0, 1.40
        )
        main_steam = (self.reference_steam_flow_kg_s
                      *self.clamp(controls.main_steam_pct/100.0,0.0,1.40)
                      *msiv*pressure_regulator)
        bypass_flow = c.bwr_bypass_capacity_kg_s * self.clamp(controls.bypass_pct/100.0, 0.0, 1.0)
        srv_command = self.clamp(controls.srv_pct / 100.0, 0.0, 1.0)
        automatic_srv = self.clamp((pressure - c.bwr_srv_open_mpa) / 0.25, 0.0, 1.0)
        ads = self.clamp(controls.ads_pct/100.0,0.0,1.0) if controls.ads_available else 0.0
        srv_flow = c.bwr_srv_capacity_kg_s * max(srv_command, automatic_srv, ads)
        suction_available = pool_mass > c.bwr_suction_inventory_fraction_min*c.bwr_pool_mass_kg
        rcic_command=self.clamp(controls.rcic_pct/100.0,0.0,1.0) if controls.rcic_available and suction_available else 0.0
        hpci_command=self.clamp(controls.hpci_pct/100.0,0.0,1.0) if controls.hpci_available and suction_available else 0.0
        lpci_command=self.clamp(controls.lpci_pct/100.0,0.0,1.0) if controls.lpci_available and suction_available else 0.0
        spray_command=self.clamp(controls.core_spray_pct/100.0,0.0,1.0) if controls.core_spray_available and suction_available else 0.0
        rcic_driver=self.clamp(
            (pressure-c.bwr_rcic_driver_min_mpa)
            /max(c.bwr_driver_full_mpa-c.bwr_rcic_driver_min_mpa,1.0e-6),0.0,1.0
        )
        hpci_driver=self.clamp(
            (pressure-c.bwr_hpci_driver_min_mpa)
            /max(c.bwr_driver_full_mpa-c.bwr_hpci_driver_min_mpa,1.0e-6),0.0,1.0
        )
        rcic_flow,rcic_margin=self._injection_curve(
            rcic_command,c.bwr_rcic_capacity_kg_s,c.bwr_rcic_shutoff_head_mpa,
            pressure,rcic_driver,
        )
        hpci_flow,hpci_margin=self._injection_curve(
            hpci_command,c.bwr_hpci_capacity_kg_s,c.bwr_hpci_shutoff_head_mpa,
            pressure,hpci_driver,
        )
        lpci_flow,lpci_margin=self._injection_curve(
            lpci_command,c.bwr_lpci_capacity_kg_s,c.bwr_lpci_shutoff_head_mpa,pressure,
        )
        core_spray_flow,spray_margin=self._injection_curve(
            spray_command,c.bwr_core_spray_capacity_kg_s,
            c.bwr_core_spray_shutoff_head_mpa,pressure,
        )
        break_command=self.clamp(controls.bwr_break_pct/100.0,0.0,1.0)
        if break_command > 0.0:
            break_flux,break_critical_pressure,break_choked=self._hem_break_flux(
                pressure,c.bwr_break_backpressure_mpa,0.0
            )
        else:
            break_flux,break_critical_pressure,break_choked=0.0,pressure,False
        break_flow=(c.bwr_break_discharge_coefficient*c.bwr_break_area_m2
                    *break_command*break_flux)
        # The remediated vessel is a single saturated equilibrium control
        # volume; feedwater mixes to saturated liquid at its boundary.
        feedwater_h = sat.hf_kj_kg
        injection_h=4.18*max(pool_temperature,20.0)
        shutdown_availability=self.clamp((2.5-pressure)/1.5,0.0,1.0)
        shutdown_cooling=350.0*self.clamp(controls.shutdown_cooling_pct/100.0,0.0,1.0)*shutdown_availability

        d[self.I_MCORE] = circulation - core_liquid_out - steam_generation
        d[self.I_UCORE] = (
            Qcc-feedwater_preheat-shutdown_cooling + circulation * dc_h / 1000.0
            - core_liquid_out * sat.hf_kj_kg / 1000.0
            - steam_generation * sat.hg_kj_kg / 1000.0
            + core_spray_flow*injection_h/1000.0
        )
        d[self.I_MCORE] += core_spray_flow
        d[self.I_MUPPER] = core_liquid_out - upper_liquid_out
        d[self.I_UUPPER] = (core_liquid_out-upper_liquid_out)*sat.hf_kj_kg/1000.0
        d[self.I_MSEPARATOR] = upper_liquid_out - separator_liquid_out
        d[self.I_USEPARATOR] = (upper_liquid_out-separator_liquid_out)*sat.hf_kj_kg/1000.0
        d[self.I_MDC] = feedwater + separator_liquid_out + rcic_flow + hpci_flow + lpci_flow - circulation - break_flow
        d[self.I_UDC] = (
            feedwater * feedwater_h / 1000.0
            + separator_liquid_out * sat.hf_kj_kg / 1000.0
            - circulation * dc_h / 1000.0
            + (rcic_flow+hpci_flow+lpci_flow)*injection_h/1000.0
            - break_flow*dc_h/1000.0
        )
        rcic_steam_use=0.035*rcic_flow
        steam_out = main_steam + bypass_flow + srv_flow + rcic_steam_use
        d[self.I_MCORE_VAPOR] = steam_generation-core_vapor_out
        d[self.I_UCORE_VAPOR] = (steam_generation-core_vapor_out)*sat.hg_kj_kg/1000.0
        d[self.I_MSTEAM] = core_vapor_out-steam_out
        d[self.I_USTEAM] = (core_vapor_out-steam_out)*sat.hg_kj_kg/1000.0

        core_vapor_volume = max(float(y[self.I_MCORE_VAPOR]),0.0)*sat.vg_m3_kg
        core_liquid_volume = max(float(y[self.I_MCORE]),1.0)*sat.vf_m3_kg
        equilibrium_void = core_vapor_volume/max(
            core_vapor_volume+core_liquid_volume, 1.0e-9
        )
        d[self.I_VOID] = 0.0
        pool_inflow = srv_flow+rcic_steam_use
        pool_outflow = rcic_flow+hpci_flow+lpci_flow+core_spray_flow
        d[self.I_POOL_MASS] = pool_inflow-pool_outflow
        d[self.I_POOL_ENERGY] = (pool_inflow*sat.hg_kj_kg-pool_outflow*injection_h)/1000.0
        d[self.I_REFLEG_T]=(dc_temperature-reference_leg_temperature)/c.bwr_reference_leg_tau_s

        stored_mass_rate = (d[self.I_MCORE] + d[self.I_MDC] + d[self.I_MUPPER]
                            + d[self.I_MSEPARATOR] + d[self.I_MCORE_VAPOR]
                            + d[self.I_MSTEAM])
        boundary_mass_rate = (
            feedwater + rcic_flow + hpci_flow + lpci_flow + core_spray_flow
            - main_steam - bypass_flow - srv_flow - rcic_steam_use - break_flow
        )
        stored_energy_rate = (
            c.Cfuel*d[self.I_TF] + c.Cclad*d[self.I_TCL]
            + d[self.I_UCORE] + d[self.I_UDC] + d[self.I_UUPPER]
            + d[self.I_USEPARATOR] + d[self.I_UCORE_VAPOR]+d[self.I_USTEAM]
        )
        boundary_energy_rate = (
            generated_power-feedwater_preheat + feedwater*feedwater_h/1000.0
            + (rcic_flow+hpci_flow+lpci_flow+core_spray_flow)*injection_h/1000.0
            - (main_steam+bypass_flow+srv_flow+rcic_steam_use)*sat.hg_kj_kg/1000.0
            - break_flow*dc_h/1000.0 - shutdown_cooling
        )
        combined_mass_boundary = feedwater-main_steam-bypass_flow-break_flow
        combined_energy_boundary = (
            generated_power-feedwater_preheat+feedwater*feedwater_h/1000.0
            -(main_steam+bypass_flow)*sat.hg_kj_kg/1000.0
            -break_flow*dc_h/1000.0-shutdown_cooling
        )

        return d, BWRStepDiagnostics(
            decay_fraction=decay_fraction,
            rho_total=rho_total,
            flow_effective=flow_fraction,
            boiling_regime="bulk boiling" if steam_generation > 1.0 else "single-phase",
            chf_ratio=0.0,
            eccs_fraction=max(rcic_command,hpci_command,lpci_command,spray_command),
            break_out=break_flow/max(c.bwr_liquid_inventory_kg,1.0),
            porv_out=srv_flow / max(c.bwr_liquid_inventory_kg, 1.0),
            evaporation_out=steam_generation / max(c.bwr_liquid_inventory_kg, 1.0),
            steam_generation_kg_s=steam_generation,
            main_steam_flow_kg_s=main_steam,
            bypass_flow_kg_s=bypass_flow,
            srv_flow_kg_s=srv_flow,
            rcic_steam_use_kg_s=rcic_steam_use,
            feedwater_flow_kg_s=feedwater,
            rcic_flow_kg_s=rcic_flow,
            hpci_flow_kg_s=hpci_flow,
            lpci_flow_kg_s=lpci_flow,
            core_spray_flow_kg_s=core_spray_flow,
            break_flow_kg_s=break_flow,
            break_critical_pressure_mpa=break_critical_pressure,
            break_mass_flux_kg_m2_s=break_flux,
            break_choked=break_choked,
            rcic_head_margin_mpa=rcic_margin,
            hpci_head_margin_mpa=hpci_margin,
            lpci_head_margin_mpa=lpci_margin,
            core_spray_head_margin_mpa=spray_margin,
            shutdown_cooling_MW=shutdown_cooling,
            mass_balance_residual_kg_s=stored_mass_rate-boundary_mass_rate,
            energy_balance_residual_MW=stored_energy_rate-boundary_energy_rate,
            pump_head_m=pump_head,
            buoyancy_head_m=buoyancy_head,
            friction_head_m=friction_head,
            core_friction_head_m=core_friction_head,
            single_phase_loss_head_m=single_phase_loss_head,
            acceleration_head_m=acceleration_head,
            two_phase_friction_multiplier=two_phase_multiplier,
            vessel_pool_mass_residual_kg_s=(stored_mass_rate+d[self.I_POOL_MASS])-combined_mass_boundary,
            vessel_pool_energy_residual_MW=(stored_energy_rate+d[self.I_POOL_ENERGY])-combined_energy_boundary,
            core_void_fraction=equilibrium_void,
            coolant_heat_transfer_factor=Kcc/c.Kcc_nom,
            heat_transfer_regime=heat_transfer_regime,
            critical_power_coupled=cpr_coupled,
        )

    def project(self, vector: np.ndarray) -> np.ndarray:
        c = self.c
        y = np.asarray(vector, dtype=float).copy()
        y[self.I_N] = self.clamp(float(y[self.I_N]), 0.0, 2.5)
        y[self.I_CI] = np.maximum(y[self.I_CI], 0.0)
        y[self.I_DI] = np.maximum(y[self.I_DI], 0.0)
        y[self.I_TF] = self.clamp(float(y[self.I_TF]), 20.0, 2800.0)
        y[self.I_TCL] = self.clamp(float(y[self.I_TCL]), 20.0, 2200.0)
        y[self.I_MCORE] = max(float(y[self.I_MCORE]), 1.0)
        y[self.I_MDC] = max(float(y[self.I_MDC]), 1.0)
        y[self.I_MSTEAM] = max(float(y[self.I_MSTEAM]), 0.0)
        y[self.I_MCORE_VAPOR] = max(float(y[self.I_MCORE_VAPOR]), 0.0)
        y[self.I_MUPPER] = max(float(y[self.I_MUPPER]), 1.0)
        y[self.I_MSEPARATOR] = max(float(y[self.I_MSEPARATOR]), 1.0)
        y[self.I_UCORE] = max(float(y[self.I_UCORE]), 0.0)
        y[self.I_UDC] = max(float(y[self.I_UDC]), 0.0)
        y[self.I_USTEAM] = max(float(y[self.I_USTEAM]), 0.0)
        y[self.I_UCORE_VAPOR] = max(float(y[self.I_UCORE_VAPOR]), 0.0)
        y[self.I_UUPPER] = max(float(y[self.I_UUPPER]), 0.0)
        y[self.I_USEPARATOR] = max(float(y[self.I_USEPARATOR]), 0.0)
        y[self.I_VOID] = self.clamp(float(y[self.I_VOID]), 0.0, 0.90)
        # Natural circulation is now the momentum-balance outcome, not a
        # prescribed minimum-flow fraction.
        y[self.I_FLOW] = self.clamp(float(y[self.I_FLOW]), 0.02, 1.20)
        y[self.I_POOL_MASS] = max(float(y[self.I_POOL_MASS]), 1.0)
        y[self.I_POOL_ENERGY] = max(float(y[self.I_POOL_ENERGY]), 0.0)
        y[self.I_REFLEG_T] = self.clamp(float(y[self.I_REFLEG_T]), 20.0, 330.0)
        for axial_slice in (self.I_AXIAL_POWER,self.I_AXIAL_VAPOR):
            values=np.maximum(y[axial_slice],1.0e-9)
            y[axial_slice]=values/np.sum(values)
        # Algebraic equilibrium projection preserves total vessel mass and
        # internal energy while enforcing a single saturated M-U-V state.
        pressure, sat, liquid_mass, vapor_mass, _ = self.equilibrium_from_vector(y)
        liquid_indices = (self.I_MCORE, self.I_MDC, self.I_MUPPER, self.I_MSEPARATOR)
        provisional_liquid = sum(float(y[index]) for index in liquid_indices)
        fractions = [float(y[index])/max(provisional_liquid, 1.0) for index in liquid_indices]
        for index, fraction in zip(liquid_indices, fractions):
            y[index] = liquid_mass*fraction
        provisional_vapor = float(y[self.I_MCORE_VAPOR])+float(y[self.I_MSTEAM])
        core_vapor_fraction = float(y[self.I_MCORE_VAPOR])/max(provisional_vapor, 1.0)
        y[self.I_MCORE_VAPOR] = vapor_mass*core_vapor_fraction
        y[self.I_MSTEAM] = vapor_mass-y[self.I_MCORE_VAPOR]
        for mass_index, energy_index in (
            (self.I_MCORE,self.I_UCORE), (self.I_MDC,self.I_UDC),
            (self.I_MUPPER,self.I_UUPPER), (self.I_MSEPARATOR,self.I_USEPARATOR),
        ):
            y[energy_index] = y[mass_index]*sat.uf_kj_kg/1000.0
        y[self.I_UCORE_VAPOR] = y[self.I_MCORE_VAPOR]*sat.ug_kj_kg/1000.0
        y[self.I_USTEAM] = y[self.I_MSTEAM]*sat.ug_kj_kg/1000.0
        return y

    def step(self, state: Any, controls: BWRControlInputs, dt: float) -> BWRStepDiagnostics:
        if not np.isfinite(dt) or dt <= 0.0:
            raise ValueError("dt must be finite and positive")
        controls = self._effective_safety_controls(state, controls, dt)
        y0 = self.pack(state)
        k1, _ = self.rhs(state.t, y0, controls)
        k2, _ = self.rhs(state.t + 0.5 * dt, y0 + 0.5 * dt * k1, controls)
        k3, _ = self.rhs(state.t + 0.5 * dt, y0 + 0.5 * dt * k2, controls)
        k4, _ = self.rhs(state.t + dt, y0 + dt * k3, controls)
        final = self.project(y0 + dt * (k1 + 2.0*k2 + 2.0*k3 + k4) / 6.0)
        _, diagnostics = self.rhs(state.t + dt, final, controls)
        final[self.I_VOID] = diagnostics.core_void_fraction
        _, diagnostics = self.rhs(state.t + dt, final, controls)

        state.n = float(final[self.I_N]); state.Ci = final[self.I_CI].copy(); state.Di = final[self.I_DI].copy()
        state.Tf = float(final[self.I_TF]); state.Tcl = float(final[self.I_TCL])
        state.bwr_core_mass_kg = float(final[self.I_MCORE]); state.bwr_core_energy_MJ = float(final[self.I_UCORE])
        state.bwr_downcomer_mass_kg = float(final[self.I_MDC]); state.bwr_downcomer_energy_MJ = float(final[self.I_UDC])
        state.bwr_upper_plenum_mass_kg = float(final[self.I_MUPPER]); state.bwr_upper_plenum_energy_MJ = float(final[self.I_UUPPER])
        state.bwr_separator_mass_kg = float(final[self.I_MSEPARATOR]); state.bwr_separator_energy_MJ = float(final[self.I_USEPARATOR])
        state.bwr_core_vapor_mass_kg = float(final[self.I_MCORE_VAPOR]); state.bwr_core_vapor_energy_MJ = float(final[self.I_UCORE_VAPOR])
        state.bwr_steam_mass_kg = float(final[self.I_MSTEAM]); state.bwr_steam_energy_MJ = float(final[self.I_USTEAM])
        state.void_fraction = float(final[self.I_VOID]); state.bwr_core_flow_fraction = float(final[self.I_FLOW])
        state.bwr_suppression_pool_mass_kg=float(final[self.I_POOL_MASS])
        state.bwr_suppression_pool_energy_MJ=float(final[self.I_POOL_ENERGY])
        state.bwr_suppression_pool_temperature_C=self.clamp(
            1000.0*state.bwr_suppression_pool_energy_MJ
            /(state.bwr_suppression_pool_mass_kg*self.c.bwr_pool_cp_kJ_kgK),
            10.0, 100.0,
        )
        state.bwr_reference_leg_temperature_C=float(final[self.I_REFLEG_T])
        state.bwr_axial_power_fraction=final[self.I_AXIAL_POWER].copy()
        state.bwr_axial_vapor_fraction=final[self.I_AXIAL_VAPOR].copy()
        pressure, sat, _, _, dc_temperature = self._derived(final)
        state.P = pressure; state.Tprz = sat.temperature_C; state.Tc = sat.temperature_C
        liquid_mass = (state.bwr_core_mass_kg + state.bwr_downcomer_mass_kg
                       + state.bwr_upper_plenum_mass_kg + state.bwr_separator_mass_kg)
        state.M = liquid_mass / self.c.bwr_liquid_inventory_kg
        state.bwr_steam_flow_kg_s = diagnostics.main_steam_flow_kg_s
        state.bwr_feedwater_flow_kg_s = diagnostics.feedwater_flow_kg_s
        state.bwr_srv_flow_kg_s = diagnostics.srv_flow_kg_s
        state.bwr_rcic_flow_kg_s = diagnostics.rcic_flow_kg_s
        state.bwr_hpci_flow_kg_s = diagnostics.hpci_flow_kg_s
        state.bwr_lpci_flow_kg_s = diagnostics.lpci_flow_kg_s
        state.bwr_core_spray_flow_kg_s = diagnostics.core_spray_flow_kg_s
        state.bwr_break_flow_kg_s = diagnostics.break_flow_kg_s
        state.bwr_break_critical_pressure_mpa = diagnostics.break_critical_pressure_mpa
        state.bwr_break_mass_flux_kg_m2_s = diagnostics.break_mass_flux_kg_m2_s
        state.bwr_break_choked = diagnostics.break_choked
        state.bwr_rcic_head_margin_mpa = diagnostics.rcic_head_margin_mpa
        state.bwr_hpci_head_margin_mpa = diagnostics.hpci_head_margin_mpa
        state.bwr_lpci_head_margin_mpa = diagnostics.lpci_head_margin_mpa
        state.bwr_core_spray_head_margin_mpa = diagnostics.core_spray_head_margin_mpa
        state.bwr_coolant_heat_transfer_factor = diagnostics.coolant_heat_transfer_factor
        state.bwr_heat_transfer_regime = diagnostics.heat_transfer_regime
        state.bwr_critical_power_coupled = diagnostics.critical_power_coupled
        state.bwr_bypass_flow_kg_s = diagnostics.bypass_flow_kg_s
        state.bwr_shutdown_cooling_MW = diagnostics.shutdown_cooling_MW
        state.bwr_mass_balance_residual_kg_s = diagnostics.mass_balance_residual_kg_s
        state.bwr_energy_balance_residual_MW = diagnostics.energy_balance_residual_MW
        state.bwr_vessel_pool_mass_residual_kg_s = diagnostics.vessel_pool_mass_residual_kg_s
        state.bwr_vessel_pool_energy_residual_MW = diagnostics.vessel_pool_energy_residual_MW
        state.bwr_pump_head_m = diagnostics.pump_head_m
        state.bwr_buoyancy_head_m = diagnostics.buoyancy_head_m
        state.bwr_friction_head_m = diagnostics.friction_head_m
        state.bwr_core_friction_head_m = diagnostics.core_friction_head_m
        state.bwr_single_phase_loss_head_m = diagnostics.single_phase_loss_head_m
        state.bwr_acceleration_head_m = diagnostics.acceleration_head_m
        state.bwr_two_phase_friction_multiplier = diagnostics.two_phase_friction_multiplier
        # Collapsed level uses the calibrated reference liquid density; void
        # swell is kept separate in the indicated-level surrogate.
        liquid_volume = liquid_mass*sat.vf_m3_kg
        reference_liquid_volume = self.c.bwr_liquid_inventory_kg*self.reference_saturation.vf_m3_kg
        state.bwr_collapsed_level_m = self.c.bwr_level_span_m*liquid_volume/reference_liquid_volume
        state.bwr_collapsed_level_percent = 100.0*state.bwr_collapsed_level_m/self.c.bwr_level_span_m
        available_dome_volume = self.c.bwr_steam_dome_volume_m3 + reference_liquid_volume-liquid_volume
        state.bwr_steam_dome_volume_m3 = available_dome_volume
        total_vapor_mass = state.bwr_core_vapor_mass_kg+state.bwr_steam_mass_kg
        state.bwr_steam_volume_residual_m3 = total_vapor_mass*sat.vg_m3_kg-available_dome_volume
        state.bwr_steam_energy_residual_MJ = (
            state.bwr_core_vapor_energy_MJ+state.bwr_steam_energy_MJ
            -total_vapor_mass*sat.ug_kj_kg/1000.0
        )
        core_reference_volume = (self.c.bwr_liquid_inventory_kg
                                 *self.c.bwr_core_inventory_fraction
                                 *self.reference_saturation.vf_m3_kg)
        swell_volume = core_reference_volume*(
            state.void_fraction/(1.0-state.void_fraction)
            - self.reference_void_fraction/(1.0-self.reference_void_fraction)
        )
        swell_height = self.c.bwr_level_span_m*swell_volume/reference_liquid_volume
        reference_leg_bias = self.c.bwr_reference_leg_sensitivity*(
            state.bwr_reference_leg_temperature_C-dc_temperature
        )/max(self.c.bwr_level_span_m, 1.0)
        state.bwr_indicated_level_m = self.clamp(
            state.bwr_collapsed_level_m+swell_height+reference_leg_bias,
            0.0, 1.30*self.c.bwr_level_span_m,
        )
        state.bwr_indicated_level_percent = 100.0*state.bwr_indicated_level_m/self.c.bwr_level_span_m
        state.bwr_downcomer_temperature_C = dc_temperature
        state.bwr_axial_void_fraction=self._axial_voids(
            state.bwr_core_vapor_mass_kg,state.bwr_core_mass_kg,sat,
            state.bwr_axial_vapor_fraction,
        )
        state.bwr_axial_peak_node=int(np.argmax(state.bwr_axial_power_fraction))+1
        state.boiling_regime = diagnostics.boiling_regime; state.chf_ratio = 0.0
        state.t += dt
        return diagnostics

    def _effective_safety_controls(
        self, state: Any, controls: BWRControlInputs, dt: float,
    ) -> BWRControlInputs:
        """Advance delayed/latching automatic demands once per completed step."""
        if not controls.auto_bwr_safety:
            return controls
        level_percent = state.bwr_indicated_level_percent
        pressure = state.P
        demands = {
            "rcic": level_percent < self.c.bwr_rcic_start_level_percent,
            "hpci": level_percent < self.c.bwr_hpci_start_level_percent,
            "ads": (
                level_percent < self.c.bwr_ads_start_level_percent
                and pressure > self.c.bwr_ads_pressure_permissive_mpa
                and (controls.lpci_available or controls.core_spray_available)
            ),
            "lpci": (
                level_percent < self.c.bwr_low_pressure_eccs_start_level_percent
                and pressure < self.c.bwr_low_pressure_eccs_pressure_permissive_mpa
            ),
            "core_spray": (
                level_percent < self.c.bwr_low_pressure_eccs_start_level_percent
                and pressure < self.c.bwr_low_pressure_eccs_pressure_permissive_mpa
            ),
        }
        delays = {
            "rcic": self.c.bwr_rcic_start_delay_s,
            "hpci": self.c.bwr_hpci_start_delay_s,
            "ads": self.c.bwr_ads_start_delay_s,
            "lpci": self.c.bwr_lpci_start_delay_s,
            "core_spray": self.c.bwr_core_spray_start_delay_s,
        }
        for name, demand in demands.items():
            timer_name = f"bwr_{name}_demand_timer_s"
            latch_name = f"bwr_{name}_latched"
            timer = getattr(state, timer_name)
            timer = timer+dt if demand else 0.0
            setattr(state, timer_name, timer)
            if timer >= delays[name]:
                setattr(state, latch_name, True)
        if level_percent > self.c.bwr_eccs_reset_level_percent:
            state.bwr_safety_reset_timer_s += dt
        else:
            state.bwr_safety_reset_timer_s = 0.0
        if state.bwr_safety_reset_timer_s >= self.c.bwr_eccs_reset_delay_s:
            for name in demands:
                setattr(state, f"bwr_{name}_latched", False)
        return replace(
            controls,
            rcic_pct=max(controls.rcic_pct, 70.0 if state.bwr_rcic_latched else 0.0),
            hpci_pct=max(controls.hpci_pct, 100.0 if state.bwr_hpci_latched else 0.0),
            ads_pct=max(controls.ads_pct, 100.0 if state.bwr_ads_latched else 0.0),
            lpci_pct=max(controls.lpci_pct, 85.0 if state.bwr_lpci_latched else 0.0),
            core_spray_pct=max(controls.core_spray_pct, 65.0 if state.bwr_core_spray_latched else 0.0),
        )

    def evaluate_protection(self, state: Any, dt: float) -> tuple[bool, str]:
        """Advance independent generic RPS channel timers once per GUI step."""
        c = self.c
        thermal_signal = (
            state.Tcl >= c.bwr_rps_high_clad_C
            or (state.hot_dnbr_valid_nodes > 0
                and math.isfinite(state.hot_min_dnbr)
                and state.hot_min_dnbr <= 1.0)
        )
        channels = (
            ("high_flux", state.n >= c.bwr_rps_high_flux_fraction,
             c.bwr_rps_high_flux_delay_s, "High neutron flux"),
            ("high_pressure", state.P >= c.bwr_rps_high_pressure_mpa,
             c.bwr_rps_high_pressure_delay_s, "High vessel pressure"),
            ("low_level", state.bwr_indicated_level_percent <= c.bwr_rps_low_level_percent,
             c.bwr_rps_low_level_delay_s, "Low reactor water level"),
            ("thermal", thermal_signal,
             c.bwr_rps_thermal_delay_s, "Fuel thermal limit"),
        )
        causes = []
        for name,signal,delay,cause in channels:
            timer_name=f"bwr_rps_{name}_timer_s"
            timer=getattr(state,timer_name)+dt if signal else 0.0
            setattr(state,timer_name,timer)
            if timer >= delay:
                causes.append(cause)
        state.bwr_protection_demand=bool(causes)
        if causes and state.bwr_trip_cause == "None":
            state.bwr_trip_cause=" / ".join(causes)
        return bool(causes), " / ".join(causes) if causes else "None"
