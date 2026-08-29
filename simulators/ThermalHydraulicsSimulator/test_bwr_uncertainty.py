"""R8 regression tests for BWR robustness and sensitivity tooling."""

import unittest

from bwr_uncertainty import (
    SensitivitySpec, local_sensitivity, run_transient, timestep_difference,
)


class BWRUncertaintyTests(unittest.TestCase):
    def test_transient_accumulates_negligible_balance_residuals(self):
        result = run_transient("SBLOCA", 5.0)
        self.assertLess(result.absolute_mass_residual_kg, 1e-5)
        self.assertLess(result.absolute_energy_residual_MJ, 1e-5)
        self.assertIsNotNone(result.trip_time_s)
        self.assertGreater(result.peak_pressure_mpa, 7.0)

    def test_transient_timestep_refinement_is_small(self):
        differences = timestep_difference("TURBINE_TRIP", 5.0)
        for metric, difference in differences.items():
            with self.subTest(metric=metric):
                self.assertLess(difference, 0.03)

    def test_local_sensitivity_is_finite_and_directional(self):
        result = local_sensitivity(SensitivitySpec(
            "bwr_break_discharge_coefficient", "SBLOCA", 5.0,
        ))
        self.assertTrue(all(
            value == value and abs(value) < 100.0
            for value in result.metric_sensitivities.values()
        ))
        self.assertLess(result.metric_sensitivities["final_inventory"], 0.0)

    def test_unknown_parameter_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown BWR parameter"):
            run_transient("NORMAL", 1.0, parameter_overrides={"not_a_parameter": 1.0})


if __name__ == "__main__":
    unittest.main()
