# ui_components/ble_manager.py - USB serial implementation (replaces BLE)
import threading
import time
from PyQt6.QtCore import QThread, pyqtSignal
import serial
from serial.tools import list_ports

from config import DEVICE_NAME, BAUD_RATE, SCAN_TIMEOUT, RECONNECT_DELAY


class BLEManager(QThread):
    """Serial port manager used by the dashboard.

    The class name is kept as BLEManager so the rest of the UI code
    does not need to change, but all communication is over USB serial.
    It exposes the same Qt signals as the old BLE implementation:

      - devices_found(list[{name,address,rssi}])
      - scan_error(str)
      - connection_status(str, str)
      - data_received(str)  # one complete text line per emit
    """

    devices_found = pyqtSignal(list)
    scan_error = pyqtSignal(str)
    connection_status = pyqtSignal(str, str)
    data_received = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._stop_event = threading.Event()
        self._scan_requested = False
        self._connect_requested_port: str | None = None
        self._disconnect_requested = False
        self._serial: serial.Serial | None = None
        self._rx_buffer: str = ""
        self._tx_queue: list[str] = []
        self.connected: bool = False

    # ------------------------------------------------------------------
    # Public API used by the dashboard
    # ------------------------------------------------------------------
    def scan_devices(self) -> None:
        """Request a one-shot scan for serial ports."""
        self._scan_requested = True

    def connect_to_device(self, port: str) -> None:
        """Request connection to the given serial port (e.g. 'COM5')."""
        self._connect_requested_port = port

    def disconnect_device(self) -> None:
        """Request the serial port to be closed."""
        self._disconnect_requested = True

    def is_connected(self) -> bool:
        return self.connected

    def send_command(self, command: str) -> None:
        """Queue a line of text to be sent over serial.

        Commands are automatically line-terminated with '\n'.
        """
        if not command:
            return
        self._tx_queue.append(command)

    def stop(self) -> None:
        """Stop the background thread and close the port."""
        self._stop_event.set()
        self._disconnect_requested = True

    # ------------------------------------------------------------------
    # Thread entry point
    # ------------------------------------------------------------------
    def run(self) -> None:
        """Main worker loop running in a separate thread."""
        while not self._stop_event.is_set():
            try:
                if self._scan_requested:
                    self._do_scan()
                    self._scan_requested = False

                if self._connect_requested_port:
                    self._open_serial(self._connect_requested_port)
                    self._connect_requested_port = None

                if self._disconnect_requested:
                    self._close_serial()
                    self._disconnect_requested = False

                if self._serial and self._serial.is_open:
                    self._service_tx()
                    self._service_rx()
                else:
                    self.connected = False

                # Small sleep to avoid a busy-wait loop
                time.sleep(0.01)
            except Exception as exc:  # noqa: BLE001
                # Any unexpected error should be surfaced but not crash the app
                self.connection_status.emit("error", f"Serial thread error: {exc}")
                time.sleep(RECONNECT_DELAY)

        # On thread exit, make sure the port is closed
        self._close_serial()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _do_scan(self) -> None:
        """Enumerate available serial ports and emit devices_found."""
        try:
            ports = list_ports.comports()
            devices = []
            for p in ports:
                desc = p.description or p.device

                # If the OS description already embeds the COM port
                # (e.g. 'USB-SERIAL CH340 (COM3)'), strip the trailing
                # '(COMx)' so we don't show the port twice.
                base_desc = desc
                if "(" in desc and p.device in desc:
                    base_desc = desc.split("(")[0].strip()

                # Prefer the Altimeter branding when present
                if DEVICE_NAME.lower() in base_desc.lower():
                    name = DEVICE_NAME
                else:
                    name = base_desc or p.device

                devices.append({
                    "name": name,
                    "address": p.device,
                    "rssi": "N/A",
                })

            self.devices_found.emit(devices)
        except Exception as exc:  # noqa: BLE001
            self.scan_error.emit(f"Serial scan failed: {exc}")

    def _open_serial(self, port: str) -> None:
        """Open the given serial port."""
        try:
            # Close any existing connection first
            if self._serial and self._serial.is_open:
                try:
                    self._serial.close()
                except Exception:
                    pass

            self._serial = serial.Serial(port, BAUD_RATE, timeout=0.1)
            self.connected = True
            self.connection_status.emit("connected", f"Connected to Altimeter on {port}")
        except Exception as exc:  # noqa: BLE001
            self._serial = None
            self.connected = False
            self.connection_status.emit("error", f"Failed to open {port}: {exc}")

    def _close_serial(self) -> None:
        """Close the current serial port, if any."""
        if self._serial:
            try:
                if self._serial.is_open:
                    self._serial.close()
            except Exception:
                pass
        self._serial = None
        if self.connected:
            self.connected = False
            self.connection_status.emit("disconnected", "Disconnected from device")

    def _service_tx(self) -> None:
        """Send any queued commands over serial."""
        if not self._serial or not self._serial.is_open:
            return

        # Send at most a few commands per iteration to keep UI responsive
        for _ in range(8):
            if not self._tx_queue:
                break
            cmd = self._tx_queue.pop(0)
            try:
                line = (cmd.strip() + "\n").encode("utf-8", errors="ignore")
                self._serial.write(line)
            except Exception as exc:  # noqa: BLE001
                self.connection_status.emit("error", f"Failed to send '{cmd}': {exc}")
                break

    def _service_rx(self) -> None:
        """Read any available data and emit complete lines."""
        if not self._serial or not self._serial.is_open:
            return

        try:
            data = self._serial.read(1024)
        except serial.SerialException as exc:  # type: ignore[attr-defined]
            # Treat as disconnect
            self.connection_status.emit("error", f"Serial read error: {exc}")
            self._close_serial()
            return
        except Exception as exc:  # noqa: BLE001
            self.connection_status.emit("error", f"Serial read error: {exc}")
            return

        if not data:
            return

        try:
            chunk = data.decode("utf-8", errors="ignore")
        except Exception:
            return

        if not chunk:
            return

        self._rx_buffer += chunk
        while "\n" in self._rx_buffer:
            line, self._rx_buffer = self._rx_buffer.split("\n", 1)
            line = line.strip().rstrip("\r")
            if not line:
                continue
            # Emit each complete line for higher-level parsing
            self.data_received.emit(line)
