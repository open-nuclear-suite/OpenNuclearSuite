"""Acceptance tests for the public-basis generic PWR scenario envelopes."""

import unittest

from pwr_calibration import (
    CALIBRATION_CASES, DEMO_END_STATE_ENVELOPES, snapshot, violations,
)
from thermal_hydraulics_gui_backend import (
    DEMO_RECOVERY_MODES, DEMO_SCRIPTS, SCENARIOS, ThermalHydraulicsGUIBackend,
)


class PWRCalibrationTests(unittest.TestCase):
    def test_all_pwr_scenarios_are_active_calibration_gates(self):
        self.assertEqual(set(CALIBRATION_CASES), set(SCENARIOS))

    def test_declared_scenario_envelopes(self):
        for scenario, case in CALIBRATION_CASES.items():
            with self.subTest(scenario=scenario):
                backend = ThermalHydraulicsGUIBackend()
                backend.select_scenario(scenario)
                backend.start()
                previous = 0.0
                for index, point in enumerate(case.points):
                    backend.advance_elapsed(point.time_s - previous, max_steps=4000)
                    previous = point.time_s
                    self.assertEqual(
                        violations(case, index, snapshot(backend.state)), []
                    )

    def test_accident_presets_retain_an_explicit_trip_cause(self):
        for scenario in set(SCENARIOS) - {"NORMAL"}:
            with self.subTest(scenario=scenario):
                backend = ThermalHydraulicsGUIBackend()
                backend.select_scenario(scenario)
                self.assertTrue(backend.state.trip)
                self.assertIn("scenario trip", backend.state.pwr_trip_cause)

    def test_transients_close_aggregate_component_and_secondary_ledgers(self):
        for scenario in set(SCENARIOS) - {"NORMAL"}:
            with self.subTest(scenario=scenario):
                backend = ThermalHydraulicsGUIBackend()
                backend.select_scenario(scenario)
                backend.start()
                backend.advance_elapsed(30.0, max_steps=4000)
                state = backend.state
                values = snapshot(state)
                self.assertLess(abs(values["mass_residual"]), 1.0e-9)
                self.assertLess(abs(values["energy_residual"]), 1.0e-6)
                self.assertLess(abs(values["secondary_mass_residual"]), 1.0e-6)
                self.assertLess(abs(values["secondary_energy_residual"]), 1.0e-6)
                self.assertAlmostEqual(sum((
                    state.pwr_core_inventory_fraction,
                    state.pwr_hot_leg_inventory_fraction,
                    state.pwr_cold_leg_inventory_fraction,
                    state.pwr_pressurizer_liquid_inventory_fraction,
                    state.pwr_pressurizer_steam_inventory_fraction,
                )), state.M, places=10)
                self.assertAlmostEqual(sum((
                    state.pwr_core_energy_MJ, state.pwr_hot_leg_energy_MJ,
                    state.pwr_cold_leg_energy_MJ,
                    state.pwr_pressurizer_liquid_energy_MJ,
                    state.pwr_pressurizer_steam_energy_MJ,
                )), state.Ucool, places=7)

    def test_recovery_demonstrations_reach_declared_stable_shutdown(self):
        self.assertEqual(set(DEMO_END_STATE_ENVELOPES), set(DEMO_SCRIPTS))
        for name, envelope in DEMO_END_STATE_ENVELOPES.items():
            with self.subTest(demo=name):
                self.assertEqual(DEMO_RECOVERY_MODES[name], "stable_shutdown")
                self.assertEqual(envelope["mode"], "stable_shutdown")
                backend = ThermalHydraulicsGUIBackend()
                backend.start_demo(name)
                backend.advance_elapsed(envelope["time_s"], max_steps=6000)
                values = snapshot(backend.state)
                failures = [
                    f"{key}={values[key]:.6g} outside [{low:.6g}, {high:.6g}]"
                    for key, (low, high) in envelope["ranges"].items()
                    if not low <= values[key] <= high
                ]
                self.assertEqual(failures, [])
                self.assertFalse(backend.demo_mode)


if __name__ == "__main__":
    unittest.main()
