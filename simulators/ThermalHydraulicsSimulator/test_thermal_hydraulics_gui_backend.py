import unittest

from thermal_hydraulics_gui_backend import (
    BWR_DEMO_SCRIPTS, DEMO_SCRIPTS, ThermalHydraulicsGUIBackend,
    hot_channel_interval_for_speed,
)


class ThermalHydraulicsGUIBackendTests(unittest.TestCase):
    def setUp(self): self.backend = ThermalHydraulicsGUIBackend()

    def test_hot_channel_work_is_wall_clock_limited_above_real_time(self):
        self.assertEqual(hot_channel_interval_for_speed(0.5), 0.25)
        self.assertEqual(hot_channel_interval_for_speed(1.0), 0.25)
        self.assertEqual(hot_channel_interval_for_speed(5.0), 1.25)
        self.assertEqual(hot_channel_interval_for_speed(10.0), 2.5)

    def test_elapsed_time_uses_fixed_steps_only_while_running(self):
        self.assertEqual(self.backend.advance_elapsed(0.11), 0)
        self.backend.start()
        self.assertEqual(self.backend.advance_elapsed(0.11), 2)
        self.assertAlmostEqual(self.backend.state.t, 0.1)

    def test_controls_are_clamped_and_validated(self):
        self.assertEqual(self.backend.set_control("break", 150), 100)
        with self.assertRaises(ValueError): self.backend.set_control("unknown", 1)

    def test_bwr_safety_system_availability_is_operator_controllable(self):
        self.backend.select_plant("BWR")
        self.assertFalse(self.backend.set_bwr_system_available("hpci", False))
        self.backend.set_control("hpci", 100)
        self.backend.start(); self.backend.advance_elapsed(0.1)
        self.assertEqual(self.backend.state.bwr_hpci_flow_kg_s, 0.0)
        with self.assertRaises(ValueError):
            self.backend.set_bwr_system_available("unknown", False)

    def test_scram_and_scenario_controls(self):
        self.backend.scram()
        self.assertTrue(self.backend.state.trip)
        self.assertEqual(self.backend.sim.control_vars["rod"].get(), 100)
        self.backend.select_scenario("SBO")
        self.assertEqual(self.backend.state.scenario_name, "Station blackout")
        self.assertFalse(self.backend.sim.auto_eccs_var.get())

    def test_reset_restores_nominal_state(self):
        self.backend.select_scenario("LBLOCA")
        self.backend.reset()
        self.assertFalse(self.backend.running)
        self.assertAlmostEqual(self.backend.state.P, 15.5)
        self.assertAlmostEqual(self.backend.state.M, 1.0)

    def test_plant_selection_preserves_pwr_and_builds_bwr_equilibrium(self):
        self.assertEqual(self.backend.plant_type, "PWR")
        self.assertTrue(self.backend.plant_metadata.scenario_capable)
        metadata = self.backend.select_plant("BWR")
        self.assertEqual(metadata.key, "BWR")
        self.assertTrue(metadata.scenario_capable)
        self.assertTrue(metadata.hot_channel_capable)
        self.assertAlmostEqual(self.backend.state.P, 7.0, places=6)
        initial_pressure = self.backend.state.P
        self.assertAlmostEqual(self.backend.state.Tc, 285.830022805751, places=6)
        self.backend.start()
        self.backend.advance_elapsed(100.0, max_steps=2500)
        self.assertLess(abs(self.backend.state.P-initial_pressure), 0.10)
        self.assertLess(abs(self.backend.state.bwr_steam_volume_residual_m3), 1.0e-6)
        self.assertLess(abs(self.backend.state.M-1.0), 2.0e-4)
        self.assertLess(abs(self.backend.state.n-1.0), 2.0e-2)
        self.assertEqual(
            self.backend.state.boiling_regime, "bulk boiling"
        )

    def test_bwr_has_own_scenarios_and_reset_keeps_plant(self):
        self.backend.select_plant("BWR")
        self.backend.select_scenario("RECIRC_TRIP")
        self.assertEqual(self.backend.sim.control_vars["recirc"].get(), 0)
        self.backend.select_scenario("SBLOCA")
        self.assertEqual(self.backend.sim.control_vars["bwr_break"].get(), 15)
        self.assertGreater(self.backend.sim.control_vars["rcic"].get(), 0)
        with self.assertRaises(ValueError):
            self.backend.select_scenario("LBLOCA")
        self.backend.start_demo(BWR_DEMO_SCRIPTS[0])
        self.assertTrue(self.backend.demo_mode)
        self.backend.reset()
        self.assertEqual(self.backend.plant_type, "BWR")
        self.assertAlmostEqual(self.backend.state.P, 7.0, places=6)

    def test_unknown_plant_is_rejected(self):
        with self.assertRaises(ValueError):
            self.backend.select_plant("CANDU")

    def test_all_teaching_demos_start_and_apply_their_first_fault(self):
        expected_breaks = {
            "SBLOCA recovery": 12, "LBLOCA ECCS response": 70,
            "Loss of heat sink recovery": 0, "Station blackout recovery": 0,
        }
        fault_times = {
            "SBLOCA recovery": 20.1, "LBLOCA ECCS response": 15.1,
            "Loss of heat sink recovery": 20.1, "Station blackout recovery": 15.1,
        }
        for script in DEMO_SCRIPTS:
            with self.subTest(script=script):
                self.backend.start_demo(script)
                self.backend.advance_elapsed(fault_times[script], max_steps=500)
                self.assertTrue(self.backend.demo_mode)
                self.assertIn("Fault inserted", self.backend.sim.demo_stage)
                self.assertEqual(self.backend.sim.control_vars["break"].get(), expected_breaks[script])

    def test_bwr_demonstrations_apply_bwr_specific_faults(self):
        expected = (
            (BWR_DEMO_SCRIPTS[0], "recirc", 0),
            (BWR_DEMO_SCRIPTS[1], "main_steam", 0),
            (BWR_DEMO_SCRIPTS[2], "feedwater", 0),
        )
        for script, control, value in expected:
            with self.subTest(script=script):
                self.backend.select_plant("BWR")
                self.backend.start_demo(script)
                self.backend.advance_elapsed(15.1, max_steps=400)
                self.assertIn("Demo:", self.backend.state.scenario_name)
                self.assertEqual(self.backend.sim.control_vars[control].get(), value)

    def test_demo_action_log_records_recovery_changes_without_duplicates(self):
        self.backend.start_demo("SBLOCA recovery")
        self.backend.apply_demo_mode()
        initial_count = len(self.backend.demo_action_log)
        self.backend.apply_demo_mode()
        self.assertEqual(len(self.backend.demo_action_log), initial_count)
        self.backend.state.t = 100.0
        self.backend.apply_demo_mode()
        self.assertIn("ECCS", self.backend.demo_action_log[-1])
        self.assertIn("Actions:", self.backend.demo_action_log[-1])

        self.backend.select_plant("BWR")
        self.backend.start_demo(BWR_DEMO_SCRIPTS[0])
        self.backend.state.t = 20.0
        self.backend.apply_demo_mode()
        self.assertIn("Recirculation", self.backend.demo_action_log[-1])
        self.assertIn("80%", self.backend.demo_action_log[-1])

    def test_stopping_demo_returns_manual_control(self):
        self.backend.start_demo(DEMO_SCRIPTS[0])
        self.backend.stop_demo()
        self.assertFalse(self.backend.demo_mode)
        self.assertIn("manual control", self.backend.sim.demo_stage)


if __name__ == "__main__": unittest.main()
