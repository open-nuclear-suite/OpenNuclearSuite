"""Regression checks for the lumped thermal-hydraulics teaching model."""

from __future__ import annotations

import unittest
from collections import deque

from thermal_hydraulics_simulator import (
    BANNER_LOGO_FILENAME,
    SPLASH_LOGO_FILENAME,
    Constants,
    LWRTeachingSimulator,
    State,
    find_logo_path,
)


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


if __name__ == "__main__":
    unittest.main()
