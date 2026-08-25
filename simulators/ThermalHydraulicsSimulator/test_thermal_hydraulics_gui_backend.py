import unittest

from thermal_hydraulics_gui_backend import DEMO_SCRIPTS, ThermalHydraulicsGUIBackend


class ThermalHydraulicsGUIBackendTests(unittest.TestCase):
    def setUp(self): self.backend = ThermalHydraulicsGUIBackend()

    def test_elapsed_time_uses_fixed_steps_only_while_running(self):
        self.assertEqual(self.backend.advance_elapsed(0.11), 0)
        self.backend.start()
        self.assertEqual(self.backend.advance_elapsed(0.11), 2)
        self.assertAlmostEqual(self.backend.state.t, 0.1)

    def test_controls_are_clamped_and_validated(self):
        self.assertEqual(self.backend.set_control("break", 150), 100)
        with self.assertRaises(ValueError): self.backend.set_control("unknown", 1)

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

    def test_stopping_demo_returns_manual_control(self):
        self.backend.start_demo(DEMO_SCRIPTS[0])
        self.backend.stop_demo()
        self.assertFalse(self.backend.demo_mode)
        self.assertIn("manual control", self.backend.sim.demo_stage)


if __name__ == "__main__": unittest.main()
