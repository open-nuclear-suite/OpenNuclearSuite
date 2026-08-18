import json
import unittest

from protocol import ProtocolError, decode_panel_line, encode_message
from hardware_reactor_simulator import HardwareReactorSimulatorTk


class FakeScale:
    def __init__(self):
        self.value = None

    def set(self, value):
        self.value = float(value)


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

    def test_hardware_bridge_uses_inserted_rod_convention(self):
        app = HardwareReactorSimulatorTk.__new__(HardwareReactorSimulatorTk)
        app.last_panel_sequence = -1
        for name in (
            "rod_scale", "flow_scale", "sink_scale", "set_scale", "boron_scale",
            "fault_severity_scale",
        ):
            setattr(app, name, FakeScale())
        command = decode_panel_line(
            '{"v":1,"type":"analog","name":"rod_insertion_pct","value":80,"seq":1}'
        )
        app.apply_hardware_command(command)
        self.assertEqual(app.rod_scale.value, 80.0)

        legacy = decode_panel_line(
            '{"v":1,"type":"analog","name":"rod_position_pct","value":20,"seq":2}'
        )
        app.apply_hardware_command(legacy)
        self.assertEqual(app.rod_scale.value, 80.0)


if __name__ == "__main__":
    unittest.main()
