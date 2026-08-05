"""Regression tests for reactor pedagogical settings and CSV provenance."""

import csv
import math
from pathlib import Path
import tempfile
import unittest

import reactor_teaching_simulator as sim


class PedagogicalSettingsTests(unittest.TestCase):
    def test_instructor_labels_include_numerical_values(self):
        self.assertEqual(sim.kinetics_preset_label("Advanced"), "Advanced (Lambda = 0.005 s)")
        self.assertEqual(
            sim.xenon_preset_label("Extended exercise"),
            "Extended exercise (I-135 = 300 s, Xe-135 = 450 s)",
        )

    def test_defaults_preserve_existing_model(self):
        state = sim.ReactorState()
        self.assertEqual(state.Lambda, 0.080)
        self.assertAlmostEqual(state.lambdaI, math.log(2) / 60.0)
        self.assertAlmostEqual(state.lambdaXe, math.log(2) / 90.0)
        self.assertEqual(state.loadFollowPeriod, 220.0)

    def test_presets_reinitialize_equilibrium_precursors(self):
        settings = sim.PedagogicalSettings("Advanced", "Extended exercise", 600.0)
        model = sim.ReactorModel()
        model.reset(settings)
        state = model.s
        expected = (state.beta_i / (state.Lambda * state.lambda_i)) * state.P
        self.assertTrue((abs(state.C - expected) < 1e-12).all())
        self.assertAlmostEqual(state.lambdaI, math.log(2) / 300.0)
        self.assertEqual(state.loadFollowPeriod, 600.0)

    def test_settings_are_bounded(self):
        with self.assertRaises(ValueError):
            sim.PedagogicalSettings(load_follow_period_s=30.0)
        with self.assertRaises(ValueError):
            sim.PedagogicalSettings(kinetics_preset="Unrestricted")
        with self.assertRaises(ValueError):
            sim.PedagogicalSettings(initial_condition="Subcritical startup")

    def test_advanced_rod_curve_and_initial_balance(self):
        self.assertAlmostEqual(1.0e5 * sim.rod_reactivity(0.0, True), -500.0)
        self.assertAlmostEqual(1.0e5 * sim.rod_reactivity(50.0, True), 0.0)
        self.assertAlmostEqual(1.0e5 * sim.rod_reactivity(100.0, True), 500.0)
        self.assertGreater(
            sim.differential_rod_worth_pcm_per_pct(50.0, True),
            sim.differential_rod_worth_pcm_per_pct(10.0, True),
        )
        state = sim.ReactorState(sim.PedagogicalSettings(physics_profile="Advanced core physics"))
        self.assertAlmostEqual(state.reactivity_pcm, 0.0, places=8)
        self.assertLess(state.rho_sm, 0.0)

    def test_subcritical_startup_uses_source_range_and_builds_power(self):
        settings = sim.PedagogicalSettings(
            physics_profile="Advanced core physics",
            initial_condition="Subcritical startup",
        )
        model = sim.ReactorModel()
        model.reset(settings)
        initial_power = model.s.P
        self.assertEqual(model.s.instrument_range, "SOURCE RANGE")
        self.assertLess(model.s.reactivity_pcm, 0.0)
        model.advance(30.0)
        self.assertGreater(model.s.P, initial_power)
        self.assertGreater(model.s.I, 0.0)
        self.assertGreater(model.s.Pm, 0.0)

    def test_advanced_feedback_separates_density_and_void_terms(self):
        state = sim.ReactorState(sim.PedagogicalSettings(physics_profile="Advanced core physics"))
        state.coolT = 410.0
        state.update_reactivity_terms()
        self.assertLess(state.moderator_density, 1.0)
        self.assertGreater(state.void_fraction, 0.0)
        self.assertLess(state.rho_density, 0.0)
        self.assertLess(state.rho_void, 0.0)
        self.assertAlmostEqual(
            state.rho_temp,
            state.rho_fuel + state.rho_moderator_temp + state.rho_density + state.rho_void,
        )

    def test_cycle_exposure_reduces_excess_reactivity(self):
        settings = sim.PedagogicalSettings(
            physics_profile="Advanced core physics",
            cycle_preset="Beginning of cycle",
        )
        model = sim.ReactorModel()
        model.reset(settings)
        initial_exposure = model.s.exposure_efpd
        initial_depletion_rho = model.s.rho_depletion
        self.assertEqual(model.s.boron_ppm, 1000.0)
        model.advance(10.0)
        self.assertGreater(model.s.exposure_efpd, initial_exposure)
        self.assertLess(model.s.rho_depletion, initial_depletion_rho)

    def test_settings_are_exported_in_every_csv_row(self):
        settings = sim.PedagogicalSettings("Intermediate", "Reference trend", 300.0)
        model = sim.ReactorModel()
        model.reset(settings)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.csv"
            model.export_csv(path)
            with path.open(newline="", encoding="utf-8") as stream:
                row = next(csv.DictReader(stream))
        self.assertEqual(row["kinetics_preset"], "Intermediate")
        self.assertEqual(row["prompt_generation_time_s"], "0.02")
        self.assertEqual(row["xenon_preset"], "Reference trend")
        self.assertEqual(row["load_follow_period_s"], "300.0")

    def test_advanced_settings_and_physics_are_exported(self):
        settings = sim.PedagogicalSettings(
            physics_profile="Advanced core physics",
            initial_condition="Subcritical startup",
            cycle_preset="Beginning of cycle",
        )
        model = sim.ReactorModel()
        model.reset(settings)
        row = model.s.make_export_row()
        self.assertEqual(row["physics_profile"], "Advanced core physics")
        self.assertEqual(row["initial_condition"], "Subcritical startup")
        self.assertIn("rho_samarium_pcm", row)
        self.assertIn("rho_density_pcm", row)
        self.assertEqual(row["instrument_range"], "SOURCE RANGE")

    def test_all_kinetics_presets_remain_finite_for_short_transient(self):
        for preset in sim.KINETICS_PRESETS:
            with self.subTest(preset=preset):
                model = sim.ReactorModel()
                model.reset(sim.PedagogicalSettings(kinetics_preset=preset))
                model.s.rho_manual = 5e-5
                model.advance(10.0)
                self.assertTrue(math.isfinite(model.s.P))
                self.assertGreater(model.s.P, 0.0)
                self.assertLessEqual(model.s.P, 3.0)


if __name__ == "__main__":
    unittest.main()
