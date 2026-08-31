"""P2-1 regression tests for PWR robustness and sensitivity tooling."""

import unittest

from pwr_uncertainty import (
    SensitivitySpec, local_sensitivity, run_transient, timestep_difference,
)


class PWRUncertaintyTests(unittest.TestCase):
    def test_transient_accumulates_negligible_equation_residuals(self):
        result = run_transient("SBLOCA", 5.0)
        self.assertLess(result.absolute_mass_residual_fraction, 1.0e-8)
        self.assertLess(result.absolute_energy_residual_MJ, 1.0e-5)
        self.assertLess(result.absolute_secondary_mass_residual_kg, 1.0e-5)
        self.assertLess(result.absolute_secondary_energy_residual_MJ, 1.0e-5)
        self.assertIsNotNone(result.trip_time_s)

    def test_projection_corrections_are_reported_separately(self):
        result = run_transient("LOHS", 30.0)
        self.assertGreaterEqual(result.absolute_projection_mass_fraction, 0.0)
        self.assertGreater(result.absolute_projection_energy_MJ, 0.0)
        self.assertLess(result.absolute_mass_residual_fraction, 1.0e-8)

    def test_transient_timestep_refinement_is_small(self):
        differences = timestep_difference("SBLOCA", 15.0)
        for metric, difference in differences.items():
            with self.subTest(metric=metric):
                self.assertLess(difference, 0.04)

    def test_all_calibrated_transient_families_refine(self):
        cases = {
            "SBLOCA": 30.0, "LBLOCA": 30.0, "LOFA": 15.0,
            "LOHS": 30.0, "SBO": 30.0,
        }
        for scenario, duration in cases.items():
            with self.subTest(scenario=scenario):
                differences = timestep_difference(scenario, duration)
                self.assertLess(max(differences.values()), 0.01)

    def test_local_break_sensitivity_is_finite_and_directional(self):
        result = local_sensitivity(SensitivitySpec(
            "break_coeff", "SBLOCA", 15.0,
        ))
        self.assertTrue(all(
            value == value and abs(value) < 100.0
            for value in result.metric_sensitivities.values()
        ))
        self.assertLess(result.metric_sensitivities["final_inventory"], 0.0)

    def test_unknown_and_derived_parameters_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown PWR parameter"):
            run_transient("NORMAL", 1.0, parameter_overrides={"not_a_parameter": 1.0})
        with self.assertRaisesRegex(ValueError, "derived"):
            run_transient("NORMAL", 1.0, parameter_overrides={"Ksg_nom": 1.0})


if __name__ == "__main__":
    unittest.main()
