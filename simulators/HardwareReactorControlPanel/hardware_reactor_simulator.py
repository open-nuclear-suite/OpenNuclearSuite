"""Hardware-ready GUI that extends, but does not modify, the canonical simulator."""

from __future__ import annotations

import argparse
import sys
import time
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANONICAL_DIR = HERE.parent / "ReactorPhysicsSimulator"
if str(CANONICAL_DIR) not in sys.path:
    sys.path.insert(0, str(CANONICAL_DIR))

from reactor_teaching_simulator import (  # noqa: E402
    ReactorTeachingSimulatorTk,
    rod_insertion_from_withdrawn,
    show_startup_splash,
)

from hardware_bridge import SerialHardwareBridge, autodetect_port  # noqa: E402
from protocol import PanelCommand  # noqa: E402


class HardwareReactorSimulatorTk(ReactorTeachingSimulatorTk):
    OUTPUT_INTERVAL_S = 0.20

    def __init__(self, root: tk.Tk, port: str | None, baudrate: int = 115200):
        self.bridge = SerialHardwareBridge(port, baudrate) if port else None
        self.last_hardware_output = 0.0
        self.last_panel_sequence = -1
        self.last_connection_state: bool | None = None
        super().__init__(root)
        self.root.title("UNTESTED HARDWARE PROTOTYPE - Reactor Control Panel Simulator")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        if self.bridge:
            self.bridge.start()
            self.model.s.add_log(f"Hardware interface opening {port} at {baudrate} baud.")
        else:
            self.model.s.add_log("Hardware interface disabled; GUI-only mode.")
        self.model.s.add_log(
            "WARNING: suggested physical hardware and reference firmware are untested."
        )

    def close(self) -> None:
        if self.bridge:
            self.bridge.close()
        self.root.destroy()

    def schedule_loop(self) -> None:
        if self.bridge:
            connected = self.bridge.status.connected
            if connected != self.last_connection_state:
                self.last_connection_state = connected
                state_text = "CONNECTED" if connected else "DISCONNECTED"
                self.root.title(f"UNTESTED HARDWARE PROTOTYPE - PANEL {state_text}")
                if self.bridge.status.last_error:
                    self.model.s.add_log(f"Hardware panel {state_text}: {self.bridge.status.last_error}")
                else:
                    self.model.s.add_log(f"Hardware panel {state_text}.")
            for command in self.bridge.get_commands():
                self.apply_hardware_command(command)
            now = time.monotonic()
            if now - self.last_hardware_output >= self.OUTPUT_INTERVAL_S:
                self.bridge.send_state(self.hardware_state())
                self.last_hardware_output = now
        super().schedule_loop()

    def apply_hardware_command(self, command: PanelCommand) -> None:
        if command.kind == "hello":
            # A panel reboot restarts its sequence counter.
            self.last_panel_sequence = -1
            self.model.s.add_log("Hardware panel handshake received.")
            return
        if command.sequence is not None:
            if command.sequence <= self.last_panel_sequence:
                return
            self.last_panel_sequence = command.sequence

        if command.kind == "button":
            callbacks = {
                "start": self.start_cb,
                "pause": self.pause_cb,
                "scram": self.scram_cb,
                "reset": self.reset_cb,
                "step": self.step_cb,
                "trim_minus": self.minus_cb,
                "trim_plus": self.plus_cb,
            }
            callbacks[command.name]()
            return
        if command.kind == "mode":
            self.mode_var.set(command.value)
            {"manual": self.manual_mode_cb, "auto": self.auto_mode_cb,
             "load_follow": self.load_follow_mode_cb}[command.value]()
            return
        if command.kind != "analog":
            return

        value = float(command.value)
        if command.name == "rod_position_pct":
            # Compatibility with the original prototype protocol, where this
            # field meant percent withdrawn. The 1.3.0 panel sends insertion.
            self.rod_scale.set(100.0 - value)
            return
        scales = {
            "rod_insertion_pct": self.rod_scale,
            "coolant_flow_pct": self.flow_scale,
            "heat_sink_pct": self.sink_scale,
            "power_setpoint_pct": self.set_scale,
            "boron_ppm": self.boron_scale,
            "fault_severity_pct": self.fault_severity_scale,
        }
        scales[command.name].set(value)

    def hardware_state(self) -> dict:
        s = self.model.s
        return {
            "sim_time_s": round(s.time, 2),
            "running": s.running,
            "scram": s.scram,
            "power_pct": round(100.0 * s.P, 3),
            "rod_insertion_pct": round(rod_insertion_from_withdrawn(s.rod_pos), 2),
            # Retained for old monitoring clients; this is percent withdrawn.
            "rod_position_pct": round(s.rod_pos, 2),
            "coolant_flow_pct": round(s.coolantFlow, 2),
            "fuel_temp_c": round(s.fuelT, 2),
            "coolant_temp_c": round(s.coolT, 2),
            "lamp_high_power": s.P > 0.95 * s.tripHighPower,
            "lamp_high_temp": s.fuelT > 0.95 * s.tripHighFuelTemp or s.cladT > 0.95 * s.tripHighCladTemp,
            "lamp_low_flow": s.coolantFlow < 1.05 * s.tripLowFlow,
            "lamp_trip": s.scram,
            "hardware_connected": bool(self.bridge and self.bridge.status.connected),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hardware-ready reactor control-panel simulator")
    parser.add_argument("--port", help="Serial port, for example COM5; omit to auto-detect")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--no-hardware", action="store_true", help="Run the hardware edition without a panel")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    port = None if args.no_hardware else (args.port or autodetect_port())
    root = tk.Tk()
    root.withdraw()
    if port:
        acknowledged = messagebox.askokcancel(
            "UNTESTED HARDWARE PROTOTYPE",
            "WARNING: The suggested physical control-panel build and reference "
            "firmware have not been assembled, commissioned, or tested by this "
            "project. They may contain wiring, electrical, firmware, calibration, "
            "or integration errors. Use only an isolated SELV educational mockup; "
            "never connect it to reactor, laboratory, process-control, protection, "
            "or safety equipment.\n\nContinue at your own risk?",
            icon="warning",
        )
        if not acknowledged:
            root.destroy()
            return
    HardwareReactorSimulatorTk(root, port, args.baud)
    show_startup_splash(
        root,
        module_name="Hardware Reactor Panel — UNTESTED PHYSICAL PROTOTYPE",
        duration_ms=3000,
    )
    root.mainloop()


if __name__ == "__main__":
    main()
