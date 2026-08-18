"""Experimental responsive-GUI variant of the reactor teaching simulator.

This launcher deliberately leaves the canonical simulator unchanged.  It
subclasses only the GUI coordination code so the revised interaction can be
evaluated before it is adopted by the main application.
"""

import time
import tkinter as tk

import reactor_teaching_simulator as canonical


class ResponsiveReactorTeachingSimulatorTk(canonical.ReactorTeachingSimulatorTk):
    """Test GUI that does not let model synchronization fight slider drags."""

    def __init__(self, root):
        super().__init__(root)
        self.root.title(
            "Reactor Teaching Simulator - Responsive GUI Test (experimental)"
        )

    def _set_scale_if_changed(self, scale, value):
        """Update an inactive scale only when its displayed value is stale."""
        if self.active_scale is scale:
            return

        # Avoid generating redundant Tk scale commands every display tick.
        # Half a resolution unit is the natural equality tolerance for a Scale.
        resolution = float(scale.cget("resolution"))
        tolerance = max(abs(resolution) * 0.5, 1.0e-9)
        if abs(float(scale.get()) - float(value)) > tolerance:
            scale.set(value)

    def sync_controls_from_model(self):
        """Synchronize model-driven controls without disturbing an active drag."""
        s = self.model.s
        self.syncing_controls = True
        try:
            self._set_scale_if_changed(
                self.rod_scale, canonical.rod_insertion_from_withdrawn(s.rod_pos)
            )
            self._set_scale_if_changed(self.flow_scale, s.coolantFlow)
            self._set_scale_if_changed(self.sink_scale, s.heatSink)
            self._set_scale_if_changed(self.noise_scale, s.noiseAmp)
            self._set_scale_if_changed(self.set_scale, 100 * s.setpoint)
            self._set_scale_if_changed(self.boron_scale, s.boron_ppm)
            self.mode_var.set(s.mode)

            if hasattr(self, "fault_vars"):
                for key, var in self.fault_vars.items():
                    expected = 1 if getattr(s, key) else 0
                    if int(var.get()) != expected:
                        var.set(expected)
                self._set_scale_if_changed(
                    self.fault_severity_scale, s.fault_severity
                )
                self.fault_severity_label.config(
                    text=f"Fault severity: {s.fault_severity:.0f}%"
                )
        finally:
            self.syncing_controls = False

    def schedule_loop(self):
        """Keep physics and throttled plots running without fighting a drag."""
        if self.model.s.running:
            self.model.advance(0.20)
            self.display_dirty = True

        now = time.perf_counter()
        if (
            self.display_dirty
            and now - self.last_display_refresh >= self.display_refresh_interval_s
        ):
            # Plot throughout a drag so the transient does not accumulate and
            # jump on release.  Model-to-widget synchronization remains
            # suspended until no scale is owned by the mouse.
            if self.active_scale is None:
                self.sync_controls_from_model()
            self.refresh_all()
        self.root.after(40, self.schedule_loop)


def main():
    root = tk.Tk()
    root.withdraw()
    ResponsiveReactorTeachingSimulatorTk(root)
    canonical.show_startup_splash(
        root,
        module_name="Reactor Simulator - Responsive GUI Test",
        duration_ms=1500,
    )
    root.mainloop()


if __name__ == "__main__":
    main()
