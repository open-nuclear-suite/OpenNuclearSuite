"""Regression checks for the lumped thermal-hydraulics teaching model."""

from __future__ import annotations

import unittest
from collections import deque
import csv
import io
import math

from thermal_hydraulics_simulator import (
    BANNER_LOGO_FILENAME,
    SPLASH_LOGO_FILENAME,
    Constants,
    LWRTeachingSimulator,
    State,
    find_logo_path,
)
from steam_properties import SteamTables
from thermal_hydraulics_engine import ControlInputs, ThermalHydraulicsEngine
from hot_channel import HotChannelModel


class FakeVar:
    def __init__(self, value: float | bool) -> None:
        self.value = value

    def get(self) -> float | bool:
        return self.value

    def set(self, value: float | bool) -> None:
        self.value = value


def make_model(**overrides: float) -> LWRTeachingSimulator:
    """Construct the physics portion without creating a Tk window."""
    model = LWRTeachingSimulator.__new__(LWRTeachingSimulator)
    model.c = Constants()
    model.state = State(model.c)
    model.steam_tables = SteamTables()
    model.physics = ThermalHydraulicsEngine(model.c, model.steam_tables)
    model.hot_channel = HotChannelModel(model.steam_tables)
    model.hot_channel_result = None
    model.hot_channel_result_time = float("nan")
    controls = {
        "rod": 0.0, "trim": 0.0, "boron": 1000.0, "pump": 100.0,
        "sg": 100.0, "break": 0.0, "eccs": 0.0, "afw": 0.0,
        "porv": 0.0, "spray": 0.0, "heater": 0.0, "rhr": 0.0,
        "noise": 0.0,
    }
    controls.update(overrides)
    model.control_vars = {key: FakeVar(value) for key, value in controls.items()}
    model.auto_trip_var = FakeVar(True)
    model.auto_eccs_var = FakeVar(True)
    model.hot_channel_coupling_var = FakeVar(True)
    model.set_slider = lambda key, value: model.control_vars[key].set(value)
    model.append_history = lambda *_args: None
    model.events = deque(maxlen=250)
    model.event_snapshot = {}
    model.last_event_time = {}
    model.reset_event_timeline()
    return model


def advance(model: LWRTeachingSimulator, seconds: float, dt: float = 0.05) -> None:
    for _ in range(round(seconds / dt)):
        model.step_model(dt)


class ThermalHydraulicsPhysicsTests(unittest.TestCase):
    def test_nested_app_directory_resolves_both_branding_images(self) -> None:
        splash = find_logo_path(SPLASH_LOGO_FILENAME)
        banner = find_logo_path(BANNER_LOGO_FILENAME)
        self.assertIsNotNone(splash)
        self.assertIsNotNone(banner)
        self.assertTrue(splash.is_file())
        self.assertTrue(banner.is_file())

    def test_nominal_state_remains_at_equilibrium(self) -> None:
        model = make_model()
        advance(model, 100.0)
        state = model.state
        self.assertAlmostEqual(state.M, 1.0, places=8)
        self.assertAlmostEqual(state.Tc, model.c.TrefCool, places=6)
        self.assertAlmostEqual(state.P, model.c.Pref, places=6)
        self.assertEqual(state.boiling_regime, "single-phase")

    def test_saturation_curve_is_monotonic_and_invertible(self) -> None:
        model = make_model()
        pressures = (0.1, 0.5, 2.0, 8.0, 15.5, 17.5)
        temperatures = [model.saturation_temperature(p) for p in pressures]
        self.assertEqual(temperatures, sorted(temperatures))
        for pressure, temperature in zip(pressures, temperatures):
            self.assertAlmostEqual(model.saturation_pressure(temperature), pressure, places=6)

    def test_stored_energy_and_temperature_stay_synchronized(self) -> None:
        model = make_model(**{"break": 12.0, "pump": 60.0})
        advance(model, 80.0)
        state, constants = model.state, model.c
        reconstructed = constants.Ccool * state.M * (
            state.Tc - constants.coolant_energy_reference_C
        )
        self.assertAlmostEqual(state.Ucool, reconstructed, places=6)

    def test_cold_eccs_injection_cools_by_enthalpy_transport(self) -> None:
        without_injection = make_model(sg=0.0)
        with_injection = make_model(sg=0.0, eccs=100.0)
        without_injection.auto_eccs_var.set(False)
        with_injection.auto_eccs_var.set(False)
        advance(without_injection, 20.0)
        advance(with_injection, 20.0)
        self.assertLess(with_injection.state.Tc, without_injection.state.Tc)
        self.assertGreater(with_injection.state.M, without_injection.state.M)

    def test_loss_of_flow_can_cross_chf_and_degrade_heat_transfer(self) -> None:
        model = make_model(pump=0.0)
        advance(model, 120.0)
        self.assertGreater(model.state.chf_ratio, 1.0)
        self.assertIn(model.state.boiling_regime, {"transition boiling", "film boiling"})

    def test_timeline_records_transitions_without_stepwise_duplicates(self) -> None:
        model = make_model(pump=0.0)
        advance(model, 120.0)
        messages = [event.message for event in model.events]
        self.assertIn("Reactor trip actuated", messages)
        self.assertIn("Critical heat flux exceeded", messages)
        self.assertEqual(messages.count("Reactor trip actuated"), 1)
        self.assertEqual(messages.count("Critical heat flux exceeded"), 1)

    def test_timeline_records_scenario_selection_immediately(self) -> None:
        model = make_model()
        model.set_scenario("Small-break LOCA")
        self.assertEqual(model.events[-1].category, "SCENARIO")
        self.assertEqual(model.events[-1].message, "Selected Small-break LOCA")

    def test_rk4_solution_converges_under_timestep_refinement(self) -> None:
        results = []
        for dt in (0.20, 0.10, 0.025):
            model = make_model(trim=50.0)
            model.auto_trip_var.set(False)
            model.auto_eccs_var.set(False)
            advance(model, 10.0, dt)
            results.append(model.state.n)
        coarse_error = abs(results[0] - results[2])
        fine_error = abs(results[1] - results[2])
        self.assertLess(fine_error, coarse_error / 8.0)

    def test_existing_accident_scenarios_remain_bounded_and_trip(self) -> None:
        scenarios = {
            "SBLOCA": {"pump": 60.0, "break": 12.0},
            "LBLOCA": {"pump": 0.0, "sg": 60.0, "break": 70.0},
            "LOFA": {"pump": 0.0},
            "LOHS": {"pump": 80.0, "sg": 0.0},
            "SBO": {"pump": 0.0, "sg": 8.0},
        }
        for name, controls in scenarios.items():
            with self.subTest(scenario=name):
                model = make_model(**controls)
                advance(model, 60.0)
                state = model.state
                self.assertTrue(state.trip)
                self.assertTrue(all(math.isfinite(value) for value in (
                    state.n, state.Tf, state.Tcl, state.Tc, state.P, state.M,
                    state.void_fraction, state.chf_ratio,
                )))
                self.assertGreaterEqual(state.M, 0.05)
                self.assertLessEqual(state.M, 1.20)
                self.assertGreaterEqual(state.P, 0.10)
                self.assertLessEqual(state.P, 17.50 + 1.0e-9)

    def test_axial_feedback_can_raise_lumped_chf_demand(self) -> None:
        model = make_model()
        vector = model.physics.pack(model.state)
        _, uncoupled = model.physics.rhs(0.0, vector, ControlInputs())
        _, coupled = model.physics.rhs(
            0.0, vector,
            ControlInputs(
                hot_channel_coupling=True,
                hot_channel_peak_clad_C=500.0,
                hot_channel_min_dnbr=0.80,
            ),
        )
        self.assertLess(uncoupled.chf_ratio, 1.0)
        self.assertGreaterEqual(coupled.chf_ratio, 1.25)
        self.assertGreaterEqual(coupled.eccs_fraction, 0.85)

    def test_eccs_and_break_conditions_reach_axial_channel(self) -> None:
        nominal = make_model()
        eccs = make_model(eccs=100.0)
        eccs.auto_eccs_var.set(False)
        loca = make_model(**{"break": 70.0})
        nominal_result = nominal.calculate_hot_channel()
        eccs_result = eccs.calculate_hot_channel()
        loca_result = loca.calculate_hot_channel()
        self.assertLess(
            eccs_result.bulk_temperature_C[0], nominal_result.bulk_temperature_C[0]
        )
        self.assertGreater(loca_result.outlet_temperature_C, nominal_result.outlet_temperature_C)

    def test_step_publishes_axial_metrics_for_summaries_and_logging(self) -> None:
        model = make_model()
        model.step_model(0.05)
        self.assertTrue(math.isfinite(model.state.hot_peak_fuel_C))
        self.assertTrue(math.isfinite(model.state.hot_peak_clad_C))
        self.assertGreater(model.state.hot_dnbr_valid_nodes, 0)

        output = io.StringIO()
        model.csv_logging = True
        model.csv_file = output
        model.csv_writer = csv.writer(output)
        model.csv_last_logged_t = -1.0e9
        model.csv_log_interval = 0.0
        model.demo_stage = ""
        model.csv_writer.writerow(model.csv_header())
        model.write_csv_row(100.0, 0.065, 0.0, 1.0)
        rows = list(csv.reader(io.StringIO(output.getvalue())))
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]), len(rows[1]))
        self.assertIn("hot_min_dnbr", rows[0])
        self.assertIn("effective_eccs_percent", rows[0])
        summary = model.scenario_summary_text()
        self.assertIn("Axial-to-lumped coupling: enabled", summary)
        self.assertIn("Minimum in-range W-3 DNBR", summary)

    def test_failed_hot_channel_solves_are_rate_limited(self) -> None:
        model = make_model()
        calls = 0

        def unavailable():
            nonlocal calls
            calls += 1
            raise ValueError("deliberate out-of-domain state")

        model.calculate_hot_channel = unavailable
        model.hot_channel_result = None
        model.hot_channel_result_time = float("nan")
        for _ in range(20):
            model.step_model(0.05)
        self.assertLessEqual(calls, 4)
        self.assertEqual(model.hot_channel_error, "deliberate out-of-domain state")

    def test_auto_eccs_demand_latches_during_active_loca(self) -> None:
        model = make_model(**{"break": 12.0})
        model.state.P = 4.0
        model.state.M = 1.00
        self.assertEqual(model.update_auto_eccs_demand(), 0.85)
        model.state.P = 5.0
        model.state.M = 1.06
        self.assertEqual(model.update_auto_eccs_demand(), 0.85)
        model.control_vars["break"].set(0.0)
        model.state.P = 15.5
        model.state.M = 1.00
        model.state.Tcl = 335.0
        model.state.hot_peak_clad_C = 360.0
        model.state.hot_min_dnbr = 4.0
        self.assertEqual(model.update_auto_eccs_demand(), 0.0)


if __name__ == "__main__":
    unittest.main()
