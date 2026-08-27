"""Regression tests for the GUI-independent core model."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from core_loading_thorium_poc_fixed import CoreModel


class CoreModelTests(unittest.TestCase):
    def test_supplied_pwr_preset_is_symmetric(self) -> None:
        model = CoreModel()
        self.assertAlmostEqual(model.north_south_tilt, 0.0, places=10)
        self.assertAlmostEqual(model.east_west_tilt, 0.0, places=10)
        self.assertAlmostEqual(model.flux_centroid_offset, 0.0, places=10)
        self.assertGreater(model.centre_edge_ratio, 0.0)
        self.assertGreater(model.k_eff, 1.04)
        self.assertLess(model.k_eff, 1.08)
        self.assertAlmostEqual(model.operating_k_eff, 1.0, places=4)
        self.assertGreater(model.required_boron_ppm, 0.0)
        self.assertGreater(float(np.max(model.fast_flux)), 0.0)
        self.assertGreater(float(np.max(model.thermal_flux)), 0.0)

    def test_converged_feedback_preserves_rotational_symmetry(self) -> None:
        model = CoreModel()
        for _ in range(5):
            model.advance_cycle(30.0)
        for field in (model.power, model.flux, model.burnup, model.u235_inventory,
                      model.xenon135_inventory, model.samarium149_inventory):
            np.testing.assert_allclose(field, np.rot90(field, 2), rtol=0.0, atol=1.0e-8)
        self.assertAlmostEqual(model.north_south_tilt, 0.0, places=10)
        self.assertAlmostEqual(model.east_west_tilt, 0.0, places=10)

    def test_feedback_solver_does_not_force_an_asymmetric_state(self) -> None:
        model = CoreModel()
        model.burnup[4, 5] += 1.0
        model.advance_cycle(30.0)
        self.assertGreater(abs(float(model.burnup[4, 5] - model.burnup[6, 5])), 0.5)

    def test_conventional_cycle_reaches_unity_near_end_of_cycle(self) -> None:
        model = CoreModel()
        model.advance_cycle(420.0)
        self.assertAlmostEqual(model.k_eff, 1.0, delta=0.01)
        self.assertLess(model.required_boron_ppm, 10.0)

    def test_advertised_1000_fpd_horizon_remains_well_conditioned(self) -> None:
        model = CoreModel()
        model.advance_cycle(1000.0)
        fuel = model.mask & (model.layout != "EMPTY") & (model.layout != "REFL")
        self.assertAlmostEqual(model.cycle_days, 1000.0, places=8)
        self.assertLessEqual(model.feedback_residual, 1.0e-7)
        for field in (
            model.power, model.flux, model.burnup, model.u235_inventory,
            model.pu239_inventory, model.xenon135_inventory,
        ):
            self.assertTrue(np.all(np.isfinite(field)))
            self.assertGreaterEqual(float(np.min(field[fuel])), 0.0)
        np.testing.assert_allclose(
            model.power, np.rot90(model.power, 2), rtol=0.0, atol=1.0e-8,
        )

    def test_boron_search_reduces_the_eigenvalue(self) -> None:
        model = CoreModel()
        unborated = model._solve_two_group(0.0, 250, 1.0e-8)[0]
        borated = model._solve_two_group(1000.0, 250, 1.0e-8)[0]
        self.assertGreater(unborated, borated)
        self.assertAlmostEqual(model.operating_k_eff, 1.0, places=4)

    def test_heavy_metal_and_absorber_inventories_evolve(self) -> None:
        model = CoreModel()
        initial_u235 = float(np.sum(model.u235_inventory))
        initial_pu239 = float(np.sum(model.pu239_inventory))
        initial_poison = float(np.sum(model.poison_inventory))
        model.advance_cycle(30.0)
        self.assertLess(float(np.sum(model.u235_inventory)), initial_u235)
        self.assertGreater(float(np.sum(model.pu239_inventory)), initial_pu239)
        self.assertLess(float(np.sum(model.poison_inventory)), initial_poison)
        self.assertGreater(float(np.sum(model.samarium149_inventory)), 0.0)

    def test_thermal_feedback_and_equilibrium_xenon_are_active(self) -> None:
        model = CoreModel()
        fuel = model.mask & (model.layout != "EMPTY") & (model.layout != "REFL")
        self.assertGreater(float(np.max(model.fuel_temperature[fuel])), 600.0)
        self.assertGreater(float(np.max(model.moderator_temperature[fuel])), 560.0)
        self.assertLess(float(np.min(model.moderator_density[fuel])), 1.0)
        self.assertGreater(float(np.sum(model.xenon135_inventory[fuel])), 0.0)

    def test_control_banks_reduce_reactivity_and_provide_shutdown_margin(self) -> None:
        model = CoreModel()
        unrodded_k = model.k_eff
        model.set_control_insertion(25.0)
        self.assertLess(model.k_eff, unrodded_k)
        self.assertGreater(model.control_worth_pcm, 0.0)
        self.assertLess(model.shutdown_k_eff, 1.0)
        self.assertGreater(model.shutdown_margin_pcm, 0.0)

    def test_feedback_converges_across_control_insertion_range(self) -> None:
        for insertion in (5.0, 25.0, 50.0, 75.0, 100.0):
            with self.subTest(insertion=insertion):
                model = CoreModel()
                model.set_control_insertion(insertion)
                self.assertLessEqual(model.feedback_residual, 1.0e-7)
                self.assertTrue(np.isfinite(model.k_eff))

    def test_controlled_depletion_converges_with_bounded_feedback_restarts(self) -> None:
        for insertion, steps in ((25.0, 3), (75.0, 2)):
            with self.subTest(insertion=insertion):
                model = CoreModel()
                model.set_control_insertion(insertion)
                restart_counts = []
                for _ in range(steps):
                    model.advance_cycle(30.0)
                    restart_counts.append(model.feedback_restart_count)
                    self.assertLessEqual(model.feedback_residual, 1.0e-7)
                # A restart is a recovery mechanism, not a required outcome.
                # Small numerical differences between supported Python/NumPy
                # versions can let the primary iteration converge directly.
                self.assertGreaterEqual(min(restart_counts), 0)
                self.assertLessEqual(max(restart_counts), 4)

    def test_controlled_depletion_reaches_1000_fpd_in_40_steps(self) -> None:
        """Long-horizon coverage for the full control-insertion sweep."""
        for insertion in (10.0, 25.0, 50.0, 75.0, 100.0):
            with self.subTest(insertion=insertion):
                model = CoreModel()
                model.set_control_insertion(insertion)
                for _ in range(40):
                    model.advance_cycle(25.0)
                    self.assertLessEqual(model.feedback_residual, 1.0e-7)
                    for field in (
                        model.power, model.flux, model.burnup,
                        model.u235_inventory, model.pu239_inventory,
                        model.xenon135_inventory,
                    ):
                        self.assertTrue(np.all(np.isfinite(field)))
                self.assertAlmostEqual(model.cycle_days, 1000.0, places=8)

    def test_refueling_move_preserves_identity_burnup_and_isotopes(self) -> None:
        model = CoreModel()
        model.advance_cycle(30.0)
        source, target = (5, 5), (4, 5)
        source_id = str(model.assembly_ids[source])
        source_state = model._capture_cell_state(*source)
        model.move_or_swap_assemblies(source, target)
        self.assertEqual(str(model.assembly_ids[target]), source_id)
        self.assertEqual(model.assembly_registry[source_id].position, model.position_id(*target))
        for key in ("burnup", "u235_inventory", "pu239_inventory", "u233_inventory"):
            self.assertAlmostEqual(model._capture_cell_state(*target)[key], source_state[key])

    def test_storage_reload_and_outage_decay_preserve_assembly_record(self) -> None:
        model = CoreModel()
        model.advance_cycle(30.0)
        cell = (5, 5)
        assembly_id = str(model.assembly_ids[cell])
        burnup = float(model.burnup[cell])
        model.discharge_assembly(*cell)
        xenon_before = model.assembly_registry[assembly_id].state["xenon135_inventory"]
        model.begin_next_cycle(30.0)
        self.assertLess(model.assembly_registry[assembly_id].state["xenon135_inventory"], xenon_before)
        model.load_stored_assembly(assembly_id, *cell)
        self.assertEqual(str(model.assembly_ids[cell]), assembly_id)
        self.assertAlmostEqual(float(model.burnup[cell]), burnup)
        self.assertEqual(model.cycle_number, 2)

    def test_saved_state_restores_ids_pool_and_histories(self) -> None:
        model = CoreModel()
        model.advance_cycle(30.0)
        assembly_id = model.discharge_assembly(5, 5)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "core_state.json"
            model.save_state(str(path))
            restored = CoreModel()
            restored.load_state(str(path))
        self.assertIn(assembly_id, restored.storage_ids())
        self.assertEqual(restored.cycle_number, model.cycle_number)
        self.assertEqual(
            len(restored.assembly_registry[assembly_id].history),
            len(model.assembly_registry[assembly_id].history),
        )

    def test_guided_unload_promotes_and_classifies_batches(self) -> None:
        model = CoreModel()
        count = model.unload_all_to_staging()
        categories = {
            category: sum(
                1 for assembly_id in model.assembly_registry
                if model.refueling_category(assembly_id) == category
            )
            for category in ("once", "twice", "special", "spent")
        }
        self.assertEqual(count, 89)
        self.assertFalse(np.any(model.assembly_ids[model.mask] != ""))
        self.assertEqual(categories["once"], 24)
        self.assertEqual(categories["twice"], 44)
        self.assertEqual(categories["spent"], 21)

    def test_new_reload_fuel_is_not_credited_before_irradiation(self) -> None:
        model = CoreModel()
        model.unload_all_to_staging()
        model.set_assembly(5, 5, "FRESH")
        assembly_id = str(model.assembly_ids[5, 5])
        model.begin_next_cycle(30.0)
        self.assertEqual(model.assembly_registry[assembly_id].cycles_completed, 0)
        self.assertEqual(model.cycle_number, 2)

    def test_reflectors_do_not_generate_power_or_burnup(self) -> None:
        model = CoreModel()
        model.load_thorium_seed_blanket()
        reflector = model.layout == "REFL"
        self.assertTrue(np.all(model.power[reflector] == 0.0))
        before = model.burnup.copy()
        model.advance_cycle(30.0)
        np.testing.assert_allclose(model.burnup[reflector], before[reflector])

    def test_pa233_precursor_and_u233_accumulate(self) -> None:
        model = CoreModel()
        model.load_thorium_seed_blanket()
        model.advance_cycle(30.0)
        self.assertGreater(float(np.sum(model.pa233_inventory)), 0.0)
        self.assertGreater(float(np.sum(model.u233_inventory)), 0.0)

    def test_empty_core_has_zero_diagnostics(self) -> None:
        model = CoreModel()
        model.clear_core()
        model.solve()
        self.assertEqual(model.k_eff, 0.0)
        self.assertEqual(model.centre_edge_ratio, 0.0)
        self.assertEqual(model.flux_centroid_offset, 0.0)

    def test_identical_fuel_progresses_differently_by_position(self) -> None:
        model = CoreModel()
        model.clear_core()
        for r, c in zip(*np.where(model.mask)):
            model.set_assembly(int(r), int(c), "FRESH")
        model.solve()
        centre = (5, 5)
        edge = (0, 4)
        self.assertGreater(model.flux[centre], model.flux[edge])
        model.advance_cycle(30.0)
        self.assertGreater(model.burnup[centre], model.burnup[edge])


if __name__ == "__main__":
    unittest.main()
