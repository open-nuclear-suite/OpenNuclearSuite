"""Responsive hardware-panel edition of the reactor teaching simulator.

The serial bridge is optional and explicitly untested. Panel commands are
translated onto the same GUI-neutral backend used by the software-only 2.0
reactor interface; serial I/O never touches Qt or the model worker directly.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANONICAL_DIR = HERE.parent / "ReactorPhysicsSimulator"
if str(CANONICAL_DIR) not in sys.path:
    sys.path.insert(0, str(CANONICAL_DIR))

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402
from reactor_pyqtgraph import ReactorWindow, load_backend  # noqa: E402

from hardware_bridge import SerialHardwareBridge, autodetect_port  # noqa: E402
from protocol import PanelCommand  # noqa: E402


SAFETY_WARNING = (
    "The suggested physical control-panel build and reference firmware have "
    "not been assembled, commissioned, or tested by this project. They may "
    "contain wiring, electrical, firmware, calibration, or integration errors. "
    "Use only an isolated SELV educational mockup after independent review. "
    "Never connect it to reactor, laboratory, process-control, protection, or "
    "safety equipment."
)


class HardwareCommandAdapter:
    """Map validated panel commands onto the canonical reactor backend."""

    def __init__(self, backend, canonical):
        self.backend = backend
        self.canonical = canonical
        self.last_sequence = -1

    def apply(self, command: PanelCommand) -> bool:
        if command.kind == "hello":
            self.last_sequence = -1
            self.backend.state.add_log("Hardware panel handshake received.")
            return True
        if command.sequence is not None:
            if command.sequence <= self.last_sequence:
                return False
            self.last_sequence = command.sequence

        if command.kind == "button":
            actions = {
                "start": self.backend.start,
                "pause": self.backend.pause,
                "scram": self.backend.scram,
                "reset": self.backend.reset,
                "step": self.backend.step,
                "trim_minus": lambda: self.backend.trim_reactivity(-5),
                "trim_plus": lambda: self.backend.trim_reactivity(5),
            }
            actions[command.name]()
            return True
        if command.kind == "mode":
            self.backend.set_mode(command.value)
            return True
        if command.kind != "analog":
            return False

        value = float(command.value)
        if command.name == "rod_position_pct":
            self.backend.set_rod_insertion(100.0 - value)
        elif command.name == "rod_insertion_pct":
            self.backend.set_rod_insertion(value)
        elif command.name == "coolant_flow_pct":
            self.backend.set_control("coolantFlow", value)
        elif command.name == "heat_sink_pct":
            self.backend.set_control("heatSink", value)
        elif command.name == "power_setpoint_pct":
            self.backend.set_control("setpoint", value / 100.0)
        elif command.name == "boron_ppm":
            self.backend.set_control("boron_ppm", value)
        elif command.name == "fault_severity_pct":
            self.backend.set_control("fault_severity", value)
        else:
            return False
        return True


def hardware_state(backend, canonical, connected: bool) -> dict:
    s = backend.state
    return {
        "sim_time_s": round(s.time, 2),
        "running": s.running,
        "scram": s.scram,
        "power_pct": round(100.0 * s.P, 3),
        "rod_insertion_pct": round(canonical.rod_insertion_from_withdrawn(s.rod_pos), 2),
        "rod_position_pct": round(s.rod_pos, 2),
        "coolant_flow_pct": round(s.coolantFlow, 2),
        "fuel_temp_c": round(s.fuelT, 2),
        "coolant_temp_c": round(s.coolT, 2),
        "lamp_high_power": s.P > 0.95 * s.tripHighPower,
        "lamp_high_temp": s.fuelT > 0.95 * s.tripHighFuelTemp or s.cladT > 0.95 * s.tripHighCladTemp,
        "lamp_low_flow": s.coolantFlow < 1.05 * s.tripLowFlow,
        "lamp_trip": s.scram,
        "hardware_connected": bool(connected),
    }


class HardwareReactorWindow(ReactorWindow):
    OUTPUT_INTERVAL_S = 0.20

    def __init__(self, backend_cls, canonical, port: str | None, baudrate: int):
        self.bridge = SerialHardwareBridge(port, baudrate) if port else None
        self.last_hardware_output = 0.0
        self.last_connection_state = None
        super().__init__(backend_cls, canonical)
        self.command_adapter = HardwareCommandAdapter(self.backend, canonical)
        self.setWindowTitle("UNTESTED HARDWARE PROTOTYPE - Responsive Reactor Control Panel")
        self.state.add_log(SAFETY_WARNING)
        if self.bridge:
            self.bridge.start()
            self.state.add_log(f"Hardware interface opening {port} at {baudrate} baud.")
        else:
            self.state.add_log("Hardware interface disabled; responsive GUI-only mode.")
        self.refresh()

    def tick(self):
        self.poll_hardware()
        super().tick()

    def poll_hardware(self):
        if not self.bridge:
            return
        connected = self.bridge.status.connected
        if connected != self.last_connection_state:
            self.last_connection_state = connected
            state_text = "CONNECTED" if connected else "DISCONNECTED"
            self.setWindowTitle(f"UNTESTED HARDWARE PROTOTYPE - PANEL {state_text}")
            detail = f": {self.bridge.status.last_error}" if self.bridge.status.last_error else "."
            self.state.add_log(f"Hardware panel {state_text}{detail}")
        changed = False
        for command in self.bridge.get_commands():
            changed = self.command_adapter.apply(command) or changed
        if changed:
            self.sync_controls()
        now = time.monotonic()
        if now - self.last_hardware_output >= self.OUTPUT_INTERVAL_S:
            self.bridge.send_state(hardware_state(self.backend, self.canonical, connected))
            self.last_hardware_output = now

    def closeEvent(self, event):
        self.physics_timer.stop()
        self.ui_timer.stop()
        if self.bridge:
            self.bridge.close()
        super().closeEvent(event)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="Serial port, for example COM5; omit to auto-detect")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--no-hardware", action="store_true", help="Run without a physical panel")
    parser.add_argument("--legacy-tk", action="store_true", help="Use the former Tkinter hardware interface")
    return parser.parse_args(argv)


def main():
    args = parse_args()
    if args.legacy_tk:
        from hardware_reactor_simulator import main as legacy_main
        sys.argv = [sys.argv[0]] + (["--no-hardware"] if args.no_hardware else [])
        if args.port:
            sys.argv.extend(["--port", args.port])
        sys.argv.extend(["--baud", str(args.baud)])
        return legacy_main()

    port = None if args.no_hardware else (args.port or autodetect_port())
    backend_cls, canonical = load_backend(CANONICAL_DIR)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Open Nuclear Suite Hardware Reactor Simulator")
    if port:
        choice = QMessageBox.warning(
            None, "UNTESTED HARDWARE PROTOTYPE", SAFETY_WARNING + "\n\nContinue at your own risk?",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if choice != QMessageBox.StandardButton.Ok:
            return 0
    window = HardwareReactorWindow(backend_cls, canonical, port, args.baud)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
