"""Newline-delimited JSON protocol shared by the simulator and panel firmware."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


PROTOCOL_VERSION = 1

ANALOG_INPUTS = {
    "rod_insertion_pct": (0.0, 100.0),
    # Backward-compatible input for pre-1.3.0 prototype firmware. Its value is
    # interpreted by the GUI bridge as the old percent-withdrawn convention.
    "rod_position_pct": (0.0, 100.0),
    "coolant_flow_pct": (20.0, 120.0),
    "heat_sink_pct": (30.0, 120.0),
    "power_setpoint_pct": (30.0, 120.0),
    "boron_ppm": (0.0, 1000.0),
    "fault_severity_pct": (0.0, 100.0),
}

BUTTON_INPUTS = {
    "start",
    "pause",
    "scram",
    "reset",
    "step",
    "trim_minus",
    "trim_plus",
}

MODE_INPUTS = {"manual", "auto", "load_follow"}


class ProtocolError(ValueError):
    """Raised for a malformed or unsupported panel message."""


@dataclass(frozen=True)
class PanelCommand:
    kind: str
    name: str
    value: Any = None
    sequence: int | None = None


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def decode_panel_line(line: str | bytes) -> PanelCommand:
    """Decode and validate one input line; values are clamped at the trust boundary."""
    if isinstance(line, bytes):
        try:
            line = line.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProtocolError("message is not UTF-8") from exc
    if len(line) > 1024:
        raise ProtocolError("message exceeds 1024 bytes")
    try:
        message = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ProtocolError("message is not valid JSON") from exc
    if not isinstance(message, dict) or message.get("v") != PROTOCOL_VERSION:
        raise ProtocolError("unsupported or missing protocol version")

    kind = message.get("type")
    name = message.get("name")
    sequence = message.get("seq")
    if sequence is not None and (not isinstance(sequence, int) or sequence < 0):
        raise ProtocolError("seq must be a non-negative integer")

    if kind == "analog" and name in ANALOG_INPUTS:
        try:
            value = float(message["value"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ProtocolError("analog value must be numeric") from exc
        low, high = ANALOG_INPUTS[name]
        return PanelCommand(kind, name, clamp(value, low, high), sequence)
    if kind == "button" and name in BUTTON_INPUTS:
        if message.get("value") != "pressed":
            raise ProtocolError("button messages must use value='pressed'")
        return PanelCommand(kind, name, "pressed", sequence)
    if kind == "mode" and name == "control_mode" and message.get("value") in MODE_INPUTS:
        return PanelCommand(kind, name, message["value"], sequence)
    if kind == "hello" and name == "panel":
        return PanelCommand(kind, name, message.get("value"), sequence)
    raise ProtocolError("unknown command type or name")


def encode_message(message_type: str, **fields: Any) -> bytes:
    message = {"v": PROTOCOL_VERSION, "type": message_type, **fields}
    return (json.dumps(message, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
