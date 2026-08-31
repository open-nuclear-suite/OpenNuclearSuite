"""Public provenance for P2-2 PWR parameter-data replacements."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ParameterBasis:
    value: float
    unit: str
    source: str
    source_value: str
    conversion: str
    applicability: str


NRC_AP1000_FSER_CH1 = (
    "https://www.nrc.gov/sites/default/files/doc_library/cdn/legacy/"
    "reading-rm/doc-collections/nuregs/staff/sr1793/initial/chapter1.pdf"
)
NRC_AP1000_FSER_CH5 = (
    "https://www.nrc.gov/cdn/legacy/reading-rm/doc-collections/"
    "nuregs/staff/sr1793/initial/chapter5.pdf"
)
NRC_TRACE_AP1000 = (
    "https://www.govinfo.gov/content/pkg/GOVPUB-Y3_N88-PURL-gpo47583/"
    "pdf/GOVPUB-Y3_N88-PURL-gpo47583.pdf"
)
OECD_BEMUSE_LOFT = (
    "https://www.oecd-nea.org/upload/docs/application/pdf/2021-03/"
    "csni-r2007-4.pdf"
)


P2_PARAMETER_BASIS = {
    "Pnom_MW": ParameterBasis(
        3415.0, "MWth", NRC_AP1000_FSER_CH1, "NSSS power rating 3415 MWt",
        "direct adoption", "Representative AP1000-rated thermal scale",
    ),
    "Pref": ParameterBasis(
        15.5, "MPa", NRC_AP1000_FSER_CH5, "AP1000 reactor coolant operating pressure 15.5 MPa",
        "direct adoption", "Rated primary-pressure reference",
    ),
    "TrefCool": ParameterBasis(
        300.75, "degC", NRC_TRACE_AP1000, "rated average coolant temperature 573.9 K",
        "573.9 - 273.15", "Aggregate primary average-temperature reference",
    ),
    "pwr_nominal_core_delta_C": ParameterBasis(
        41.0, "degC", NRC_TRACE_AP1000,
        "rated hot/cold leg temperatures 594.4 K and 553.4 K",
        "594.4 - 553.4", "Reduced hot-to-cold-leg temperature-rise target",
    ),
    "pwr_rcp_shutoff_head_m": ParameterBasis(
        111.25, "m", NRC_AP1000_FSER_CH5,
        "RCP developed head 365 ft at design point",
        "365 ft x 0.3048 = 111.25 m",
        "Adopted as nominal developed head; full pump curve remains generic",
    ),
    "pwr_loop_loss_head_m": ParameterBasis(
        111.25, "m", NRC_AP1000_FSER_CH5,
        "RCP developed head 365 ft at design point",
        "nominal steady-state head closure",
        "Effective whole-loop loss at rated flow, not a component decomposition",
    ),
    "pwr_secondary_reference_pressure_mpa": ParameterBasis(
        5.76, "MPa", NRC_TRACE_AP1000, "rated SG steam outlet pressure 5.76 MPa",
        "direct adoption", "Aggregate two-SG secondary pressure reference",
    ),
    "pwr_secondary_inventory_kg": ParameterBasis(
        76965.77, "kg", NRC_TRACE_AP1000, "rated SG secondary water mass 76965.77 kg",
        "direct adoption", "One reported SG model inventory used as reduced aggregate scale",
    ),
    "Tsink": ParameterBasis(
        273.0, "degC", NRC_TRACE_AP1000,
        "5.76 MPa rated steam outlet pressure",
        "rounded saturation temperature at 5.76 MPa",
        "Effective SG saturation-temperature sink, not feedwater temperature",
    ),
}


UNRESOLVED_P2_PARAMETERS = {
    "pwr_rcp_curve_shape": "Only a rated AP1000 flow/head point was adopted; no public homologous curve was mapped.",
    "break_coeff": "No transferable coefficient exists for the simulator's equivalent homogeneous opening.",
    "pwr_hpsi_runout_fraction_s": "LOFT supplies event timing, not a commercial-plant normalized HPSI pump curve.",
    "pwr_lpsi_runout_fraction_s": "LOFT supplies event timing, not a commercial-plant normalized LPSI pump curve.",
    "pwr_accumulator_inventory_fraction_of_primary": "Facility and plant inventories do not map to the normalized aggregate without geometry.",
    "pressurizer_tau": "No defensible scalar response time maps detailed surge/spray/heater dynamics to this state.",
    "pwr_secondary_pressure_energy_capacity_MJ_MPa": "A single equilibrium pressure capacitance is model-specific.",
    "pwr_axial_void_reactivity_pcm_per_fraction": "Core loading, burnup, boron, rod pattern, and spatial state are required.",
}


LOFT_TIMING_EVIDENCE = {
    "reactor_scram_s": 0.24,
    "pump_trip_s": 0.94,
    "accumulator_injection_s": 16.8,
    "hpsi_injection_s": 23.90,
    "lpsi_injection_s": 37.32,
    "complete_quench_s": 65.0,
    "source": OECD_BEMUSE_LOFT,
    "applicability": "Sequence evidence only; not adopted as generic commercial-PWR setpoints or delays.",
}
