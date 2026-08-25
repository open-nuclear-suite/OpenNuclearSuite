import tempfile
import unittest
from pathlib import Path

from reactor_gui_backend import ReactorGUIBackend
from reactor_teaching_simulator import PedagogicalSettings


class ReactorGUIBackendTests(unittest.TestCase):
    def setUp(self):
        self.backend = ReactorGUIBackend()

    def test_elapsed_time_uses_fixed_steps_only_while_running(self):
        self.assertEqual(self.backend.advance_elapsed(1.0), 0)
        self.backend.start()
        self.assertEqual(self.backend.advance_elapsed(0.051), 2)
        self.assertAlmostEqual(self.backend.state.time, 0.04)

    def test_controls_and_fault_latches(self):
        self.backend.set_rod_insertion(40)
        self.backend.toggle_fault("fault_stuck_rod", True)
        self.backend.set_rod_insertion(10)
        self.assertAlmostEqual(100 - self.backend.state.rod_pos, 40)
        self.backend.toggle_fault("fault_frozen_detector", True)
        self.assertIsNotNone(self.backend.state.frozen_measured_power)

    def test_settings_require_pause(self):
        settings = PedagogicalSettings(kinetics_preset="Intermediate")
        self.backend.apply_settings(settings)
        self.assertEqual(self.backend.state.pedagogical_settings, settings)
        self.backend.start()
        with self.assertRaises(RuntimeError):
            self.backend.apply_settings(PedagogicalSettings())

    def test_csv_export(self):
        self.backend.step()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "run.csv"
            self.assertGreater(self.backend.export_csv(output), 0)
            self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()
