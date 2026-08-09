"""Regression tests for reactor GUI scheduling during slider interaction."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import reactor_teaching_simulator as simulator


class GuiResponsivenessTests(TestCase):
    def make_app(self, active_scale):
        app = simulator.ReactorTeachingSimulatorTk.__new__(
            simulator.ReactorTeachingSimulatorTk
        )
        app.model = SimpleNamespace(
            s=SimpleNamespace(running=True),
            advance=Mock(),
        )
        app.root = SimpleNamespace(after=Mock())
        app.active_scale = active_scale
        app.display_dirty = False
        app.last_display_refresh = 10.0
        app.display_refresh_interval_s = 0.20
        app.sync_controls_from_model = Mock()
        app.refresh_all = Mock()
        return app

    @patch.object(simulator.time, "perf_counter", return_value=10.25)
    def test_drag_keeps_physics_and_plot_running_without_control_sync(self, _clock):
        app = self.make_app(active_scale=object())

        app.schedule_loop()

        app.model.advance.assert_called_once_with(0.20)
        app.refresh_all.assert_called_once_with()
        app.sync_controls_from_model.assert_not_called()
        app.root.after.assert_called_once_with(40, app.schedule_loop)

    @patch.object(simulator.time, "perf_counter", return_value=10.25)
    def test_idle_refresh_synchronizes_model_driven_controls(self, _clock):
        app = self.make_app(active_scale=None)

        app.schedule_loop()

        app.model.advance.assert_called_once_with(0.20)
        app.sync_controls_from_model.assert_called_once_with()
        app.refresh_all.assert_called_once_with()
