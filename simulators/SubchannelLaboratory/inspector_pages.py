"""Pure HTML rendering for the Solution Inspector calculation tabs."""

from __future__ import annotations

import numpy as np


def _number(value: float, digits: int = 5) -> str:
    return "unavailable" if not np.isfinite(value) else f"{value:.{digits}g}"


def _table(rows: list[tuple[str, str]]) -> str:
    body = "".join(
        f"<tr><td style='padding:3px 12px 3px 0;color:#9fcbe3'>{name}</td>"
        f"<td style='padding:3px;color:#ffffff'>{value}</td></tr>"
        for name, value in rows
    )
    return f"<table>{body}</table>"


def render_inspector_pages(result, geometry, node: int, *, statistical: bool,
                           samples: int, seed: int) -> dict[str, str]:
    """Return all inspector page bodies without depending on Qt widgets."""
    i = node
    provenance = {entry.quantity: entry for entry in result.provenance}
    transport = provenance["transport_properties"]
    friction_model = provenance["friction_factor"]
    heat_model = provenance["single_phase_heat_transfer"]
    boiling_model = provenance["nucleate_boiling"]
    heat_shape_model = provenance["axial_heat_shape"]
    void_model = provenance["void_fraction"]
    pressure_model = provenance["frictional_pressure_drop"]
    gravity_model = provenance["gravitational_pressure_drop"]
    acceleration_model = provenance["acceleration_pressure_drop"]
    chf_model = provenance["critical_heat_flux"]
    comparison_rows = []
    for key, values in result.chf_predictions_W_m2.items():
        value = values[i] / 1.0e6
        status = "VALID" if result.chf_validity[key][i] else "OUTSIDE PUBLISHED DOMAIN"
        comparison_rows.append((f"{key} prediction", f"{_number(value, 7)} MW/m² — {status}"))
        if key == "groeneveld_2006":
            detail = result.chf_interpolation_detail[key][i].replace("; ", "<br>")
            comparison_rows.append(("Groeneveld interpolation / uncertainty", detail))
    onb = (f"{result.onset_nucleate_boiling_height_m:.7g} m"
           if np.isfinite(result.onset_nucleate_boiling_height_m) else "not reached")
    bulk = (f"{result.bulk_boiling_height_m:.7g} m"
            if np.isfinite(result.bulk_boiling_height_m) else "not reached")

    return {
        "Geometry": "<h2>Geometry construction</h2>" + _table([
            ("Flow area", f"A = p² − πD²/4 = {geometry.flow_area_m2:.7g} m²"),
            ("Wetted perimeter", f"Pᵥ = πD = {geometry.wetted_perimeter_m:.7g} m"),
            ("Hydraulic diameter", f"Dₕ = 4A/Pᵥ = {geometry.hydraulic_diameter_m:.7g} m"),
            ("Axial cell length", f"Δz = Lh/N = {geometry.heated_length_m/result.z_m.size:.6g} m"),
            ("Total illustrated length", f"{geometry.total_channel_length_m:.5g} m"),
            ("Heated transfer area", f"A<sub>h</sub> = P<sub>w</sub>L<sub>h</sub> = {result.heated_surface_area_m2:.7g} m&sup2;"),
        ]),
        "Properties": (
            f"<h2>Selected-node thermodynamic and transport properties</h2><p><b>{transport.model_label}</b><br>"
            f"{transport.citation}</p>" + _table([
                ("Selected-node pressure", f"{result.pressure_mpa[i]:.6g} MPa"),
                ("Selected-node enthalpy", f"{result.enthalpy_kj_kg[i]:.6g} kJ/kg"),
                ("Bulk / saturation temperature", f"{result.bulk_temperature_C[i]:.4f} / {result.saturation_temperature_C[i]:.4f} °C"),
                ("Viscosity", f"{result.viscosity_Pa_s[i]:.6e} Pa·s"),
                ("Conductivity", f"{result.conductivity_W_mK[i]:.6g} W/m·K"),
                ("Surface tension", f"{result.surface_tension_N_m[i]:.6g} N/m"),
            ])
        ),
        "Flow": (
            f"<h2>Flow parameters</h2><p><b>{friction_model.model_label}</b> — {friction_model.citation}</p>"
            + _table([
                ("Mass flux", f"G = ṁ/A = {result.mass_flux_kg_m2_s[i]:.6g} kg/m²·s"),
                ("Velocity", f"v = G/ρ = {result.velocity_m_s[i]:.6g} m/s"),
                ("Mixture density", f"{result.mixture_density_kg_m3[i]:.6g} kg/m&sup3;"),
                ("Liquid / vapor velocity", f"{result.liquid_velocity_m_s[i]:.6g} / {result.vapor_velocity_m_s[i]:.6g} m/s"),
                ("Reynolds number", f"Re = GDₕ/μ = {result.reynolds[i]:.6g}"),
                ("Prandtl number", f"Pr = cpμ/k = {result.prandtl[i]:.6g}"),
                ("Friction factor", f"f = {result.friction_factor[i]:.7g}"),
            ])
        ),
        "Heat Transfer": (
            f"<h2>Selected-node heat transfer and ONB selection</h2><p>Single phase: <b>{heat_model.model_label}</b> "
            f"({heat_model.citation})<br>Boiling: <b>{boiling_model.model_label}</b> ({boiling_model.citation})<br>"
            f"Heat shape: <b>{heat_shape_model.model_label}</b> — {heat_shape_model.note}</p>" + _table([
                ("Selected-node shape factor", f"{result.axial_heat_shape_factor[i]:.7g}"),
                ("Shape offset / skew parameter", f"{result.heat_shape_parameter:.7g}"),
                ("Localized axial nuclear-power multiplier", f"{result.localized_power_factor[i]:.7g}"),
                ("Overall power factor at node", f"{result.combined_power_factor[i]:.7g}"),
                ("Localized-factor mode", "preserve total power" if result.preserve_power_with_local_factors else "additional power"),
                ("Hot-factor combination", result.hot_factor_combination_method.replace("_", " ").title()),
                ("Selected-node linear heat", f"{result.linear_heat_rate_W_m[i] / 1000.0:.7g} kW/m"),
                ("Applied heat flux", f"q″ = {result.surface_heat_flux_W_m2[i]:.6g} W/m²"),
                ("CHANNEL TOTAL: heat transferred", f"Q = {result.deposited_power_W / 1000.0:.7g} kW"),
                ("CHANNEL TOTAL: heated area", f"A<sub>h</sub> = {result.heated_surface_area_m2:.7g} m&sup2;"),
                ("CHANNEL AVERAGE: surface heat flux", f"Q/A<sub>h</sub> = {result.average_surface_heat_flux_W_m2 / 1.0e6:.7g} MW/m&sup2;"),
                ("Nusselt number", f"Nu = {result.nusselt[i]:.6g}"),
                ("Heat-transfer coefficient", f"h = Nu·k/Dₕ = {result.heat_transfer_coefficient_W_m2K[i]:.6g} W/m²·K"),
                ("Active model", result.wall_heat_transfer_mode[i]),
                ("Coolant-side wall", f"{result.wall_temperature_C[i]:.5g} °C"),
                ("Inner cladding", f"{result.inner_clad_temperature_C[i]:.5g} °C"),
                ("CHANNEL: ONB elevation", onb),
                ("CHANNEL: bulk saturation elevation", bulk),
                ("CHANNEL: non-boiling length", f"{result.nonboiling_length_m:.7g} m"),
                ("CHANNEL: subcooled-boiling length", f"{result.subcooled_boiling_length_m:.7g} m"),
                ("CHANNEL: bulk two-phase length", f"{result.bulk_two_phase_length_m:.7g} m"),
            ])
        ),
        "Quality / Void": (
            f"<h2>Selected-node quality and void</h2><p><b>{void_model.model_label}</b><br>"
            f"{void_model.citation}<br>{void_model.note}</p>" + _table([
                ("Equilibrium quality", f"xₑ = (h−hf)/hfg = {result.equilibrium_quality[i]:.7g}"),
                ("Void fraction", f"α = {result.void_fraction[i]:.7g}"),
                ("Slip ratio", f"S = u<sub>g</sub>/u<sub>l</sub> = {result.slip_ratio[i]:.7g}"),
                ("Model validity", "VALID" if result.void_model_valid[i] else "OUTSIDE RECOMMENDED USE"),
                ("Bulk regime", result.flow_regime[i]),
                ("Nucleate boiling selected", "yes" if result.nucleate_boiling_active[i] else "no"),
                ("OUTLET: temperature", f"{result.outlet_temperature_C:.6g} &deg;C"),
                ("OUTLET: equilibrium quality", f"{result.outlet_equilibrium_quality:.7g}"),
                ("OUTLET: void fraction", f"{result.outlet_void_fraction:.7g}"),
                ("OUTLET: regime", result.outlet_flow_regime),
            ])
        ),
        "Pressure Drop": (
            f"<h2>Selected-node pressure-drop solution</h2><p><b>{pressure_model.model_label}</b><br>"
            f"{pressure_model.citation}<br>{pressure_model.note}<br><b>{gravity_model.model_label}</b>: "
            f"{gravity_model.citation}<br><b>{acceleration_model.model_label}</b>: {acceleration_model.citation}</p>"
            + _table([
                ("Selected-node pressure", f"{result.pressure_mpa[i]:.7g} MPa"),
                ("OUTLET: pressure", f"{result.outlet_pressure_mpa:.7g} MPa"),
                ("Node friction from selected model", f"{result.friction_pressure_drop_kpa[i]:.7g} kPa"),
                ("Node elevation", f"rho_m g dz sin(theta) = {result.gravity_pressure_drop_kpa[i]:.7g} kPa"),
                ("Node acceleration", f"G&sup2;(M_out-M_in) = {result.acceleration_pressure_drop_kpa[i]:.7g} kPa"),
                ("Node total", f"{result.node_pressure_drop_kpa[i]:.7g} kPa"),
                ("CHANNEL TOTAL: heated pressure drop", f"<b>{result.total_heated_pressure_drop_kpa:.7g} kPa</b>"),
                ("CHANNEL TOTAL: friction", f"{result.total_friction_pressure_drop_kpa:.7g} kPa"),
                ("CHANNEL TOTAL: elevation", f"{result.total_gravity_pressure_drop_kpa:.7g} kPa"),
                ("CHANNEL TOTAL: acceleration", f"{result.total_acceleration_pressure_drop_kpa:.7g} kPa"),
                ("Cumulative total to node", f"{result.cumulative_pressure_drop_kpa[i]:.7g} kPa"),
                ("Mixture density", f"{result.mixture_density_kg_m3[i]:.7g} kg/m&sup3;"),
                ("Two-phase multiplier", f"{result.two_phase_friction_multiplier[i]:.7g}"),
                ("Interpolation basis", result.two_phase_friction_detail[i] or "Not table-interpolated at this node"),
                ("Liquid / vapor Reynolds", f"{result.liquid_reynolds[i]:.7g} / {result.vapor_reynolds[i]:.7g}"),
                ("Friction-model validity", "VALID" if result.two_phase_friction_valid[i] else "OUTSIDE RECOMMENDED USE"),
                ("Darcy factor", f"{result.friction_factor[i]:.7g}"),
                ("Scope", "Heated section; selected void/slip and friction models; local losses excluded"),
            ])
        ),
        "CHF / Margin": (
            f"<h2>Critical heat flux and margin</h2><p><b>{chf_model.model_label}</b> — "
            f"{chf_model.citation}<br>{chf_model.note}</p>" + _table([
                ("Validity", "<span style='color:#55ff9a'>VALID</span>" if result.chf_correlation_valid[i]
                 else "<span style='color:#ffbf3f'>UNAVAILABLE</span>"),
                ("Applied heat flux", f"{result.surface_heat_flux_W_m2[i]/1e6:.7g} MW/m²"),
                ("Critical heat flux", f"{_number(result.critical_heat_flux_W_m2[i]/1e6, 7)} MW/m²"),
                ("DNBR", _number(result.dnbr[i], 7)),
            ] + comparison_rows)
        ),
        "Statistics": "<h2>Statistical hot-channel calculation</h2>" + _table([
            ("Selected mode", "Statistical" if statistical else "Deterministic"),
            ("Samples", str(samples)),
            ("Seed", str(seed)),
            ("Power-factor σ", "3% relative"),
            ("Flow-factor σ", "2% relative"),
            ("Pitch / diameter σ", "0.1% relative each"),
        ]),
    }
