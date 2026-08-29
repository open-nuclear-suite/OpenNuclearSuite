"""Representative axial BWR channel with open critical-quality dryout screening."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from steam_properties import SteamTables


@dataclass(frozen=True)
class BWRHotChannelGeometry:
    node_count: int = 24
    heated_length_m: float = 3.80
    rod_outer_diameter_m: float = 0.0123
    fuel_diameter_m: float = 0.0104
    rod_pitch_m: float = 0.0162
    nominal_mass_flow_kg_s: float = 0.32
    nominal_average_linear_heat_W_m: float = 18_000.0
    radial_hot_channel_factor: float = 1.18
    enthalpy_rise_factor: float = 1.08
    local_heat_flux_factor: float = 1.10
    hydraulic_diameter_m: float = 0.0145
    darcy_friction_factor: float = 0.018
    spacer_loss_coefficient: float = 1.6
    nominal_coolant_htc_W_m2K: float = 32_000.0
    effective_fuel_resistance_mK_W: float = 0.020

    @property
    def flow_area_m2(self) -> float:
        return self.rod_pitch_m**2 - math.pi*self.rod_outer_diameter_m**2/4.0


@dataclass(frozen=True)
class BWRHotChannelResult:
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
    coolant_heat_transfer_coefficient_W_m2K: np.ndarray
    heat_transfer_regime: np.ndarray
    inlet_enthalpy_kj_kg: float
    outlet_enthalpy_kj_kg: float
    deposited_power_W: float
    phase_warning: str
    void_fraction: np.ndarray
    plant_type: str = "BWR"

    @property
    def outlet_temperature_C(self) -> float:
        return float(self.bulk_temperature_C[-1])

    @property
    def minimum_dnbr_index(self) -> int | None:
        return None if np.all(np.isnan(self.dnbr)) else int(np.nanargmin(self.dnbr))

    @property
    def minimum_dnbr(self) -> float:
        index = self.minimum_dnbr_index
        return float("nan") if index is None else float(self.dnbr[index])

    @property
    def minimum_cpr(self) -> float:
        return self.minimum_dnbr


class BWRHotChannelModel:
    """Quasi-steady channel using a guarded CISE-style X-L dryout method."""

    def __init__(self, properties: SteamTables, geometry: BWRHotChannelGeometry | None = None):
        self.properties = properties
        self.geometry = geometry or BWRHotChannelGeometry()

    @staticmethod
    def post_dryout_multiplier(cpr: float, valid: bool) -> tuple[float, str]:
        """Bounded teaching boiling curve driven only by a valid CPR result."""
        if not valid or not np.isfinite(cpr):
            return 1.0, "unassessed two-phase"
        if cpr >= 1.0:
            return 1.0, "nucleate boiling"
        if cpr >= 0.80:
            fraction = (1.0-cpr)/0.20
            return 1.0-0.75*fraction, "transition boiling"
        return 0.12, "film boiling / dryout"

    def solve(self, power_fraction: float, inlet_pressure_mpa: float,
              inlet_temperature_C: float, flow_fraction: float,
              axial_power_fractions: np.ndarray | None = None) -> BWRHotChannelResult:
        g = self.geometry
        count, dz = g.node_count, g.heated_length_m/g.node_count
        z = (np.arange(count, dtype=float)+0.5)*dz
        if axial_power_fractions is None:
            shape = np.sin(math.pi*z/g.heated_length_m); shape /= np.mean(shape)
        else:
            coarse=np.maximum(np.asarray(axial_power_fractions,dtype=float),0.0)
            if coarse.shape != (4,) or float(np.sum(coarse)) <= 0.0:
                raise ValueError("axial_power_fractions must contain four positive-zone shares")
            coarse/=np.sum(coarse)
            coarse_z=(np.arange(4,dtype=float)+0.5)*g.heated_length_m/4.0
            shape=np.interp(z,coarse_z,4.0*coarse,left=4.0*coarse[0],right=4.0*coarse[-1])
            shape/=np.mean(shape)
        linear_heat = (g.nominal_average_linear_heat_W_m*g.radial_hot_channel_factor
                       *g.enthalpy_rise_factor*max(power_fraction, 0.0)*shape)
        mass_flow = g.nominal_mass_flow_kg_s*max(flow_fraction, 0.08)
        mass_flux_value = mass_flow/g.flow_area_m2
        inlet_sat = self.properties.saturation_at_pressure(inlet_pressure_mpa)
        inlet_h = inlet_sat.hf_kj_kg - inlet_sat.cpf_kj_kgK * max(
            0.0, inlet_sat.temperature_C-inlet_temperature_C
        )
        inlet = self.properties.state_ph(inlet_pressure_mpa, inlet_h)
        boundaries = np.empty(count+1); boundaries[0] = inlet.enthalpy_kj_kg
        for i in range(count):
            boundaries[i+1] = boundaries[i] + linear_heat[i]*dz/mass_flow/1000.0
        enthalpy = 0.5*(boundaries[:-1]+boundaries[1:])
        pressure = np.full(count, inlet_pressure_mpa)
        # Iterate pressure and density because two-phase gravity, friction, and
        # acceleration losses depend on the local thermodynamic state.
        for _ in range(4):
            trial_density = np.empty(count)
            for i in range(count):
                trial_density[i] = self.properties.state_ph(
                    float(pressure[i]), float(enthalpy[i])
                ).density_kg_m3
            new_pressure = np.empty(count)
            boundary_pressure = inlet_pressure_mpa
            previous_v = 1.0/max(inlet.density_kg_m3, 1.0)
            spacer_k_node = g.spacer_loss_coefficient/count
            for i in range(count):
                rho = max(trial_density[i], 1.0)
                velocity_head = mass_flux_value**2/(2.0*rho)
                friction_pa = (g.darcy_friction_factor*dz/g.hydraulic_diameter_m+spacer_k_node)*velocity_head
                gravity_pa = rho*9.80665*dz
                current_v = 1.0/rho
                acceleration_pa = max(0.0, mass_flux_value**2*(current_v-previous_v))
                boundary_pressure -= (friction_pa+gravity_pa+acceleration_pa)/1.0e6
                new_pressure[i] = boundary_pressure
                previous_v = current_v
            pressure = 0.5*pressure+0.5*new_pressure
        bulk=np.empty(count); saturation_t=np.empty(count); density=np.empty(count)
        quality=np.full(count,np.nan); eq_quality=np.empty(count); void=np.zeros(count)
        dryout_flux=np.full(count, np.nan)
        cpr=np.full(count, np.nan)
        valid=np.zeros(count,dtype=bool)
        boiling_start = None
        cumulative_power = np.cumsum(linear_heat*dz)
        total_power = max(float(cumulative_power[-1]), 1.0)
        for i in range(count):
            state=self.properties.state_ph(float(pressure[i]),float(enthalpy[i]))
            sat=self.properties.saturation_at_pressure(float(pressure[i]))
            bulk[i]=state.temperature_C; saturation_t[i]=sat.temperature_C; density[i]=state.density_kg_m3
            eq_quality[i]=(enthalpy[i]-sat.hf_kj_kg)/sat.latent_heat_kj_kg
            x=max(0.0,min(0.95,eq_quality[i])); quality[i]=x if eq_quality[i]>=0 else np.nan
            void[i]=x*sat.vg_m3_kg/max(x*sat.vg_m3_kg+(1-x)*sat.vf_m3_kg,1e-12)
            if eq_quality[i] >= 0.0 and boiling_start is None:
                boiling_start = z[i]-0.5*dz
            boiling_length = 0.0 if boiling_start is None else z[i]-boiling_start
            valid[i] = (
                3.0 <= pressure[i] <= 10.0
                and 500.0 <= mass_flux_value <= 3000.0
                and 0.005 <= g.hydraulic_diameter_m <= 0.020
                and boiling_length > 0.0
                and -0.05 <= eq_quality[i] <= 0.80
            )
            if valid[i]:
                # Open CISE-style critical-quality/boiling-length screening form.
                # Coefficients are deliberately generic, never bundle-specific.
                xcrit = self.clamp(
                    (0.62-0.018*(pressure[i]-7.0))
                    *(mass_flux_value/1500.0)**0.10
                    *(g.hydraulic_diameter_m/0.012)**0.15
                    /(1.0+0.08*boiling_length),
                    0.12, 0.78,
                )
                required_rise = sat.hf_kj_kg+sat.latent_heat_kj_kg*xcrit-inlet.enthalpy_kj_kg
                critical_power = mass_flow*max(required_rise, 0.0)*1000.0*total_power/max(cumulative_power[i],1.0)
                cpr[i] = critical_power/total_power
        heat_flux=linear_heat*g.local_heat_flux_factor/(math.pi*g.rod_outer_diameter_m)
        dryout_flux = heat_flux*cpr
        base_htc=g.nominal_coolant_htc_W_m2K*math.sqrt(max(flow_fraction,0.08))
        htc=np.full(count,base_htc)
        regimes=np.full(count,"single-phase convection",dtype=object)
        for i in range(count):
            if eq_quality[i] >= 0.0:
                multiplier,regimes[i]=self.post_dryout_multiplier(cpr[i],bool(valid[i]))
                htc[i]*=multiplier
        clad=bulk+heat_flux/np.maximum(htc,1.0)
        fuel=clad+linear_heat*g.effective_fuel_resistance_mK_W
        two_phase=np.flatnonzero(eq_quality>=0)+1
        warning=("Equilibrium two-phase flow at node(s) "+", ".join(map(str,two_phase))+". " if two_phase.size else "")
        invalid=np.flatnonzero(~valid)+1
        if invalid.size:
            warning += "X-L method outside its declared range at node(s) "+", ".join(map(str,invalid))+". "
        warning += "CISE-style X-L screening is diagnostic, not a bundle-specific licensing correlation."
        return BWRHotChannelResult(
            z,bulk,saturation_t,clad,fuel,pressure,enthalpy,density,
            np.full(count,mass_flux_value),quality,linear_heat,heat_flux,eq_quality,
            dryout_flux,cpr,valid,htc,regimes,inlet.enthalpy_kj_kg,
            float(boundaries[-1]),float(np.sum(linear_heat)*dz),warning,void,
        )

    @staticmethod
    def clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))
