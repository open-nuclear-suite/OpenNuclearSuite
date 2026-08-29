"""Public provenance for R9 BWR parameter-data replacements."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ParameterBasis:
    value: float
    unit: str
    source: str
    source_value: str
    applicability: str


OECD_PB2_VOLUME_I = (
    "https://www.oecd-nea.org/jcms/pl_13532/"
    "boiling-water-reactor-turbine-trip-tt-benchmark-volume-i"
)
NRC_LEVEL_GL_84_23 = (
    "https://www.nrc.gov/reading-rm/doc-collections/gen-comm/gen-letters/1984/gl84023"
)
NRC_LEVEL_ISSUE_101 = (
    "https://www.nrc.gov/sr0933/section-3-new-generic-issues/"
    "issue-101-bwr-water-level-redundancy"
)
NRC_RECIRC_ISSUE_151 = (
    "https://www.nrc.gov/sr0933/section-3-new-generic-issues/"
    "issue-151-reliability-anticipated-transient-without-scram-recirculation-pump-trip-bwrs"
)
NRC_NUREG_1953 = "https://downloads.regulations.gov/NRC-2010-0344-0002/content.pdf"
PEACH_BOTTOM_FLEX = "https://adamswebsearch2.nrc.gov/webSearch2/main.jsp?AccessionNumber=ML14140A367"
NRC_HPCI_INSPECTION = "https://adamswebsearch2.nrc.gov/webSearch2/main.jsp?AccessionNumber=ML24180A058"


R9_PARAMETER_BASIS = {
    "Pnom_MW": ParameterBasis(
        3293.0, "MWth", OECD_PB2_VOLUME_I, "rated core thermal power 3293 MWth",
        "Representative BWR/4 rated reference only",
    ),
    "bwr_reference_core_flow_kg_s": ParameterBasis(
        12915.0, "kg/s", OECD_PB2_VOLUME_I, "rated total core flow 12915 kg/s",
        "Total core flow including the benchmark's declared bypass treatment",
    ),
    "reference_steam_flow_kg_s": ParameterBasis(
        1685.0, "kg/s", OECD_PB2_VOLUME_I, "rated steam flow 1685 kg/s",
        "Acceptance reference; model derives 1682 kg/s from energy balance",
    ),
    "bwr_feedwater_subcooling_kJ_kg": ParameterBasis(
        452.09, "kJ/kg", OECD_PB2_VOLUME_I,
        "191.17 C rated feedwater mapped at 7 MPa with bundled IF97 properties",
        "Property conversion, not a directly tabulated benchmark delta-h",
    ),
    "bwr_loop_loss_head_m": ParameterBasis(
        20.90, "m liquid head", OECD_PB2_VOLUME_I,
        "151.685 kPa rated core drop divided by rho_f(7 MPa) g",
        "Effective reduced core loop; excludes direct use of external pump head",
    ),
    "bwr_single_phase_loss_head_ref_m": ParameterBasis(
        17.10, "m liquid head", OECD_PB2_VOLUME_I,
        "124.105 kPa core support-plate drop divided by rho_f(7 MPa) g",
        "Support-plate contribution represented as single-phase/local loss",
    ),
    "bwr_core_friction_head_ref_m": ParameterBasis(
        3.80, "m liquid head", OECD_PB2_VOLUME_I,
        "difference between measured total core and support-plate drops",
        "Aggregate bundle/two-phase remainder; not a separated measurement",
    ),
    "bwr_rcic_capacity_kg_s": ParameterBasis(
        68.0, "kg/s zero-head curve equivalent", PEACH_BOTTOM_FLEX,
        "600 gpm rated RCIC injection; mapped through retained 10 MPa quadratic curve",
        "Rated point is sourced; shutoff head and curve shape remain generic",
    ),
    "bwr_hpci_capacity_kg_s": ParameterBasis(
        566.0, "kg/s zero-head curve equivalent", NRC_HPCI_INSPECTION,
        "at least 5000 gpm at the required reactor-pressure system head",
        "Representative BWR value mapped through retained generic curve",
    ),
    "bwr_rcic_driver_min_mpa": ParameterBasis(
        0.52, "MPa", NRC_NUREG_1953, "RCIC/HPCI isolate below 75 psig steam pressure",
        "Used as the minimum steam-driver pressure for the teaching curve",
    ),
    "bwr_hpci_driver_min_mpa": ParameterBasis(
        0.52, "MPa", NRC_NUREG_1953, "RCIC/HPCI isolate below 75 psig steam pressure",
        "Used as the minimum steam-driver pressure for the teaching curve",
    ),
}


UNRESOLVED_R9_PARAMETERS = {
    "bwr_pump_shutoff_head_m": "Actual pump head drives jet pumps; no public reduced-loop curve located.",
    "bwr_reference_leg_sensitivity": "NRC sources establish density/temperature errors but not a generic scalar response.",
    "alpha_void": "Coefficient is core-state, exposure, and spatial-distribution dependent; no transferable scalar located.",
    "bwr_srv_capacity_kg_s": "Public values are valve-count and plant/configuration dependent; no matched aggregate PB2 curve adopted.",
    "bwr_break_discharge_coefficient": "No transferable plant-independent coefficient located for the modeled equivalent opening.",
}
