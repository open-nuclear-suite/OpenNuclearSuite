"""Steady one-dimensional channel model and statistical hot-channel sampler."""

from __future__ import annotations

import math
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

THERMAL_HYDRAULICS_DIR = Path(__file__).resolve().parents[1] / "ThermalHydraulicsSimulator"
if str(THERMAL_HYDRAULICS_DIR) not in sys.path:
    sys.path.insert(0, str(THERMAL_HYDRAULICS_DIR))

from steam_properties import SteamTables

from .correlations import BOILING_CORRELATIONS, FRICTION_CORRELATIONS, HEAT_TRANSFER_CORRELATIONS
from .materials import CLADDING_MATERIALS
from .provenance import CalculationProvenance
from .void_models import VOID_FRACTION_MODELS
from .two_phase_friction import TWO_PHASE_FRICTION_MODELS
from .axial_heat_shapes import AXIAL_HEAT_SHAPES
from .localized_hot_factors import combine_power_hot_factors
from .channel_types import (
    ChannelGeometry,
    ChannelInputs,
    ChannelResult,
    StatisticalResult,
    StatisticalSettings,
)
from .channel_transitions import classify_boiling_regions
from .chf_correlations import CHF_CORRELATIONS, evaluate_chf


class SingleChannelModel:
    def __init__(self, properties: SteamTables | None = None) -> None:
        self.properties = properties or SteamTables()

    def solve(self, geometry: ChannelGeometry, inputs: ChannelInputs) -> ChannelResult:
        if inputs.friction_key not in FRICTION_CORRELATIONS:
            raise ValueError(f"unknown friction correlation: {inputs.friction_key}")
        if inputs.heat_transfer_key not in HEAT_TRANSFER_CORRELATIONS:
            raise ValueError(f"unknown heat-transfer correlation: {inputs.heat_transfer_key}")
        if inputs.boiling_key not in BOILING_CORRELATIONS:
            raise ValueError(f"unknown boiling correlation: {inputs.boiling_key}")
        if inputs.cladding_key not in CLADDING_MATERIALS:
            raise ValueError(f"unknown cladding material: {inputs.cladding_key}")
        if inputs.void_model_key not in VOID_FRACTION_MODELS:
            raise ValueError(f"unknown void-fraction model: {inputs.void_model_key}")
        if inputs.two_phase_friction_key not in TWO_PHASE_FRICTION_MODELS:
            raise ValueError(f"unknown two-phase friction model: {inputs.two_phase_friction_key}")
        if inputs.heat_shape_key not in AXIAL_HEAT_SHAPES:
            raise ValueError(f"unknown axial heat shape: {inputs.heat_shape_key}")
        if inputs.chf_key not in CHF_CORRELATIONS:
            raise ValueError(f"unknown CHF correlation: {inputs.chf_key}")
        mass_flow = inputs.mass_flow_kg_s * inputs.flow_factor
        if mass_flow <= 0.0 or inputs.average_linear_heat_W_m < 0.0:
            raise ValueError("mass flow must be positive and heat rate non-negative")

        n = geometry.node_count
        dz = geometry.heated_length_m / n
        z = (np.arange(n, dtype=float) + 0.5) * dz
        base_shape = AXIAL_HEAT_SHAPES[inputs.heat_shape_key].evaluate(
            z, geometry.heated_length_m, inputs.heat_shape_parameter
        )
        localized_factor, hot_factor = combine_power_hot_factors(
            z, geometry.heated_length_m, inputs.localized_power_factors,
            inputs.power_factor, inputs.hot_factor_combination_method,
        )
        raw_overall_factor = base_shape * hot_factor
        if inputs.preserve_power_with_local_factors:
            raw_overall_factor *= inputs.power_factor / np.mean(raw_overall_factor)
        combined_power_factor = raw_overall_factor
        shape = combined_power_factor / inputs.power_factor
        linear_heat = inputs.average_linear_heat_W_m * combined_power_factor
        base_linear_heat = inputs.average_linear_heat_W_m * inputs.power_factor * base_shape
        heat_flux = linear_heat / geometry.wetted_perimeter_m
        deposited_power = float(np.sum(linear_heat) * dz)
        inlet = self.properties.state_pt(inputs.inlet_pressure_mpa, inputs.inlet_temperature_C)
        boundaries_h = np.empty(n + 1)
        boundaries_p = np.empty(n + 1)
        boundaries_h[0] = inlet.enthalpy_kj_kg
        boundaries_p[0] = inputs.inlet_pressure_mpa

        temperature = np.empty(n)
        saturation_temperature = np.empty(n)
        wall_temperature = np.empty(n)
        inner_clad_temperature = np.empty(n)
        pressure = np.empty(n)
        enthalpy = np.empty(n)
        eq_quality = np.empty(n)
        void = np.empty(n)
        slip_ratio = np.empty(n)
        void_model_valid = np.ones(n, dtype=bool)
        mass_fluxes = np.full(n, mass_flow / geometry.flow_area_m2)
        reynolds = np.empty(n)
        velocities = np.empty(n)
        liquid_velocities = np.zeros(n)
        vapor_velocities = np.zeros(n)
        prandtl_values = np.empty(n)
        nusselt_values = np.empty(n)
        viscosity_values = np.empty(n)
        conductivity_values = np.empty(n)
        surface_tension_values = np.empty(n)
        friction = np.empty(n)
        friction_multiplier = np.ones(n)
        liquid_reynolds = np.zeros(n)
        vapor_reynolds = np.zeros(n)
        two_phase_friction_valid = np.ones(n, dtype=bool)
        two_phase_friction_details: list[str] = []
        mixture_density = np.empty(n)
        friction_dp = np.empty(n)
        gravity_dp = np.empty(n)
        acceleration_dp = np.empty(n)
        total_dp = np.empty(n)
        cumulative_friction_dp = np.empty(n)
        cumulative_gravity_dp = np.empty(n)
        cumulative_acceleration_dp = np.empty(n)
        cumulative_pressure_drop = np.empty(n)
        htc = np.empty(n)
        chf_predictions = {key: np.full(n, np.nan) for key in CHF_CORRELATIONS}
        chf_details = {key: [] for key in CHF_CORRELATIONS}
        messages: set[str] = set()
        regimes: list[str] = []
        heat_transfer_modes: list[str] = []
        boiling_active = np.zeros(n, dtype=bool)
        boiling_onset_margin = np.empty(n)
        clad = CLADDING_MATERIALS[inputs.cladding_key]

        for i in range(n):
            enthalpy[i] = boundaries_h[i] + linear_heat[i] * dz / mass_flow / 2000.0
            pressure[i] = boundaries_p[i]
            state = self.properties.state_ph(float(pressure[i]), float(enthalpy[i]))
            temperature[i] = state.temperature_C
            sat = self.properties.saturation_at_pressure(float(pressure[i]))
            saturation_temperature[i] = sat.temperature_C
            eq_quality[i] = (enthalpy[i] - sat.hf_kj_kg) / sat.latent_heat_kj_kg

            transport = self.properties.transport_ph(
                float(pressure[i]), float(enthalpy[i]), two_phase_basis="saturated-liquid"
            )
            saturated_vapor_transport = self.properties.transport_ph(
                float(pressure[i]),
                float(0.5 * (sat.hf_kj_kg + sat.hg_kj_kg)),
                two_phase_basis="saturated-vapor",
            )
            viscosity = transport.viscosity_Pa_s
            conductivity = transport.conductivity_W_mK
            viscosity_values[i] = viscosity
            conductivity_values[i] = conductivity
            surface_tension_values[i] = transport.surface_tension_N_m
            void_result = VOID_FRACTION_MODELS[inputs.void_model_key].evaluate(
                quality=float(eq_quality[i]),
                pressure_mpa=float(pressure[i]),
                rho_l=1.0 / sat.vf_m3_kg,
                rho_g=1.0 / sat.vg_m3_kg,
                mass_flux=float(mass_fluxes[i]),
                surface_tension=float(transport.surface_tension_N_m),
                inclination_degrees=float(inputs.inclination_degrees),
            )
            void[i] = void_result.void_fraction
            slip_ratio[i] = void_result.slip_ratio
            void_model_valid[i] = void_result.valid
            if not void_result.valid and void_result.message:
                messages.add(void_result.message)
            reynolds[i] = mass_fluxes[i] * geometry.hydraulic_diameter_m / viscosity
            relative_roughness = geometry.roughness_m / geometry.hydraulic_diameter_m
            f_value = FRICTION_CORRELATIONS[inputs.friction_key].evaluate(
                float(reynolds[i]), relative_roughness
            )
            friction[i] = f_value.value
            if not f_value.valid:
                messages.add(f_value.message)
            liquid_cp_J_kgK = (
                state.cp_kj_kgK * 1000.0
                if np.isfinite(state.cp_kj_kgK)
                else sat.cpf_kj_kgK * 1000.0
            )
            prandtl = liquid_cp_J_kgK * viscosity / conductivity
            prandtl_values[i] = prandtl
            if inputs.heat_transfer_key == "gnielinski":
                nu_value = HEAT_TRANSFER_CORRELATIONS[inputs.heat_transfer_key].evaluate(
                    float(reynolds[i]), float(prandtl), float(friction[i])
                )
            else:
                nu_value = HEAT_TRANSFER_CORRELATIONS[inputs.heat_transfer_key].evaluate(
                    float(reynolds[i]), float(prandtl), True
                )
            if not nu_value.valid:
                messages.add(nu_value.message)
            nusselt_values[i] = nu_value.value
            htc[i] = nu_value.value * conductivity / geometry.hydraulic_diameter_m
            single_phase_wall_C = temperature[i] + heat_flux[i] / max(htc[i], 1.0)
            boiling = BOILING_CORRELATIONS[inputs.boiling_key].evaluate(
                heat_flux_W_m2=float(heat_flux[i]),
                pressure_mpa=float(pressure[i]),
                saturation_temperature_C=float(sat.temperature_C),
                bulk_temperature_C=float(temperature[i]),
                mass_flux_kg_m2_s=float(mass_fluxes[i]),
                hydraulic_diameter_m=geometry.hydraulic_diameter_m,
                equilibrium_quality=float(eq_quality[i]),
                liquid_density_kg_m3=1.0 / sat.vf_m3_kg,
                vapor_density_kg_m3=1.0 / sat.vg_m3_kg,
                liquid_viscosity_Pa_s=viscosity,
                liquid_conductivity_W_mK=conductivity,
                liquid_cp_J_kgK=liquid_cp_J_kgK,
                latent_heat_J_kg=sat.latent_heat_kj_kg * 1000.0,
                vapor_viscosity_Pa_s=saturated_vapor_transport.viscosity_Pa_s,
                surface_tension_N_m=transport.surface_tension_N_m,
                saturation_pressure_at_temperature=self.properties.saturation_pressure,
            )
            # Heat-flux intersection: nucleate boiling is selected when its wall
            # solution is cooler than the single-phase extrapolation.
            boiling_onset_margin[i] = single_phase_wall_C - boiling.temperature_C
            boiling_active[i] = boiling.temperature_C <= single_phase_wall_C
            if boiling_active[i]:
                wall_temperature[i] = boiling.temperature_C
                heat_transfer_modes.append(inputs.boiling_key)
                if not boiling.valid:
                    messages.add(boiling.message)
            else:
                wall_temperature[i] = single_phase_wall_C
                heat_transfer_modes.append(inputs.heat_transfer_key)
            clad_resistance_mK_W = math.log(
                geometry.rod_outer_diameter_m / geometry.clad_inner_diameter_m
            ) / (2.0 * math.pi * clad.conductivity_W_mK)
            inner_clad_temperature[i] = wall_temperature[i] + linear_heat[i] * clad_resistance_mK_W
            if eq_quality[i] >= 0.0:
                regimes.append("bulk two-phase")
            elif boiling_active[i]:
                regimes.append("subcooled nucleate boiling")
            else:
                regimes.append("single-phase liquid")
            for chf_key in CHF_CORRELATIONS:
                chf_value, chf_detail = evaluate_chf(
                    chf_key, float(pressure[i]), float(mass_fluxes[i]),
                    float(eq_quality[i]), geometry.hydraulic_diameter_m,
                    sat.hf_kj_kg - inlet.enthalpy_kj_kg,
                    sat.latent_heat_kj_kg * 1000.0, geometry.heated_length_m,
                    float(heat_flux[i]),
                    rod_pitch_m=geometry.rod_pitch_m,
                    rod_outer_diameter_m=geometry.rod_outer_diameter_m,
                    rho_l=1.0 / sat.vf_m3_kg,
                    rho_g=1.0 / sat.vg_m3_kg,
                    groeneveld_k1=inputs.groeneveld_k1,
                    groeneveld_k2=inputs.groeneveld_k2,
                    groeneveld_k4=inputs.groeneveld_k4,
                )
                chf_predictions[chf_key][i] = chf_value
                chf_details[chf_key].append(chf_detail)

            boundaries_h[i + 1] = boundaries_h[i] + linear_heat[i] * dz / mass_flow / 1000.0
            if 0.0 < eq_quality[i] < 1.0:
                rho_l = 1.0 / sat.vf_m3_kg
                rho_g = 1.0 / sat.vg_m3_kg
                mixture_density[i] = (1.0 - void[i]) * rho_l + void[i] * rho_g
                liquid_velocities[i] = (
                    mass_fluxes[i] * (1.0 - eq_quality[i])
                    / (rho_l * max(1.0 - void[i], 1.0e-12))
                )
                vapor_velocities[i] = (
                    mass_fluxes[i] * eq_quality[i]
                    / (rho_g * max(void[i], 1.0e-12))
                )
            else:
                mixture_density[i] = state.density_kg_m3
                if eq_quality[i] <= 0.0:
                    liquid_velocities[i] = mass_fluxes[i] / state.density_kg_m3
                else:
                    vapor_velocities[i] = mass_fluxes[i] / state.density_kg_m3
            mixture_specific_volume = 1.0 / mixture_density[i]
            velocities[i] = mass_fluxes[i] / mixture_density[i]

            homogeneous_friction_dp = friction[i] * dz / geometry.hydraulic_diameter_m * (
                mass_fluxes[i] ** 2 * mixture_specific_volume / 2.0
            ) / 1000.0
            friction_result = TWO_PHASE_FRICTION_MODELS[
                inputs.two_phase_friction_key
            ].evaluate(
                quality=float(eq_quality[i]),
                pressure_mpa=float(pressure[i]),
                mass_flux=float(mass_fluxes[i]),
                diameter=geometry.hydraulic_diameter_m,
                length=dz,
                rho_l=1.0 / sat.vf_m3_kg,
                rho_g=1.0 / sat.vg_m3_kg,
                mu_l=float(viscosity),
                mu_g=float(saturated_vapor_transport.viscosity_Pa_s),
                surface_tension=float(transport.surface_tension_N_m),
                inclination_degrees=float(inputs.inclination_degrees),
                friction_evaluator=lambda phase_re: FRICTION_CORRELATIONS[
                    inputs.friction_key
                ].evaluate(float(phase_re), relative_roughness).value,
                baseline_dp_kpa=float(homogeneous_friction_dp),
                reynolds=float(reynolds[i]),
            )
            friction_dp[i] = friction_result.pressure_drop_kpa
            friction_multiplier[i] = friction_result.multiplier
            liquid_reynolds[i] = friction_result.liquid_reynolds
            vapor_reynolds[i] = friction_result.vapor_reynolds
            two_phase_friction_valid[i] = friction_result.valid
            two_phase_friction_details.append(friction_result.detail)
            if not friction_result.valid and friction_result.message:
                messages.add(friction_result.message)
            gravity_dp[i] = (
                mixture_density[i] * 9.80665 * dz
                * math.sin(math.radians(inputs.inclination_degrees)) / 1000.0
            )

            inlet_state = self.properties.state_ph(
                float(boundaries_p[i]), float(boundaries_h[i])
            )
            inlet_quality = (boundaries_h[i] - sat.hf_kj_kg) / sat.latent_heat_kj_kg
            if 0.0 < inlet_quality < 1.0:
                inlet_void = VOID_FRACTION_MODELS[inputs.void_model_key].evaluate(
                    quality=float(inlet_quality), rho_l=1.0 / sat.vf_m3_kg,
                    rho_g=1.0 / sat.vg_m3_kg, mass_flux=float(mass_fluxes[i]),
                    surface_tension=float(transport.surface_tension_N_m),
                    inclination_degrees=float(inputs.inclination_degrees),
                ).void_fraction
                inlet_momentum_volume = (
                    inlet_quality**2 * sat.vg_m3_kg / inlet_void
                    + (1.0 - inlet_quality) ** 2 * sat.vf_m3_kg / (1.0 - inlet_void)
                )
            else:
                inlet_momentum_volume = 1.0 / inlet_state.density_kg_m3
            outlet_state_estimate = self.properties.state_ph(
                float(boundaries_p[i]), float(boundaries_h[i + 1])
            )
            outlet_quality_estimate = (
                (boundaries_h[i + 1] - sat.hf_kj_kg) / sat.latent_heat_kj_kg
            )
            if 0.0 < outlet_quality_estimate < 1.0:
                outlet_void_estimate = VOID_FRACTION_MODELS[inputs.void_model_key].evaluate(
                    quality=float(outlet_quality_estimate), rho_l=1.0 / sat.vf_m3_kg,
                    rho_g=1.0 / sat.vg_m3_kg, mass_flux=float(mass_fluxes[i]),
                    surface_tension=float(transport.surface_tension_N_m),
                    inclination_degrees=float(inputs.inclination_degrees),
                ).void_fraction
                outlet_momentum_volume = (
                    outlet_quality_estimate**2 * sat.vg_m3_kg / outlet_void_estimate
                    + (1.0 - outlet_quality_estimate) ** 2 * sat.vf_m3_kg
                    / (1.0 - outlet_void_estimate)
                )
            else:
                outlet_momentum_volume = 1.0 / outlet_state_estimate.density_kg_m3
            acceleration_dp[i] = (
                mass_fluxes[i] ** 2 * (outlet_momentum_volume - inlet_momentum_volume)
                / 1000.0
            )
            total_dp[i] = friction_dp[i] + gravity_dp[i] + acceleration_dp[i]
            boundaries_p[i + 1] = max(0.05, boundaries_p[i] - total_dp[i] / 1000.0)
            cumulative_friction_dp[i] = np.sum(friction_dp[: i + 1])
            cumulative_gravity_dp[i] = np.sum(gravity_dp[: i + 1])
            cumulative_acceleration_dp[i] = np.sum(acceleration_dp[: i + 1])
            cumulative_pressure_drop[i] = np.sum(total_dp[: i + 1])

        chf = chf_predictions[inputs.chf_key]
        chf_model = CHF_CORRELATIONS[inputs.chf_key]
        if np.any(~np.isfinite(chf)):
            messages.add(f"{chf_model.label} CHF unavailable at nodes outside its published domain")
        dnbr = np.divide(chf, heat_flux, out=np.full(n, np.nan), where=heat_flux > 0.0)
        chf_valid = np.isfinite(chf)
        chf_validity = {key: np.isfinite(values) for key, values in chf_predictions.items()}
        outlet_pressure = float(boundaries_p[-1])
        outlet_enthalpy = float(boundaries_h[-1])
        outlet_state = self.properties.state_ph(outlet_pressure, outlet_enthalpy)
        outlet_sat = self.properties.saturation_at_pressure(outlet_pressure)
        outlet_quality = (
            (outlet_enthalpy - outlet_sat.hf_kj_kg) / outlet_sat.latent_heat_kj_kg
        )
        outlet_transport = self.properties.transport_ph(
            outlet_pressure, outlet_enthalpy, two_phase_basis="saturated-liquid"
        )
        outlet_void = VOID_FRACTION_MODELS[inputs.void_model_key].evaluate(
            quality=outlet_quality,
            rho_l=1.0 / outlet_sat.vf_m3_kg,
            rho_g=1.0 / outlet_sat.vg_m3_kg,
            mass_flux=float(mass_fluxes[-1]),
            surface_tension=outlet_transport.surface_tension_N_m,
            inclination_degrees=inputs.inclination_degrees,
        ).void_fraction
        if outlet_quality <= 0.0:
            outlet_regime = "single-phase liquid"
        elif outlet_quality < 1.0:
            outlet_regime = "bulk two-phase"
        else:
            outlet_regime = "single-phase vapor"
        boiling_regions = classify_boiling_regions(
            z, boiling_onset_margin, eq_quality, geometry.heated_length_m
        )
        friction_model = FRICTION_CORRELATIONS[inputs.friction_key]
        void_model = VOID_FRACTION_MODELS[inputs.void_model_key]
        two_phase_friction_model = TWO_PHASE_FRICTION_MODELS[inputs.two_phase_friction_key]
        heat_model = HEAT_TRANSFER_CORRELATIONS[inputs.heat_transfer_key]
        boiling_model = BOILING_CORRELATIONS[inputs.boiling_key]
        provenance = (
            CalculationProvenance(
                "axial_heat_shape", inputs.heat_shape_key,
                AXIAL_HEAT_SHAPES[inputs.heat_shape_key].label,
                "User-selected normalized axial heat-rate model",
                AXIAL_HEAT_SHAPES[inputs.heat_shape_key].note,
            ),
            CalculationProvenance(
                "transport_properties", "if97_transport_table",
                "IF97::Water transport-property table",
                "IAPWS transport formulations via CoolProp IF97::Water",
                "Two-phase heat-transfer inputs use saturated-liquid and saturated-vapor phase properties.",
            ),
            CalculationProvenance(
                "friction_factor", friction_model.key, friction_model.label,
                friction_model.citation,
            ),
            CalculationProvenance(
                "single_phase_heat_transfer", heat_model.key, heat_model.label,
                heat_model.citation,
            ),
            CalculationProvenance(
                "nucleate_boiling", boiling_model.key, boiling_model.label,
                boiling_model.citation,
            ),
            CalculationProvenance(
                "critical_heat_flux", chf_model.key, chf_model.label,
                chf_model.citation, chf_model.note,
            ),
            CalculationProvenance(
                "void_fraction", void_model.key, void_model.label,
                void_model.citation, void_model.note,
            ),
            CalculationProvenance(
                "frictional_pressure_drop", two_phase_friction_model.key,
                two_phase_friction_model.label, two_phase_friction_model.citation,
                two_phase_friction_model.note,
            ),
            CalculationProvenance(
                "gravitational_pressure_drop", "homogeneous_hydrostatic", "Hydrostatic head",
                "One-dimensional momentum balance: rho_m g dz sin(theta)",
                "Positive inclination denotes upward flow.",
            ),
            CalculationProvenance(
                "acceleration_pressure_drop", "homogeneous_momentum_flux", "Homogeneous acceleration",
                "One-dimensional momentum balance: G^2 d(v_m)",
                "Slip ratio is unity; cell-boundary specific volumes use the local pressure.",
            ),
        )
        return ChannelResult(
            z_m=z,
            pressure_mpa=pressure,
            bulk_temperature_C=temperature,
            saturation_temperature_C=saturation_temperature,
            wall_temperature_C=wall_temperature,
            inner_clad_temperature_C=inner_clad_temperature,
            enthalpy_kj_kg=enthalpy,
            equilibrium_quality=eq_quality,
            void_fraction=void,
            slip_ratio=slip_ratio,
            void_model_valid=void_model_valid,
            mass_flux_kg_m2_s=mass_fluxes,
            velocity_m_s=velocities,
            liquid_velocity_m_s=liquid_velocities,
            vapor_velocity_m_s=vapor_velocities,
            reynolds=reynolds,
            prandtl=prandtl_values,
            nusselt=nusselt_values,
            viscosity_Pa_s=viscosity_values,
            conductivity_W_mK=conductivity_values,
            surface_tension_N_m=surface_tension_values,
            friction_factor=friction,
            two_phase_friction_multiplier=friction_multiplier,
            liquid_reynolds=liquid_reynolds,
            vapor_reynolds=vapor_reynolds,
            two_phase_friction_valid=two_phase_friction_valid,
            two_phase_friction_detail=tuple(two_phase_friction_details),
            mixture_density_kg_m3=mixture_density,
            friction_pressure_drop_kpa=friction_dp,
            gravity_pressure_drop_kpa=gravity_dp,
            acceleration_pressure_drop_kpa=acceleration_dp,
            total_pressure_drop_kpa=total_dp,
            cumulative_friction_pressure_drop_kpa=cumulative_friction_dp,
            cumulative_gravity_pressure_drop_kpa=cumulative_gravity_dp,
            cumulative_acceleration_pressure_drop_kpa=cumulative_acceleration_dp,
            cumulative_pressure_drop_kpa=cumulative_pressure_drop,
            heat_transfer_coefficient_W_m2K=htc,
            surface_heat_flux_W_m2=heat_flux,
            linear_heat_rate_W_m=linear_heat,
            base_linear_heat_rate_W_m=base_linear_heat,
            axial_heat_shape_factor=shape,
            base_axial_heat_shape_factor=base_shape,
            localized_power_factor=localized_factor,
            combined_power_factor=combined_power_factor,
            boiling_onset_margin_C=boiling_onset_margin,
            critical_heat_flux_W_m2=chf,
            dnbr=dnbr,
            chf_correlation_valid=chf_valid,
            chf_predictions_W_m2=chf_predictions,
            chf_validity=chf_validity,
            chf_interpolation_detail={key: tuple(values) for key, values in chf_details.items()},
            selected_chf_key=inputs.chf_key,
            nucleate_boiling_active=boiling_active,
            wall_heat_transfer_mode=tuple(heat_transfer_modes),
            flow_regime=tuple(regimes),
            validity_messages=tuple(sorted(messages)),
            inlet_enthalpy_kj_kg=inlet.enthalpy_kj_kg,
            outlet_enthalpy_kj_kg=outlet_enthalpy,
            outlet_pressure_mpa=outlet_pressure,
            outlet_temperature_C=outlet_state.temperature_C,
            outlet_equilibrium_quality=outlet_quality,
            outlet_void_fraction=outlet_void,
            outlet_flow_regime=outlet_regime,
            deposited_power_W=deposited_power,
            heated_surface_area_m2=geometry.wetted_perimeter_m * geometry.heated_length_m,
            heat_shape_key=inputs.heat_shape_key,
            heat_shape_parameter=inputs.heat_shape_parameter,
            preserve_power_with_local_factors=inputs.preserve_power_with_local_factors,
            hot_factor_combination_method=inputs.hot_factor_combination_method,
            onset_nucleate_boiling_height_m=boiling_regions.onset_nucleate_boiling_height_m,
            bulk_boiling_height_m=boiling_regions.bulk_boiling_height_m,
            nonboiling_length_m=boiling_regions.nonboiling_length_m,
            subcooled_boiling_length_m=boiling_regions.subcooled_boiling_length_m,
            bulk_two_phase_length_m=boiling_regions.bulk_two_phase_length_m,
            provenance=provenance,
        )


def run_statistical_hot_channel(
    model: SingleChannelModel,
    geometry: ChannelGeometry,
    inputs: ChannelInputs,
    settings: StatisticalSettings,
) -> StatisticalResult:
    if settings.sample_count < 1:
        raise ValueError("sample_count must be positive")
    rng = np.random.default_rng(settings.seed)
    power = np.clip(
        rng.normal(
            inputs.power_factor,
            inputs.power_factor * settings.power_sigma_fraction,
            settings.sample_count,
        ),
        0.5, 2.0,
    )
    flow = np.clip(
        rng.normal(
            inputs.flow_factor,
            inputs.flow_factor * settings.flow_sigma_fraction,
            settings.sample_count,
        ),
        0.2, 2.0,
    )
    pitch = rng.normal(geometry.rod_pitch_m, geometry.rod_pitch_m * settings.pitch_sigma_fraction, settings.sample_count)
    diameter = rng.normal(
        geometry.rod_outer_diameter_m,
        geometry.rod_outer_diameter_m * settings.diameter_sigma_fraction,
        settings.sample_count,
    )
    peak_wall = np.empty(settings.sample_count)
    min_dnbr = np.empty(settings.sample_count)
    for i in range(settings.sample_count):
        sampled_diameter = max(
            float(diameter[i]), geometry.clad_inner_diameter_m * 1.001
        )
        sampled_geometry = replace(
            geometry,
            rod_pitch_m=max(float(pitch[i]), sampled_diameter * 1.01),
            rod_outer_diameter_m=sampled_diameter,
        )
        sampled_inputs = replace(inputs, power_factor=float(power[i]), flow_factor=float(flow[i]))
        result = model.solve(sampled_geometry, sampled_inputs)
        peak_wall[i] = result.peak_wall_temperature_C
        min_dnbr[i] = result.minimum_dnbr
    return StatisticalResult(peak_wall, min_dnbr, power, flow)
