"""Public-basis normalized acceptance envelopes for generic PWR scenarios."""

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
    "OECD_LOFT": "https://www.oecd-nea.org/upload/docs/application/pdf/2020-01/csni90-181.pdf",
    "OECD_SBLOCA": "https://www.oecd-nea.org/jcms/pl_16140",
    "OECD_PKL": "https://www.oecd-nea.org/jcms/pl_25236/primary-coolant-loop-test-facility-pkl-project",
    "NRC_PWR_GFE": "https://www.nrc.gov/reactors/operator-licensing/history-rulemaking-activities/generic-fundamentals-examinations/pwr",
}

# Broad, normalized teaching-model gates. They encode response direction,
# sequence, and order of magnitude; they are not plant uncertainty bands.
CALIBRATION_CASES = {
    "NORMAL": CalibrationCase(SOURCES["NRC_PWR_GFE"], "steady-state preservation", (
        CalibrationPoint(30.0, {
            "power": (0.98, 1.02), "pressure": (15.4, 15.6),
            "inventory": (0.99, 1.01), "flow": (0.98, 1.02),
            "secondary_pressure": (5.70, 5.82), "trip": (0.0, 0.0),
        }),
    )),
    "SBLOCA": CalibrationCase(SOURCES["OECD_SBLOCA"], "depressurization, inventory loss, scram, and high-pressure injection", (
        CalibrationPoint(5.0, {
            "power": (0.12, 0.20), "pressure": (9.5, 10.8),
            "inventory": (0.94, 0.99), "flow": (0.62, 0.72), "trip": (1.0, 1.0),
        }),
        CalibrationPoint(15.0, {
            "power": (0.04, 0.08), "pressure": (5.5, 7.0),
            "inventory": (0.86, 0.93), "void": (0.45, 0.60),
            "hpsi_flow": (0.0025, 0.0038), "trip": (1.0, 1.0),
        }),
        CalibrationPoint(30.0, {
            "power": (0.02, 0.05), "pressure": (3.5, 4.8),
            "inventory": (0.75, 0.84), "accumulator_flow": (0.0005, 0.0020),
            "trip": (1.0, 1.0),
        }),
    )),
    "LBLOCA": CalibrationCase(SOURCES["OECD_LOFT"], "rapid blowdown, pump coastdown, accumulator/LPSI response, and reflood", (
        CalibrationPoint(5.0, {
            "power": (0.12, 0.20), "pressure": (1.7, 2.8),
            "inventory": (0.84, 0.94), "flow": (0.38, 0.50),
            "hpsi_flow": (0.0030, 0.0042), "lpsi_flow": (0.0025, 0.0045),
            "accumulator_flow": (0.0020, 0.0042), "trip": (1.0, 1.0),
        }),
        CalibrationPoint(30.0, {
            "power": (0.02, 0.05), "pressure": (0.20, 0.60),
            "inventory": (0.82, 0.91), "flow": (0.08, 0.16),
            "lpsi_flow": (0.0055, 0.0070), "recirculation_flow": (0.0025, 0.0045),
            "trip": (1.0, 1.0),
        }),
    )),
    "LOFA": CalibrationCase(SOURCES["NRC_PWR_GFE"], "pump coastdown, scram, and decay-heat temperature response", (
        CalibrationPoint(5.0, {
            "power": (0.12, 0.20), "pressure": (15.3, 15.8),
            "flow": (0.38, 0.50), "clad_temperature": (360.0, 420.0),
            "trip": (1.0, 1.0),
        }),
        CalibrationPoint(30.0, {
            "power": (0.02, 0.05), "pressure": (15.7, 16.6),
            "flow": (0.08, 0.16), "clad_temperature": (460.0, 520.0),
            "trip": (1.0, 1.0),
        }),
    )),
    "LOHS": CalibrationCase(SOURCES["OECD_PKL"], "loss of secondary heat removal, primary heatup, and pressurization", (
        CalibrationPoint(15.0, {
            "power": (0.04, 0.08), "pressure": (17.2, 17.5),
            "inventory": (0.96, 1.01), "void": (0.05, 0.20),
            "trip": (1.0, 1.0),
        }),
        CalibrationPoint(30.0, {
            "power": (0.02, 0.05), "pressure": (17.45, 17.5),
            "inventory": (0.85, 0.94), "void": (0.75, 0.88),
            "trip": (1.0, 1.0),
        }),
    )),
    "SBO": CalibrationCase(SOURCES["NRC_PWR_GFE"], "scram, pump coastdown, loss of active primary systems, and heatup", (
        CalibrationPoint(15.0, {
            "power": (0.04, 0.08), "pressure": (16.2, 16.9),
            "inventory": (0.98, 1.02), "flow": (0.16, 0.26),
            "clad_temperature": (440.0, 500.0), "trip": (1.0, 1.0),
        }),
        CalibrationPoint(30.0, {
            "power": (0.02, 0.05), "pressure": (17.45, 17.5),
            "inventory": (0.96, 1.02), "flow": (0.08, 0.16),
            "clad_temperature": (460.0, 525.0), "trip": (1.0, 1.0),
        }),
    )),
}

CALIBRATION_STATUS = "P1-4 post-axial-remediation generic transient envelopes active"

DEMO_END_STATE_ENVELOPES = {
    "SBLOCA recovery": {"mode": "stable_shutdown", "time_s": 245.0,
        "ranges": {"power": (0.0, 0.01), "pressure": (0.8, 1.8),
                   "inventory": (0.95, 1.10), "clad_temperature": (190.0, 280.0),
                   "trip": (1.0, 1.0)}},
    "LBLOCA ECCS response": {"mode": "stable_shutdown", "time_s": 245.0,
        "ranges": {"power": (0.0, 0.01), "pressure": (1.7, 2.8),
                   "inventory": (0.98, 1.14), "clad_temperature": (270.0, 340.0),
                   "trip": (1.0, 1.0)}},
    "Loss of heat sink recovery": {"mode": "stable_shutdown", "time_s": 245.0,
        "ranges": {"power": (0.0, 0.01), "pressure": (0.5, 1.6),
                   "inventory": (0.98, 1.12), "clad_temperature": (200.0, 280.0),
                   "trip": (1.0, 1.0)}},
    "Station blackout recovery": {"mode": "stable_shutdown", "time_s": 245.0,
        "ranges": {"power": (0.0, 0.01), "pressure": (0.4, 1.4),
                   "inventory": (1.05, 1.20), "clad_temperature": (205.0, 285.0),
                   "trip": (1.0, 1.0)}},
}


def snapshot(state) -> dict[str, float]:
    return {
        "power": state.n, "pressure": state.P, "inventory": state.M,
        "flow": state.pwr_primary_flow_fraction, "void": state.void_fraction,
        "fuel_temperature": state.Tf, "clad_temperature": state.Tcl,
        "secondary_pressure": state.pwr_secondary_pressure_mpa,
        "trip": float(state.trip),
        "hpsi_flow": state.pwr_hpsi_flow_fraction_s,
        "lpsi_flow": state.pwr_lpsi_flow_fraction_s,
        "accumulator_flow": state.pwr_accumulator_flow_fraction_s,
        "recirculation_flow": state.pwr_recirculation_flow_fraction_s,
        "mass_residual": state.pwr_mass_balance_residual_fraction_s,
        "energy_residual": state.pwr_energy_balance_residual_MW,
        "secondary_mass_residual": state.pwr_secondary_mass_residual_kg_s,
        "secondary_energy_residual": state.pwr_secondary_energy_residual_MW,
    }


def violations(case: CalibrationCase, point_index: int,
               values: Mapping[str, float]) -> list[str]:
    point = case.points[point_index]
    return [
        f"{name}={values[name]:.6g} outside [{low:.6g}, {high:.6g}]"
        for name, (low, high) in point.ranges.items()
        if not low <= values[name] <= high
    ]
