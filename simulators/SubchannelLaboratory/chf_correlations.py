"""Open CHF correlations used for selection and classroom comparison."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .groeneveld_lut import interpolate_groeneveld_2006

@dataclass(frozen=True)
class CHFCorrelation:
    key: str
    label: str
    citation: str
    note: str


CHF_CORRELATIONS = {
    "tong_w3": CHFCorrelation(
        "tong_w3", "Tong W-3", "Tong (1967); TID-25887",
        "Uniform-flux teaching form without bundle/grid corrections.",
    ),
    "biasi": CHFCorrelation(
        "biasi", "Biasi", "Biasi et al. (1967); equations reproduced in ORNL/SPR-2023/3125",
        "Local round-tube correlation; no bundle, grid, or non-uniform-flux correction.",
    ),
    "bowring": CHFCorrelation(
        "bowring", "Bowring", "Bowring (1972), AEEW-R789; ORNL/SPR-2023/3125 §12.9.4",
        "Modified local-quality form for uniformly heated round tubes; no bundle/grid correction.",
    ),
    "epri_1": CHFCorrelation(
        "epri_1", "EPRI-1",
        "Reddy and Fighetti (1983); equations reproduced in PNNL-29720, Sec. 4.2.4.1",
        "Base rod-bundle form using inlet quality and local heat flux; cold-wall, grid, and non-uniform corrections are off.",
    ),
    "groeneveld_2006": CHFCorrelation(
        "groeneveld_2006", "Groeneveld 2006 LUT (24 pressure planes)",
        "Groeneveld et al., Nuclear Engineering and Design 237 (2007) 1909–1922",
        "Bounded interpolation of the complete 24-plane, 8 mm vertical-tube cube; selected K factors are explicit.",
    ),
}


def biasi_critical_heat_flux_W_m2(pressure_mpa: float, mass_flux_kg_m2_s: float,
                                  quality: float, hydraulic_diameter_m: float) -> float:
    """Original local Biasi correlation, returning NaN outside its data range.

    The published mixed units are retained internally: pressure in bar,
    diameter in cm, mass flux in g/(cm² s), and CHF in kW/m².
    """
    if not (0.27 <= pressure_mpa <= 14.0):
        return float("nan")
    if not (100.0 <= mass_flux_kg_m2_s <= 6000.0):
        return float("nan")
    if not (0.003 <= hydraulic_diameter_m <= 0.0375) or not quality < 1.0:
        return float("nan")
    pressure_bar = pressure_mpa * 10.0
    diameter_cm = hydraulic_diameter_m * 100.0
    mass_flux_cgs = mass_flux_kg_m2_s / 10.0
    exponent = 0.4 if diameter_cm >= 1.0 else 0.6
    pressure_f = 0.7249 + 0.099 * pressure_bar * math.exp(-0.032 * pressure_bar)
    pressure_h = (
        -1.159 + 0.149 * pressure_bar * math.exp(-0.019 * pressure_bar)
        + 8.99 * pressure_bar / (10.0 + pressure_bar**2)
    )
    low_quality = (
        1.883e4 / diameter_cm**exponent * mass_flux_cgs**(1.0 / 6.0)
        * (pressure_f / mass_flux_cgs**(1.0 / 6.0) - quality)
    )
    high_quality = (
        3.78e4 * pressure_h / (diameter_cm**exponent * mass_flux_cgs**0.6)
        * (1.0 - quality)
    )
    if mass_flux_kg_m2_s < 300.0:
        return max(0.0, high_quality) * 1000.0
    return max(0.0, low_quality, high_quality) * 1000.0


def bowring_critical_heat_flux_W_m2(pressure_mpa: float, mass_flux_kg_m2_s: float,
                                    quality: float, hydraulic_diameter_m: float,
                                    latent_heat_J_kg: float,
                                    heated_length_m: float) -> float:
    """Modified local-quality Bowring correlation in the published SI form."""
    if not (0.234 <= pressure_mpa <= 18.96):
        return float("nan")
    if not (136.0 <= mass_flux_kg_m2_s <= 18_580.0):
        return float("nan")
    if not (0.00203 <= hydraulic_diameter_m <= 0.0447):
        return float("nan")
    if not (0.152 <= heated_length_m <= 3.70) or not quality < 1.0:
        return float("nan")
    reduced_pressure = 0.145038 * pressure_mpa
    if reduced_pressure < 1.0:
        f1 = (
            reduced_pressure**18.942 * math.exp(20.89 * (1.0 - reduced_pressure))
            + 0.917
        ) / 1.917
        f2 = f1 / ((
            reduced_pressure**1.316 * math.exp(2.444 * (1.0 - reduced_pressure))
            + 0.309
        ) / 1.309)
        f3 = (
            reduced_pressure**17.023 * math.exp(16.658 * (1.0 - reduced_pressure))
            + 0.667
        ) / 1.667
    else:
        f1 = reduced_pressure**-0.368 * math.exp(0.648 * (1.0 - reduced_pressure))
        f2 = f1 / (
            reduced_pressure**-0.448 * math.exp(0.245 * (1.0 - reduced_pressure))
        )
        f3 = reduced_pressure**0.219
    f4 = f3 * reduced_pressure**1.649
    exponent = 2.0 - 0.5 * reduced_pressure
    coefficient_b = 0.25 * hydraulic_diameter_m * mass_flux_kg_m2_s
    coefficient_a = (
        0.57925 * f1 * latent_heat_J_kg * hydraulic_diameter_m * mass_flux_kg_m2_s
        / (1.0 + 0.0143 * f2 * hydraulic_diameter_m**0.5 * mass_flux_kg_m2_s)
    )
    coefficient_c = (
        0.077 * f3 * hydraulic_diameter_m * mass_flux_kg_m2_s
        / (1.0 + 0.347 * f4 * (mass_flux_kg_m2_s / 1356.0)**exponent)
    )
    chf_kw_m2 = 0.001 * (
        coefficient_a - coefficient_b * latent_heat_J_kg * quality
    ) / coefficient_c
    return max(0.0, chf_kw_m2) * 1000.0


def epri_1_critical_heat_flux_W_m2(
    pressure_mpa: float, mass_flux_kg_m2_s: float, quality: float,
    inlet_quality: float, local_heat_flux_W_m2: float,
) -> float:
    """Base EPRI-1 rod-bundle CHF formulation in its published mixed units."""
    pressure_psia = pressure_mpa * 145.0377377
    mass_flux_mlbm_hr_ft2 = mass_flux_kg_m2_s * 7.3733812e-4
    if not (200.0 <= pressure_psia <= 2400.0):
        return float("nan")
    if not (0.2 <= mass_flux_mlbm_hr_ft2 <= 4.5):
        return float("nan")
    if not (-0.25 <= quality <= 0.75 and -1.10 <= inlet_quality <= 0.0):
        return float("nan")
    if local_heat_flux_W_m2 <= 0.0:
        return float("nan")
    reduced_pressure = pressure_psia / 3208.2
    coefficient_a = (
        0.5328 * reduced_pressure**0.1212
        * mass_flux_mlbm_hr_ft2**(-0.3040 - 0.3285 * reduced_pressure)
    )
    coefficient_c = (
        1.6151 * reduced_pressure**1.4066
        * mass_flux_mlbm_hr_ft2**(0.4843 - 2.0749 * reduced_pressure)
    )
    local_heat_flux_mbtu_hr_ft2 = local_heat_flux_W_m2 / 3.154590745e6
    denominator = coefficient_c + (
        quality - inlet_quality
    ) / local_heat_flux_mbtu_hr_ft2
    if denominator <= 0.0:
        return float("nan")
    chf_mbtu_hr_ft2 = (coefficient_a - inlet_quality) / denominator
    return max(chf_mbtu_hr_ft2, 0.0) * 3.154590745e6


def evaluate_chf(key: str, pressure_mpa: float, mass_flux_kg_m2_s: float,
                 quality: float, hydraulic_diameter_m: float,
                 inlet_subcooling_kj_kg: float, latent_heat_J_kg: float,
                 heated_length_m: float, local_heat_flux_W_m2: float, *, rod_pitch_m: float,
                 rod_outer_diameter_m: float, rho_l: float, rho_g: float,
                 groeneveld_k1: bool, groeneveld_k2: bool,
                 groeneveld_k4: bool) -> tuple[float, str]:
    if key == "tong_w3":
        from hot_channel import w3_critical_heat_flux_W_m2

        return w3_critical_heat_flux_W_m2(
            pressure_mpa, mass_flux_kg_m2_s, quality,
            hydraulic_diameter_m, inlet_subcooling_kj_kg,
        ), "local equation; no interpolation"
    if key == "biasi":
        return biasi_critical_heat_flux_W_m2(
            pressure_mpa, mass_flux_kg_m2_s, quality, hydraulic_diameter_m
        ), "local equation; no interpolation"
    if key == "bowring":
        return bowring_critical_heat_flux_W_m2(
            pressure_mpa, mass_flux_kg_m2_s, quality, hydraulic_diameter_m,
            latent_heat_J_kg, heated_length_m,
        ), "local equation; no interpolation"
    if key == "epri_1":
        inlet_quality = -inlet_subcooling_kj_kg / (latent_heat_J_kg / 1000.0)
        value = epri_1_critical_heat_flux_W_m2(
            pressure_mpa, mass_flux_kg_m2_s, quality, inlet_quality,
            local_heat_flux_W_m2,
        )
        return value, (
            f"base EPRI-1; xin={inlet_quality:.5g}; local q={local_heat_flux_W_m2 / 1e6:.5g} MW/m2; "
            "cold-wall/grid/non-uniform correction factors off"
        )
    if key == "groeneveld_2006":
        result = interpolate_groeneveld_2006(
            pressure_mpa, mass_flux_kg_m2_s, quality, hydraulic_diameter_m,
            rod_pitch_m, rod_outer_diameter_m, heated_length_m, rho_l, rho_g,
            diameter_correction=groeneveld_k1,
            bundle_correction=groeneveld_k2,
            heated_length_correction=groeneveld_k4,
        )
        return result.chf_W_m2, result.detail
    raise KeyError(f"Unknown CHF correlation: {key}")
