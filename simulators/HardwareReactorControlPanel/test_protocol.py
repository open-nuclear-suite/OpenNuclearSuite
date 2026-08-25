import json
import unittest

from protocol import ProtocolError, decode_panel_line, encode_message
from hardware_reactor_pyqtgraph import HardwareCommandAdapter, hardware_state


class FakeState:
    def __init__(self):
        self.time = 12.345
        self.running = True
        self.scram = False
        self.P = 0.75
        self.rod_pos = 20.0
        self.coolantFlow = 90.0
        self.fuelT = 500.0
        self.coolT = 300.0
        self.cladT = 400.0
        self.tripHighPower = 1.10
        self.tripHighFuelTemp = 900.0
        self.tripHighCladTemp = 700.0
        self.tripLowFlow = 45.0
        self.log = []

    def add_log(self, text):
        self.log.append(text)


class FakeBackend:
    def __init__(self):
        self.state = FakeState()
        self.calls = []

    def __getattr__(self, name):
        def record(*args):
            self.calls.append((name, *args))
        return record


class FakeCanonical:
    @staticmethod
    def rod_insertion_from_withdrawn(value):
        return 100.0 - value

class ProtocolTests(unittest.TestCase):
    def test_analog_is_decoded(self):
        command = decode_panel_line('{"v":1,"type":"analog","name":"rod_insertion_pct","value":42.5,"seq":7}')
        self.assertEqual(command.name, "rod_insertion_pct")
        self.assertEqual(command.value, 42.5)
        self.assertEqual(command.sequence, 7)

    def test_analog_is_clamped(self):
        command = decode_panel_line('{"v":1,"type":"analog","name":"boron_ppm","value":5000}')
        self.assertEqual(command.value, 1000.0)

    def test_unknown_command_is_rejected(self):
        with self.assertRaises(ProtocolError):
            decode_panel_line('{"v":1,"type":"button","name":"launch","value":"pressed"}')

    def test_button_requires_pressed_edge(self):
        with self.assertRaises(ProtocolError):
            decode_panel_line('{"v":1,"type":"button","name":"scram","value":"released"}')

    def test_encoder_emits_strict_json(self):
        encoded = encode_message("state", running=True, power_pct=99.2)
        self.assertEqual(json.loads(encoded), {"v": 1, "type": "state", "running": True, "power_pct": 99.2})

    def test_hardware_adapter_uses_inserted_rod_convention(self):
        backend = FakeBackend()
        adapter = HardwareCommandAdapter(backend, FakeCanonical)
        command = decode_panel_line(
            '{"v":1,"type":"analog","name":"rod_insertion_pct","value":80,"seq":1}'
        )
        adapter.apply(command)
        self.assertEqual(backend.calls[-1], ("set_rod_insertion", 80.0))

        legacy = decode_panel_line(
            '{"v":1,"type":"analog","name":"rod_position_pct","value":20,"seq":2}'
        )
        adapter.apply(legacy)
        self.assertEqual(backend.calls[-1], ("set_rod_insertion", 80.0))

    def test_hardware_adapter_maps_all_backend_controls(self):
        backend = FakeBackend()
        adapter = HardwareCommandAdapter(backend, FakeCanonical)
        messages = (
            '{"v":1,"type":"button","name":"scram","value":"pressed","seq":1}',
            '{"v":1,"type":"mode","name":"control_mode","value":"auto","seq":2}',
            '{"v":1,"type":"analog","name":"power_setpoint_pct","value":85,"seq":3}',
            '{"v":1,"type":"analog","name":"fault_severity_pct","value":70,"seq":4}',
        )
        for message in messages:
            self.assertTrue(adapter.apply(decode_panel_line(message)))
        self.assertEqual(backend.calls, [
            ("scram",), ("set_mode", "auto"),
            ("set_control", "setpoint", 0.85),
            ("set_control", "fault_severity", 70.0),
        ])

    def test_duplicate_sequence_is_ignored(self):
        backend = FakeBackend()
        adapter = HardwareCommandAdapter(backend, FakeCanonical)
        message = decode_panel_line(
            '{"v":1,"type":"button","name":"start","value":"pressed","seq":5}'
        )
        self.assertTrue(adapter.apply(message))
        self.assertFalse(adapter.apply(message))
        self.assertEqual(backend.calls, [("start",)])

    def test_hardware_state_uses_canonical_2_0_model_values(self):
        backend = FakeBackend()
        payload = hardware_state(backend, FakeCanonical, connected=True)
        self.assertEqual(payload["sim_time_s"], 12.35)
        self.assertEqual(payload["power_pct"], 75.0)
        self.assertEqual(payload["rod_insertion_pct"], 80.0)
        self.assertTrue(payload["hardware_connected"])


if __name__ == "__main__":
    unittest.main()
