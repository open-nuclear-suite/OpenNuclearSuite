"""Machine-readable deterministic channel-result export."""

from __future__ import annotations

import csv
from pathlib import Path


BASE_COLUMNS = (
    "node", "z_m", "pressure_MPa", "bulk_temperature_C",
    "saturation_temperature_C", "wall_temperature_C", "inner_clad_temperature_C",
    "enthalpy_kJ_kg", "equilibrium_quality", "void_fraction", "slip_ratio",
    "void_model_valid", "mass_flux_kg_m2_s", "velocity_m_s",
    "liquid_velocity_m_s", "vapor_velocity_m_s", "Re", "Pr", "Nu",
    "viscosity_Pa_s", "conductivity_W_mK", "surface_tension_N_m",
    "friction_factor", "two_phase_friction_multiplier", "two_phase_friction_valid",
    "friction_dP_kPa", "gravity_dP_kPa", "acceleration_dP_kPa", "total_dP_kPa",
    "cumulative_friction_dP_kPa", "cumulative_gravity_dP_kPa",
    "cumulative_acceleration_dP_kPa", "cumulative_total_dP_kPa",
    "heat_transfer_coefficient_W_m2K", "surface_heat_flux_W_m2",
    "linear_heat_rate_W_m", "base_linear_heat_rate_W_m", "axial_heat_shape_factor",
    "base_axial_heat_shape_factor", "localized_power_factor", "combined_power_factor",
    "boiling_onset_margin_C",
    "selected_CHF_W_m2", "DNBR", "selected_CHF_valid", "nucleate_boiling_active",
    "flow_regime", "wall_heat_transfer_mode", "two_phase_friction_detail",
)

CASE_COLUMNS = (
    "selected_CHF_model", "heat_shape_model", "heat_shape_parameter",
    "hot_factor_combination_method", "preserve_power_with_local_factors", "deposited_power_W",
    "heated_surface_area_m2", "average_surface_heat_flux_W_m2",
    "total_heated_dP_kPa", "total_friction_dP_kPa", "total_gravity_dP_kPa",
    "total_acceleration_dP_kPa", "outlet_pressure_MPa", "outlet_temperature_C",
    "outlet_enthalpy_kJ_kg", "outlet_equilibrium_quality", "outlet_void_fraction",
    "outlet_flow_regime", "ONB_height_m", "bulk_boiling_height_m",
    "nonboiling_length_m", "subcooled_boiling_length_m", "bulk_two_phase_length_m",
)


def channel_result_header(result) -> tuple[str, ...]:
    correlation_columns: list[str] = []
    for key in result.chf_predictions_W_m2:
        correlation_columns.extend((
            f"CHF_{key}_W_m2", f"CHF_{key}_valid", f"CHF_{key}_detail",
        ))
    return BASE_COLUMNS + tuple(correlation_columns) + CASE_COLUMNS


def channel_result_rows(result):
    case_values = (
        result.selected_chf_key, result.heat_shape_key, result.heat_shape_parameter,
        result.hot_factor_combination_method, result.preserve_power_with_local_factors,
        result.deposited_power_W,
        result.heated_surface_area_m2, result.average_surface_heat_flux_W_m2,
        result.total_heated_pressure_drop_kpa, result.total_friction_pressure_drop_kpa,
        result.total_gravity_pressure_drop_kpa, result.total_acceleration_pressure_drop_kpa,
        result.outlet_pressure_mpa, result.outlet_temperature_C,
        result.outlet_enthalpy_kj_kg, result.outlet_equilibrium_quality,
        result.outlet_void_fraction, result.outlet_flow_regime,
        result.onset_nucleate_boiling_height_m, result.bulk_boiling_height_m,
        result.nonboiling_length_m, result.subcooled_boiling_length_m,
        result.bulk_two_phase_length_m,
    )
    for index in range(result.z_m.size):
        values = (
            index + 1, result.z_m[index], result.pressure_mpa[index],
            result.bulk_temperature_C[index], result.saturation_temperature_C[index],
            result.wall_temperature_C[index], result.inner_clad_temperature_C[index],
            result.enthalpy_kj_kg[index], result.equilibrium_quality[index],
            result.void_fraction[index], result.slip_ratio[index],
            bool(result.void_model_valid[index]), result.mass_flux_kg_m2_s[index],
            result.velocity_m_s[index], result.liquid_velocity_m_s[index],
            result.vapor_velocity_m_s[index], result.reynolds[index],
            result.prandtl[index], result.nusselt[index], result.viscosity_Pa_s[index],
            result.conductivity_W_mK[index], result.surface_tension_N_m[index],
            result.friction_factor[index], result.two_phase_friction_multiplier[index],
            bool(result.two_phase_friction_valid[index]),
            result.friction_pressure_drop_kpa[index], result.gravity_pressure_drop_kpa[index],
            result.acceleration_pressure_drop_kpa[index], result.total_pressure_drop_kpa[index],
            result.cumulative_friction_pressure_drop_kpa[index],
            result.cumulative_gravity_pressure_drop_kpa[index],
            result.cumulative_acceleration_pressure_drop_kpa[index],
            result.cumulative_pressure_drop_kpa[index],
            result.heat_transfer_coefficient_W_m2K[index],
            result.surface_heat_flux_W_m2[index], result.linear_heat_rate_W_m[index],
            result.base_linear_heat_rate_W_m[index], result.axial_heat_shape_factor[index],
            result.base_axial_heat_shape_factor[index], result.localized_power_factor[index],
            result.combined_power_factor[index], result.boiling_onset_margin_C[index],
            result.critical_heat_flux_W_m2[index], result.dnbr[index],
            bool(result.chf_correlation_valid[index]),
            bool(result.nucleate_boiling_active[index]), result.flow_regime[index],
            result.wall_heat_transfer_mode[index], result.two_phase_friction_detail[index],
        )
        correlation_values: list[object] = []
        for key, predictions in result.chf_predictions_W_m2.items():
            correlation_values.extend((
                predictions[index], bool(result.chf_validity[key][index]),
                result.chf_interpolation_detail[key][index],
            ))
        yield values + tuple(correlation_values) + case_values


def write_channel_result_csv(path: str | Path, result) -> Path:
    destination = Path(path)
    with destination.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(channel_result_header(result))
        writer.writerows(channel_result_rows(result))
    return destination
