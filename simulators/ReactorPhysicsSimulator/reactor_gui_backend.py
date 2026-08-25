"""GUI-neutral handlers for the canonical reactor kinetics model."""

from __future__ import annotations

from pathlib import Path

from reactor_teaching_simulator import (
    FAULT_KEYS, PedagogicalSettings, ReactorModel, clamp,
    rod_insertion_from_withdrawn, rod_withdrawn_from_insertion,
)


class ReactorGUIBackend:
    """Canonical operator-control API shared by responsive front ends."""

    def __init__(self, model=None):
        self.model = model or ReactorModel()
        self.physics_credit = 0.0

    @property
    def state(self):
        return self.model.s

    def start(self):
        self.state.running = True
        self.state.add_log("Simulation started.")

    def pause(self):
        self.state.running = False
        self.state.add_log("Simulation paused.")

    def scram(self):
        self.state.scram = True
        self.state.running = True
        self.state.add_log("Manual SCRAM pushbutton pressed. Decay heat remains; maintain cooling.")

    def reset(self, settings=None):
        self.model.reset(settings)
        self.physics_credit = 0.0

    def apply_settings(self, settings: PedagogicalSettings):
        if self.state.running:
            raise RuntimeError("Pause the simulator before changing pedagogical settings")
        self.reset(settings)
        self.state.add_log("Pedagogical settings applied; simulation reset.")

    def set_mode(self, mode):
        if mode not in {"manual", "auto", "load_follow"}:
            raise ValueError(f"Unknown operating mode: {mode}")
        self.state.mode = mode
        self.state.add_log(f"Mode changed to {mode.replace('_', '-').upper()}.")

    def set_rod_insertion(self, insertion):
        s = self.state
        if s.fault_stuck_rod and s.stuck_rod_pos is not None:
            return rod_insertion_from_withdrawn(s.stuck_rod_pos)
        s.rod_pos = rod_withdrawn_from_insertion(clamp(float(insertion), 0.0, 100.0))
        if s.scram and s.rod_pos > 5.0:
            s.scram = False
            s.add_log("SCRAM cleared by rod withdrawal. Use RESET for a clean restart if desired.")
        return rod_insertion_from_withdrawn(s.rod_pos)

    def set_control(self, name, value):
        s = self.state
        limits = {
            "coolantFlow": (5.0, 120.0), "heatSink": (10.0, 120.0),
            "noiseAmp": (0.0, 8.0), "boron_ppm": (0.0, 1000.0),
            "fault_severity": (0.0, 100.0), "setpoint": (0.0, 1.2),
            "rho_manual": (-0.01, 0.01), "source_strength": (1e-8, 1e-3),
        }
        if name not in limits:
            raise ValueError(f"Unknown control: {name}")
        if name == "coolantFlow" and s.fault_pump_trip:
            return s.coolantFlow
        if name == "heatSink" and s.fault_heat_sink_loss:
            return s.heatSink
        if name == "source_strength" and not s.pedagogical_settings.advanced_physics:
            return s.source_strength
        low, high = limits[name]
        setattr(s, name, clamp(float(value), low, high))
        return getattr(s, name)

    def trim_reactivity(self, pcm):
        self.state.rho_manual = clamp(self.state.rho_manual + float(pcm) * 1e-5, -0.01, 0.01)
        self.state.add_log(f"Manual reactivity changed by {float(pcm):+g} pcm.")

    def step(self, seconds=1.0):
        self.model.advance(seconds)
        self.state.add_log(f"Single {seconds:g} s step executed.")

    def advance_elapsed(self, elapsed, speed=1.0, max_steps=250):
        if not self.state.running:
            return 0
        self.physics_credit += max(0.0, elapsed) * max(0.0, speed)
        steps = min(int(self.physics_credit / self.state.dt), max_steps)
        if steps:
            self.model.advance(steps * self.state.dt)
            self.physics_credit -= steps * self.state.dt
        return steps

    def toggle_fault(self, key, active):
        if key not in FAULT_KEYS:
            raise ValueError(f"Unknown fault: {key}")
        s = self.state
        active = bool(active)
        setattr(s, key, active)
        if key == "fault_stuck_rod":
            s.stuck_rod_pos = s.rod_pos if active else None
        elif key == "fault_pump_trip":
            s.pump_trip_start_time = s.time if active else None
            if active:
                s.pump_trip_initial_flow = s.coolantFlow
        elif key == "fault_heat_sink_loss":
            s.heat_sink_loss_start_time = s.time if active else None
            if active:
                s.heat_sink_initial = s.heatSink
        elif key == "fault_frozen_detector":
            s.frozen_measured_power = s.measuredPower if active else None
        elif key == "fault_low_flow_trip_fail":
            s.low_flow_trip_fail_announced = False
        s.add_log(f"FAULT {'ON' if active else 'OFF'}: {key.removeprefix('fault_').replace('_', ' ')}.")

    def export_csv(self, filepath: str | Path):
        return self.model.export_csv(filepath)
