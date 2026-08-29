"""Acceptance tests for the published-basis generic BWR scenario envelopes."""

import unittest

from bwr_calibration import CALIBRATION_CASES, DEMO_END_STATE_ENVELOPES, snapshot, violations
from thermal_hydraulics_gui_backend import BWR_DEMO_SCRIPTS, DEMO_RECOVERY_MODES, ThermalHydraulicsGUIBackend


class BWRCalibrationTests(unittest.TestCase):
    def test_declared_scenario_envelopes(self):
        for scenario, case in CALIBRATION_CASES.items():
            with self.subTest(scenario=scenario):
                backend = ThermalHydraulicsGUIBackend(); backend.select_plant("BWR")
                backend.select_scenario(scenario); backend.start()
                previous = 0.0
                for index, point in enumerate(case.points):
                    backend.advance_elapsed(point.time_s-previous, max_steps=2000)
                    previous = point.time_s
                    self.assertEqual(violations(case, index, snapshot(backend.state)), [])

    def test_recovery_classes_distinguish_power_return_from_stable_shutdown(self):
        self.assertEqual(DEMO_RECOVERY_MODES[BWR_DEMO_SCRIPTS[0]], "return_to_power")
        self.assertEqual(DEMO_RECOVERY_MODES[BWR_DEMO_SCRIPTS[1]], "stable_shutdown")
        self.assertEqual(DEMO_RECOVERY_MODES[BWR_DEMO_SCRIPTS[2]], "stable_shutdown")
        for name in BWR_DEMO_SCRIPTS:
            self.assertEqual(DEMO_END_STATE_ENVELOPES[name]["mode"], DEMO_RECOVERY_MODES[name])

    def test_all_declared_transients_are_active(self):
        self.assertEqual(
            set(CALIBRATION_CASES),
            {"NORMAL", "RECIRC_TRIP", "TURBINE_TRIP", "LOFW", "SBLOCA", "SBO"},
        )

    def test_recovery_demonstrations_reach_their_declared_end_states(self):
        for name, envelope in DEMO_END_STATE_ENVELOPES.items():
            with self.subTest(demo=name):
                backend = ThermalHydraulicsGUIBackend(); backend.select_plant("BWR")
                backend.start_demo(name)
                backend.advance_elapsed(envelope["time_s"], max_steps=4000)
                values = snapshot(backend.state)
                failures = [
                    f"{key}={values[key]:.6g} outside [{low:.6g}, {high:.6g}]"
                    for key, (low, high) in envelope["ranges"].items()
                    if not low <= values[key] <= high
                ]
                self.assertEqual(failures, [])

    def test_transient_sequences_preserve_declared_conservation_ledgers(self):
        for scenario in ("RECIRC_TRIP", "TURBINE_TRIP", "LOFW", "SBLOCA", "SBO"):
            with self.subTest(scenario=scenario):
                backend = ThermalHydraulicsGUIBackend(); backend.select_plant("BWR")
                backend.select_scenario(scenario); backend.start()
                backend.advance_elapsed(30.0, max_steps=2000)
                values = snapshot(backend.state)
                self.assertLess(abs(values["mass_residual"]), 1e-6)
                self.assertLess(abs(values["energy_residual"]), 1e-6)


if __name__ == "__main__":
    unittest.main()
