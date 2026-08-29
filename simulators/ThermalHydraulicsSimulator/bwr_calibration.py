"""Published-basis, normalized acceptance envelopes for generic BWR scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class CalibrationPoint:
    time_s: float
    ranges: Mapping[str, tuple[float, float]]


@dataclass(frozen=True)
class CalibrationCase:
    source: str
    basis: str
    points: tuple[CalibrationPoint, ...]


SOURCES = {
    "OECD_BWRTT": "https://www.oecd-nea.org/jcms/pl_13532/boiling-water-reactor-turbine-trip-tt-benchmark-volume-i",
    "NRC_RECIRC": "https://www.nrc.gov/sr0933/section-3-new-generic-issues/issue-151-reliability-anticipated-transient-without-scram-recirculation-pump-trip-bwrs",
    "NRC_GFE": "https://www.nrc.gov/reactors/operator-licensing/history-rulemaking-activities/generic-fundamentals-examinations/bwr/bwr-files/292all.pdf",
}

# These are normalized teaching-model acceptance envelopes, not plant data.
# They encode direction, ordering, and broad magnitude from the cited phenomena.
LEGACY_CALIBRATION_CASES = {
    "NORMAL": CalibrationCase(SOURCES["OECD_BWRTT"], "steady-state preservation", (
        CalibrationPoint(30.0, {"power": (0.97, 1.03), "pressure": (6.8, 7.2),
                                "inventory": (0.98, 1.02), "flow": (0.95, 1.05)}),
    )),
    "RECIRC_TRIP": CalibrationCase(SOURCES["NRC_RECIRC"], "flow coastdown, void increase, negative reactivity", (
        CalibrationPoint(15.0, {"power": (0.25, 0.65), "pressure": (6.5, 7.4),
                                "flow": (0.22, 0.40), "void": (0.75, 0.90)}),
    )),
    "TURBINE_TRIP": CalibrationCase(SOURCES["OECD_BWRTT"], "pressurization, void collapse, scram", (
        CalibrationPoint(5.0, {"power": (0.05, 0.30), "pressure": (7.4, 7.8),
                               "void": (0.45, 0.65)}),
    )),
    "LOFW": CalibrationCase(SOURCES["NRC_GFE"], "inventory loss followed by protection", (
        CalibrationPoint(15.0, {"inventory": (0.85, 0.95), "power": (0.70, 1.05)}),
        CalibrationPoint(30.0, {"inventory": (0.75, 0.86), "power": (0.15, 0.60)}),
    )),
    "SBO": CalibrationCase(SOURCES["NRC_GFE"], "scram, coastdown, inventory challenge", (
        CalibrationPoint(30.0, {"power": (0.0, 0.08), "inventory": (0.82, 0.93),
                                "flow": (0.22, 0.35), "pressure": (7.3, 7.8)}),
    )),
}

# R7 revalidated these deliberately broad, normalized envelopes after R1-R6.
# They are regression gates for sequence, direction, and order of magnitude;
# they are not measured plant uncertainty bands or safety-analysis limits.
CALIBRATION_CASES = {
    "NORMAL": CalibrationCase(SOURCES["OECD_BWRTT"], "steady-state preservation", (
        CalibrationPoint(30.0, {
            "power": (0.97, 1.03), "pressure": (6.8, 7.2),
            "inventory": (0.98, 1.02), "flow": (0.95, 1.05),
            "void": (0.34, 0.40), "trip": (0.0, 0.0),
        }),
    )),
    "RECIRC_TRIP": CalibrationCase(SOURCES["NRC_RECIRC"], "flow coastdown followed by protection", (
        CalibrationPoint(5.0, {
            "power": (0.90, 1.03), "pressure": (6.9, 7.4),
            "inventory": (0.98, 1.03), "flow": (0.52, 0.70),
            "trip": (0.0, 0.0),
        }),
        CalibrationPoint(15.0, {
            "power": (0.70, 0.92), "pressure": (7.35, 7.85),
            "inventory": (0.99, 1.06), "flow": (0.34, 0.48),
            "void": (0.32, 0.43), "trip": (0.0, 0.0),
            "srv_flow": (500.0, 1800.0),
        }),
        CalibrationPoint(30.0, {
            "power": (0.03, 0.12), "pressure": (8.7, 9.6),
            "inventory": (1.02, 1.12), "flow": (0.26, 0.39),
            "void": (0.18, 0.32), "trip": (1.0, 1.0),
            "srv_flow": (2500.0, 3300.0),
        }),
    )),
    "TURBINE_TRIP": CalibrationCase(SOURCES["OECD_BWRTT"], "isolation pressurization, SRV response, and scram", (
        CalibrationPoint(5.0, {
            "power": (0.12, 0.28), "pressure": (7.45, 7.85),
            "inventory": (0.96, 1.02), "flow": (0.80, 0.95),
            "void": (0.25, 0.38), "trip": (1.0, 1.0),
            "srv_flow": (1000.0, 2500.0),
        }),
        CalibrationPoint(15.0, {
            "power": (0.03, 0.10), "pressure": (7.45, 7.9),
            "inventory": (0.88, 0.97), "flow": (0.72, 0.90),
            "trip": (1.0, 1.0), "srv_flow": (1000.0, 2600.0),
        }),
    )),
    "LOFW": CalibrationCase(SOURCES["NRC_GFE"], "level decrease followed by low-level protection", (
        CalibrationPoint(15.0, {
            "power": (0.80, 1.02), "pressure": (7.1, 7.6),
            "inventory": (0.85, 0.94), "indicated_level": (0.86, 0.96),
            "trip": (0.0, 0.0),
        }),
        CalibrationPoint(35.0, {
            "power": (0.20, 0.48), "pressure": (7.0, 7.8),
            "inventory": (0.74, 0.85), "indicated_level": (0.75, 0.87),
            "trip": (1.0, 1.0),
        }),
    )),
    "SBLOCA": CalibrationCase(SOURCES["NRC_GFE"], "break discharge, scram, and steam-driven makeup", (
        CalibrationPoint(5.0, {
            "power": (0.12, 0.25), "pressure": (7.35, 7.85),
            "inventory": (0.95, 1.03), "break_flow": (45.0, 100.0),
            "rcic_flow": (10.0, 40.0), "hpci_flow": (0.0, 0.0),
            "trip": (1.0, 1.0),
        }),
        CalibrationPoint(15.0, {
            "power": (0.03, 0.10), "pressure": (7.7, 8.3),
            "inventory": (0.89, 1.0), "break_flow": (45.0, 110.0),
            "rcic_flow": (10.0, 35.0), "trip": (1.0, 1.0),
        }),
        CalibrationPoint(30.0, {
            "power": (0.015, 0.06), "pressure": (7.5, 8.8),
            "inventory": (0.80, 0.95), "break_flow": (45.0, 120.0),
            "rcic_flow": (8.0, 32.0), "pool_temperature": (45.0, 60.0),
            "trip": (1.0, 1.0),
        }),
    )),
    "SBO": CalibrationCase(SOURCES["NRC_GFE"], "scram, recirculation coastdown, RCIC, and pool heating", (
        CalibrationPoint(5.0, {
            "power": (0.12, 0.25), "pressure": (7.4, 7.9),
            "inventory": (0.95, 1.03), "flow": (0.50, 0.68),
            "rcic_flow": (15.0, 40.0), "trip": (1.0, 1.0),
        }),
        CalibrationPoint(15.0, {
            "power": (0.03, 0.10), "pressure": (7.8, 8.8),
            "inventory": (0.90, 1.02), "flow": (0.34, 0.48),
            "rcic_flow": (12.0, 35.0), "pool_temperature": (38.0, 48.0),
            "trip": (1.0, 1.0),
        }),
        CalibrationPoint(30.0, {
            "power": (0.015, 0.06), "pressure": (8.4, 10.8),
            "inventory": (0.82, 0.98), "flow": (0.30, 0.46),
            "rcic_flow": (5.0, 28.0), "pool_temperature": (48.0, 62.0),
            "hpci_flow": (0.0, 0.0), "lpci_flow": (0.0, 0.0),
            "core_spray_flow": (0.0, 0.0), "trip": (1.0, 1.0),
        }),
    )),
}
CALIBRATION_STATUS = "Post-R9 rod-step-stability generic transient envelopes active"

DEMO_END_STATE_ENVELOPES = {
    "BWR recirculation trip and recovery": {
        "mode": "return_to_power", "time_s": 50.0,
        "ranges": {"power": (0.90, 1.08), "pressure": (6.8, 7.3),
                   "inventory": (0.97, 1.04), "flow": (0.94, 1.06),
                   "trip": (0.0, 0.0)},
    },
    "BWR turbine trip and SRV response": {
        "mode": "stable_shutdown", "time_s": 145.0,
        "ranges": {"power": (0.0, 0.02), "pressure": (6.0, 6.9),
                   "inventory": (0.78, 0.95), "flow": (0.42, 0.63),
                   "trip": (1.0, 1.0)},
    },
    "BWR loss of feedwater recovery": {
        "mode": "stable_shutdown", "time_s": 145.0,
        "ranges": {"power": (0.0, 0.025), "pressure": (7.2, 7.9),
                   "inventory": (0.78, 0.93), "flow": (0.34, 0.53),
                   "trip": (1.0, 1.0)},
    },
}


def snapshot(state) -> dict[str, float]:
    return {
        "power": state.n,
        "pressure": state.P,
        "inventory": state.M,
        "flow": state.bwr_core_flow_fraction,
        "void": state.void_fraction,
        "collapsed_level": state.bwr_collapsed_level_percent/100.0,
        "indicated_level": state.bwr_indicated_level_percent/100.0,
        "fuel_temperature": state.Tf,
        "clad_temperature": state.Tcl,
        "trip": float(state.trip),
        "srv_flow": state.bwr_srv_flow_kg_s,
        "break_flow": state.bwr_break_flow_kg_s,
        "rcic_flow": state.bwr_rcic_flow_kg_s,
        "hpci_flow": state.bwr_hpci_flow_kg_s,
        "lpci_flow": state.bwr_lpci_flow_kg_s,
        "core_spray_flow": state.bwr_core_spray_flow_kg_s,
        "pool_temperature": state.bwr_suppression_pool_temperature_C,
        "mass_residual": state.bwr_mass_balance_residual_kg_s,
        "energy_residual": state.bwr_energy_balance_residual_MW,
    }


def violations(case: CalibrationCase, point_index: int, values: Mapping[str, float]) -> list[str]:
    point = case.points[point_index]
    return [
        f"{name}={values[name]:.6g} outside [{low:.6g}, {high:.6g}]"
        for name, (low, high) in point.ranges.items()
        if not low <= values[name] <= high
    ]
