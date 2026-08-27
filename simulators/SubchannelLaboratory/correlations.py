"""Small, traceable correlation registry for the subchannel laboratory."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class CorrelationValue:
    value: float
    valid: bool
    message: str = ""


@dataclass(frozen=True)
class Correlation:
    key: str
    label: str
    citation: str
    evaluate: Callable[..., CorrelationValue]


@dataclass(frozen=True)
class BoilingWallTemperature:
    temperature_C: float
    valid: bool
    message: str = ""


def _result(value: float, valid: bool, domain: str) -> CorrelationValue:
    return CorrelationValue(float(value), valid, "" if valid else domain)


def blasius_friction(reynolds: float, relative_roughness: float = 0.0) -> CorrelationValue:
    """Darcy friction factor for smooth turbulent tubes."""
    valid = 4.0e3 <= reynolds <= 1.0e5 and relative_roughness <= 1.0e-5
    value = 0.3164 / max(reynolds, 1.0) ** 0.25
    return _result(value, valid, "Blasius: 4,000 <= Re <= 100,000; smooth wall")


def haaland_friction(reynolds: float, relative_roughness: float = 0.0) -> CorrelationValue:
    """Explicit Darcy friction-factor approximation."""
    valid = reynolds >= 4.0e3 and 0.0 <= relative_roughness <= 0.05
    argument = (relative_roughness / 3.7) ** 1.11 + 6.9 / max(reynolds, 1.0)
    value = (-1.8 * math.log10(max(argument, 1.0e-16))) ** -2
    return _result(value, valid, "Haaland: Re >= 4,000 and 0 <= roughness/D <= 0.05")


def churchill_friction(reynolds: float, relative_roughness: float = 0.0) -> CorrelationValue:
    """All-regime Darcy friction factor of Churchill (1977)."""
    re = max(reynolds, 1.0e-12)
    a = (2.457 * math.log(1.0 / ((7.0 / re) ** 0.9 + 0.27 * relative_roughness))) ** 16
    b = (37530.0 / re) ** 16
    value = 8.0 * ((8.0 / re) ** 12 + 1.0 / (a + b) ** 1.5) ** (1.0 / 12.0)
    valid = re > 0.0 and 0.0 <= relative_roughness <= 0.05
    return _result(value, valid, "Churchill: positive Re and 0 <= roughness/D <= 0.05")


def dittus_boelter(reynolds: float, prandtl: float, heating: bool = True) -> CorrelationValue:
    exponent = 0.4 if heating else 0.3
    value = 0.023 * max(reynolds, 1.0) ** 0.8 * max(prandtl, 1.0e-9) ** exponent
    valid = reynolds >= 1.0e4 and 0.7 <= prandtl <= 160.0
    return _result(value, valid, "Dittus-Boelter: Re >= 10,000 and 0.7 <= Pr <= 160")


def gnielinski(reynolds: float, prandtl: float, friction_factor: float) -> CorrelationValue:
    numerator = (friction_factor / 8.0) * max(reynolds - 1000.0, 0.0) * prandtl
    denominator = 1.0 + 12.7 * math.sqrt(max(friction_factor / 8.0, 0.0)) * (
        prandtl ** (2.0 / 3.0) - 1.0
    )
    value = numerator / max(denominator, 1.0e-12)
    valid = 3.0e3 <= reynolds <= 5.0e6 and 0.5 <= prandtl <= 2000.0
    return _result(value, valid, "Gnielinski: 3,000 <= Re <= 5e6 and 0.5 <= Pr <= 2,000")


def jens_lottes_wall_temperature_C(
    heat_flux_W_m2: float, pressure_mpa: float, saturation_temperature_C: float, **_: float,
) -> BoilingWallTemperature:
    """Jens-Lottes nucleate-boiling wall temperature in its original units."""
    pressure_psia = pressure_mpa * 145.0377377
    heat_flux_btu_h_ft2 = max(heat_flux_W_m2, 0.0) / 3.15459075
    superheat_F = 60.0 * math.exp(-pressure_psia / 900.0) * (
        heat_flux_btu_h_ft2 / 1.0e6
    ) ** 0.25
    valid = 3.5 <= pressure_mpa <= 14.0 and heat_flux_W_m2 > 0.0
    message = "" if valid else "Jens-Lottes: documented teaching range 3.5 <= P <= 14 MPa"
    return BoilingWallTemperature(saturation_temperature_C + superheat_F / 1.8, valid, message)


def thom_wall_temperature_C(
    heat_flux_W_m2: float, pressure_mpa: float, saturation_temperature_C: float, **_: float,
) -> BoilingWallTemperature:
    """Thom high-pressure water nucleate-boiling wall temperature."""
    superheat_C = 0.022 * math.sqrt(max(heat_flux_W_m2, 0.0)) / math.exp(pressure_mpa / 8.6)
    valid = 5.2 <= pressure_mpa <= 13.2 and 2.9e5 <= heat_flux_W_m2 <= 1.57e6
    message = "" if valid else "Thom: 5.2 <= P <= 13.2 MPa and 0.29 <= q'' <= 1.57 MW/m2"
    return BoilingWallTemperature(saturation_temperature_C + superheat_C, valid, message)


def _surface_tension_water_N_m(saturation_temperature_C: float) -> float:
    reduced = max(1.0 - (saturation_temperature_C + 273.15) / 647.096, 1.0e-8)
    return 0.2358 * reduced**1.256 * (1.0 - 0.625 * reduced)


def chen_wall_temperature_C(
    heat_flux_W_m2: float,
    pressure_mpa: float,
    saturation_temperature_C: float,
    bulk_temperature_C: float,
    mass_flux_kg_m2_s: float,
    hydraulic_diameter_m: float,
    equilibrium_quality: float,
    liquid_density_kg_m3: float,
    vapor_density_kg_m3: float,
    liquid_viscosity_Pa_s: float,
    liquid_conductivity_W_mK: float,
    liquid_cp_J_kgK: float,
    latent_heat_J_kg: float,
    saturation_pressure_at_temperature: Callable[[float], float],
    vapor_viscosity_Pa_s: float = 1.3e-5,
    surface_tension_N_m: float | None = None,
    **_: float,
) -> BoilingWallTemperature:
    """Solve the Chen convective-plus-nucleate-boiling superposition.

    The implementation follows the public PARET/ANL description. Water vapor
    viscosity is represented by a small teaching approximation pending expanded
    transport-property tables.
    """
    x = min(max(equilibrium_quality, 1.0e-6), 0.999999)
    x_tt = ((1.0 - x) / x) ** 0.9 * (
        vapor_density_kg_m3 / liquid_density_kg_m3
    ) ** 0.5 * (liquid_viscosity_Pa_s / vapor_viscosity_Pa_s) ** 0.1
    inverse_x_tt = 1.0 / max(x_tt, 1.0e-12)
    enhancement = 1.0 if inverse_x_tt <= 0.1 else 2.35 * (inverse_x_tt + 0.213) ** 0.736
    re_liquid = mass_flux_kg_m2_s * max(1.0 - x, 1.0e-5) * hydraulic_diameter_m / liquid_viscosity_Pa_s
    prandtl = liquid_cp_J_kgK * liquid_viscosity_Pa_s / liquid_conductivity_W_mK
    h_macro = 0.023 * max(re_liquid, 1.0) ** 0.8 * prandtl**0.4 * (
        liquid_conductivity_W_mK / hydraulic_diameter_m
    )
    suppression_re = re_liquid * enhancement**1.25
    suppression = 1.0 / (1.0 + 2.53e-6 * suppression_re**1.17)
    surface_tension = (
        _surface_tension_water_N_m(saturation_temperature_C)
        if surface_tension_N_m is None else surface_tension_N_m
    )
    saturation_temperature_K = saturation_temperature_C + 273.15
    specific_volume_change = 1.0 / vapor_density_kg_m3 - 1.0 / liquid_density_kg_m3
    clapeyron_slope_Pa_K = latent_heat_J_kg / (
        saturation_temperature_K * max(specific_volume_change, 1.0e-12)
    )
    coefficient = 0.00122 * (
        liquid_conductivity_W_mK**0.79
        * liquid_cp_J_kgK**0.45
        * liquid_density_kg_m3**0.49
    ) / (
        surface_tension**0.5
        * liquid_viscosity_Pa_s**0.29
        * latent_heat_J_kg**0.24
        * vapor_density_kg_m3**0.24
    )

    def predicted_flux(wall_C: float) -> float:
        superheat = max(wall_C - saturation_temperature_C, 0.0)
        # Local Clausius-Clapeyron pressure increment avoids extrapolating the
        # finite bundled saturation table above its maximum pressure.
        delta_pressure = max(clapeyron_slope_Pa_K * superheat, 0.0)
        h_micro = coefficient * superheat**0.24 * delta_pressure**0.75
        return (
            h_macro * enhancement * max(wall_C - bulk_temperature_C, 0.0)
            + h_micro * suppression * superheat
        )

    low = max(saturation_temperature_C, bulk_temperature_C)
    high = min(saturation_temperature_C + 150.0, 373.0)
    for _iteration in range(60):
        middle = 0.5 * (low + high)
        if predicted_flux(middle) < heat_flux_W_m2:
            low = middle
        else:
            high = middle
    temperature = 0.5 * (low + high)
    valid = (
        heat_flux_W_m2 > 0.0
        and pressure_mpa > 0.0
        and re_liquid > 0.0
        and temperature < 373.0 - 1.0e-6
    )
    message = "" if valid else "Chen solution reached the teaching property/domain boundary"
    return BoilingWallTemperature(temperature, valid, message)


FRICTION_CORRELATIONS = {
    item.key: item for item in (
        Correlation("blasius", "Blasius (smooth)", "Blasius (1913)", blasius_friction),
        Correlation("haaland", "Haaland", "Haaland (1983)", haaland_friction),
        Correlation("churchill", "Churchill", "Churchill (1977)", churchill_friction),
    )
}

HEAT_TRANSFER_CORRELATIONS = {
    item.key: item for item in (
        Correlation("dittus_boelter", "Dittus-Boelter", "Dittus and Boelter (1930)", dittus_boelter),
        Correlation("gnielinski", "Gnielinski", "Gnielinski (1976)", gnielinski),
    )
}

BOILING_CORRELATIONS = {
    item.key: item for item in (
        Correlation("jens_lottes", "Jens-Lottes", "Jens and Lottes (1951)", jens_lottes_wall_temperature_C),
        Correlation("thom", "Thom", "Thom et al. (1965)", thom_wall_temperature_C),
        Correlation("chen", "Chen", "Chen (1963); PARET/ANL implementation", chen_wall_temperature_C),
    )
}
