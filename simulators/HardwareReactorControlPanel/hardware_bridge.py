"""Threaded serial I/O. Tkinter and reactor state are never touched here."""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from protocol import PanelCommand, ProtocolError, decode_panel_line, encode_message


@dataclass
class BridgeStatus:
    connected: bool = False
    last_rx_monotonic: float = 0.0
    valid_messages: int = 0
    invalid_messages: int = 0
    last_error: str = ""


class SerialHardwareBridge:
    """Own the serial port on a worker thread and expose bounded queues."""

    def __init__(self, port: str, baudrate: int = 115200, timeout_s: float = 0.10):
        self.port = port
        self.baudrate = baudrate
        self.timeout_s = timeout_s
        self.commands: queue.Queue[PanelCommand] = queue.Queue(maxsize=100)
        self.outputs: queue.Queue[bytes] = queue.Queue(maxsize=10)
        self.status = BridgeStatus()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="reactor-panel-serial", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.5)

    def get_commands(self, limit: int = 25) -> list[PanelCommand]:
        result = []
        for _ in range(limit):
            try:
                result.append(self.commands.get_nowait())
            except queue.Empty:
                break
        return result

    def send_state(self, state: dict) -> None:
        payload = encode_message("state", **state)
        try:
            self.outputs.put_nowait(payload)
        except queue.Full:
            try:
                self.outputs.get_nowait()
            except queue.Empty:
                pass
            self.outputs.put_nowait(payload)

    def _run(self) -> None:
        try:
            import serial  # type: ignore
            with serial.Serial(self.port, self.baudrate, timeout=self.timeout_s) as connection:
                self.status.connected = True
                connection.write(encode_message("hello", name="simulator", value="ready"))
                while not self._stop.is_set():
                    line = connection.readline()
                    if line:
                        self._accept_line(line)
                    try:
                        connection.write(self.outputs.get_nowait())
                    except queue.Empty:
                        pass
        except Exception as exc:  # surfaced in the GUI; worker must not crash the app
            self.status.last_error = str(exc)
        finally:
            self.status.connected = False

    def _accept_line(self, line: bytes) -> None:
        try:
            command = decode_panel_line(line)
            self.commands.put_nowait(command)
        except (ProtocolError, queue.Full) as exc:
            self.status.invalid_messages += 1
            self.status.last_error = str(exc)
            return
        self.status.valid_messages += 1
        self.status.last_rx_monotonic = time.monotonic()


def autodetect_port() -> str | None:
    """Return a likely USB serial port, preferring a uniquely available port."""
    try:
        from serial.tools import list_ports  # type: ignore
    except ImportError:
        return None
    ports = list(list_ports.comports())
    usb = [p.device for p in ports if p.vid is not None]
    candidates = usb or [p.device for p in ports]
    return candidates[0] if len(candidates) == 1 else None
