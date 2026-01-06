# ui_dashboard.py - COMPLETE FIXED VERSION
import sys
from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QSplitter, QMessageBox, QFileDialog, QScrollArea
from PyQt6.QtCore import QTimer, Qt, pyqtSlot
from PyQt6.QtGui import QGuiApplication
import os
from io import StringIO

import numpy as np
import pandas as pd
from config import CMD_MEMORY_STATUS, CMD_EXTRACT_DATA, CMD_CLEAR_MEMORY

# Legacy python_app UI is no longer used in the merged app.
LabMainWindow = None  # kept for backward compatibility but never instantiated

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ui_components.control_panel import ControlPanel
from ui_components.data_panel import DataPanel
from ui_components.ble_manager import BLEManager
from ui_components.data_manager import DataManager

class TelemetryDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        # Initialize managers first
        self.ble_manager = BLEManager()
        self.data_manager = DataManager()
        
        # Initialize UI components
        self.control_panel = ControlPanel()
        self.data_panel = DataPanel()
        
        self.setup_ui()
        self.setup_connections()
        self.setup_managers()
        
        # State variables
        self.is_connected = False
        self.auto_scroll = True
        self.is_exporting_data = False
        self.connection_verified = False
        self.exported_samples = 0
        self.expected_samples = 0

        # Legacy lab-analysis window from python_app is no longer used
        self.lab_window = None

        # Buffers for BLE flash dump via time_s,alt_m,... CSV
        self._ble_dump_active: bool = False
        self._ble_dump_lines: list[str] = []

        # State for chunked file-style export over BLE (FINFO/FGET)
        self._file_export_active: bool = False
        self._file_total_chunks: int = 0
        self._file_next_chunk: int = 0
        self._file_total_samples: int = 0
        self._file_samples_per_chunk: int = 0
        self._file_last_completed_chunk: int = -1
        self._file_session_id = None  # optional session identifier from FILEINFO
        
    def setup_ui(self):
        self.setWindowTitle("Altimeter Flight Data Viewer - Flash Storage Dashboard")
        
        # Set window size to fit screen with 16:9 aspect ratio
        screen = QGuiApplication.primaryScreen()
        geom = screen.availableGeometry() if screen else None
        if geom:
            target_width = int(geom.width() * 0.9)
            target_height = int(target_width * 9 / 16)
            if target_height > int(geom.height() * 0.9):
                target_height = int(geom.height() * 0.9)
                target_width = int(target_height * 16 / 9)
            self.resize(target_width, target_height)
            self.move(
                geom.x() + (geom.width() - target_width) // 2,
                geom.y() + (geom.height() - target_height) // 2,
            )
        else:
            self.resize(1280, 720)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Make the left control panel scrollable so sections have more room.
        # Horizontal scrolling is disabled so the toolbar never scrolls
        # sideways; the control panel will resize to fit the available
        # width and use vertical scrolling only.
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        left_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.control_panel.setMinimumWidth(0)
        left_scroll.setWidget(self.control_panel)
        splitter.addWidget(left_scroll)

        # Make the main visualization area scrollable so graphs have more room
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        right_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        right_scroll.setWidget(self.data_panel)
        splitter.addWidget(right_scroll)
        splitter.setSizes([420, 980])
        
        main_layout.addWidget(splitter)

        # Attach the live communication logs group under the sample rate section on the left
        logs_group = self.data_panel.create_log_group()
        self.control_panel.add_logs_group(logs_group)
        
    def setup_connections(self):
        # Control Panel signals
        self.control_panel.scan_requested.connect(self.scan_devices)
        self.control_panel.connect_requested.connect(self.connect_device)
        self.control_panel.disconnect_requested.connect(self.disconnect_device)
        self.control_panel.memory_check_requested.connect(self.check_memory)
        self.control_panel.memory_erase_requested.connect(self.erase_memory)
        self.control_panel.extract_data_requested.connect(self.extract_data)
        self.control_panel.export_requested.connect(self.export_to_csv)
        self.control_panel.import_csv_requested.connect(self.import_csv)
        self.control_panel.view_data_requested.connect(self.view_all_data)
        self.control_panel.sample_rate_apply_requested.connect(self.on_sample_rate_changed)
        
        # Data Panel signals
        self.data_panel.auto_scroll_changed.connect(self.set_auto_scroll)
        self.data_panel.clear_logs_requested.connect(self.clear_logs)
        self.data_panel.save_logs_requested.connect(self.save_logs)
        self.data_panel.clear_requested.connect(self.handle_refresh)
        
        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(1000)
        
    def setup_managers(self):
        # BLE Manager signals
        self.ble_manager.devices_found.connect(self.on_devices_found)
        self.ble_manager.scan_error.connect(self.on_scan_error)
        self.ble_manager.connection_status.connect(self.on_connection_status)
        self.ble_manager.data_received.connect(self.on_data_received)
        self.ble_manager.start()
        
    @pyqtSlot(list)
    def on_devices_found(self, devices):
        self.control_panel.update_devices_list(devices)
        if devices:
            self.log_message(f"Found {len(devices)} Altimeter device(s) on USB serial ports")
        else:
            self.log_message("No Altimeter devices found on USB serial ports")
        
    @pyqtSlot(str)
    def on_scan_error(self, error_message):
        self.log_message(f"❌ {error_message}")
        QMessageBox.warning(self, "Scan Error", error_message)
        
    @pyqtSlot(str, str)
    def on_connection_status(self, status: str, message: str) -> None:
        """Handle connection status updates from the serial manager."""
        self.control_panel.update_connection_status(status, message)
        self.log_message(message)

        if status == "connected":
            self.is_connected = True
            self.connection_verified = True
            # After a successful connection, automatically query memory so the
            # dashboard shows how full the flash is.
            QTimer.singleShot(1000, self.check_memory)
        elif status == "disconnected":
            self.is_connected = False
            self.connection_verified = False
            if self.is_exporting_data:
                self.log_message("⚠️ Export interrupted because the device was disconnected.")
                self.is_exporting_data = False
                self.data_panel.update_export_progress(0, 0)
                self.control_panel.update_extract_progress(0, 0)
        elif status == "error":
            self.log_message("⚠️ Communication problem with the Altimeter. Please check the USB cable and port.")

    @pyqtSlot(str)
    def on_data_received(self, data: str) -> None:
        """Handle all incoming data from the Altimeter over USB serial.

        The firmware streams human-readable text lines. For flash dumps
        it sends a CSV header (time_s,...) followed by one CSV row per
        sample and finishes with an '=== END FLASH DUMP ===' marker.
        Other lines carry memory/config/status information.
        """
        line = (data or "").strip()
        if not line:
            return

        print(f"📨 SERIAL RX: '{line}'")

        # ------------------------------------------------------------------
        # Heartbeat from firmware
        # ------------------------------------------------------------------
        if "DEVICE_ALIVE" in line:
            print("💓 Heartbeat received")
            if not self.is_connected or not self.connection_verified:
                self.is_connected = True
                self.connection_verified = True
                self.control_panel.update_connection_status("connected", "Device connected")
            return

        # ------------------------------------------------------------------
        # Memory status
        # ------------------------------------------------------------------
        if line.startswith("MEMORY:"):
            self.process_memory_data(line)
            return

        # ------------------------------------------------------------------
        # Configuration (e.g. sample rate)
        # ------------------------------------------------------------------
        if line.startswith("CONFIG:"):
            self.process_config_data(line)
            return

        # ------------------------------------------------------------------
        # Flash memory cleared
        # ------------------------------------------------------------------
        if line == "MEMORY_CLEARED":
            print("Memory cleared confirmation received")
            self.data_manager.process_incoming_data(line)
            memory_status = self.data_manager.get_memory_status()
            self.control_panel.update_memory_display(memory_status)
            self.data_panel.update_extracted_data_table(self.data_manager.get_flight_data())
            self.data_panel.clear_visualization()
            self.log_message("Memory cleared on device")
            # Also reset progress indicators
            self.data_panel.update_export_progress(0, 0)
            self.control_panel.update_extract_progress(0, 0)
            return

        # ------------------------------------------------------------------
        # Explicit "no data" response when flash is empty
        # ------------------------------------------------------------------
        if line in ("NO_DATA_IN_FLASH", "No data in flash"):
            self.data_manager.clear_data()
            self.data_panel.clear_visualization()
            self.data_panel.update_extracted_data_table(self.data_manager.get_flight_data())
            self.log_message("Device reports no stored samples in flash")
            self.data_panel.update_export_progress(0, 0)
            self.control_panel.update_extract_progress(0, 0)
            return

        # ------------------------------------------------------------------
        # Start of CSV dump
        # ------------------------------------------------------------------
        if line.startswith("time_s,") or line.startswith("t_ms,") or line.startswith("timestamp,"):
            # Reset state for a fresh dump
            self._ble_dump_active = True
            self._ble_dump_lines = [line]
            self.is_exporting_data = True
            self.exported_samples = 0

            total = self.expected_samples if self.expected_samples > 0 else 0
            self.data_panel.update_export_progress(0, total)
            self.control_panel.update_extract_progress(0, total)
            self.log_message("Starting data download from the Altimeter...")
            return

        # ------------------------------------------------------------------
        # End of CSV dump
        # ------------------------------------------------------------------
        if line.startswith("=== END FLASH DUMP"):
            self._ble_dump_active = False
            self.is_exporting_data = False
            if self._ble_dump_lines:
                self._handle_ble_dump_complete()
            else:
                self.log_message("Flash dump ended but no CSV lines were received")
                self.data_panel.update_export_progress(0, 0)
                self.control_panel.update_extract_progress(0, 0)
            return

        # ------------------------------------------------------------------
        # CSV sample line while a dump is active
        # ------------------------------------------------------------------
        if self._ble_dump_active and "," in line:
            self._ble_dump_lines.append(line)
            self.exported_samples += 1
            total = self.expected_samples if self.expected_samples > 0 else self.exported_samples
            self.data_panel.update_export_progress(self.exported_samples, total)
            self.control_panel.update_extract_progress(self.exported_samples, total)
            if self.exported_samples and self.exported_samples % 100 == 0:
                self.log_message(f"Received {self.exported_samples} samples...")
            return

        # ------------------------------------------------------------------
        # Fallback: delegate other lines to DataManager and log them
        # ------------------------------------------------------------------
        self.data_manager.process_incoming_data(line)

        if not line.startswith("TELEMETRY:") and not line.startswith("STATUS:"):
            self.log_message(line)

            session_part = f", session {self._file_session_id}" if self._file_session_id is not None else ""
            self.log_message(
                f"Starting chunked export: {total_chunks} chunks, {total_samples} samples" + session_part
            )
            # Request first (or resumed) chunk
            self.log_message(f"[TX] FGET:{self._file_next_chunk}")
            self.ble_manager.send_command(f"FGET:{self._file_next_chunk}")
            return
            return

        # --- Handle flash dump over BLE using time_s,alt_m,... CSV ---------
        # Start of dump (header line)
        if data.startswith("time_s,"):
            if self._file_export_active:
                # Chunked export path: first chunk gets header stored,
                # subsequent chunks' headers are ignored (we only need
                # one header at the top of the combined CSV).
                if not self._ble_dump_lines:
                    self._ble_dump_lines.append(data)
                self._ble_dump_active = True
                return

            # Legacy single-shot dump path: reset state entirely.
            self._ble_dump_active = True
            self._ble_dump_lines = [data]
            # Initialize progress UI at 0% for this extraction
            self.data_panel.update_export_progress(0, 1)
            self.control_panel.update_extract_progress(0, 1)
            return

        """
        # Explicit "no data" message from firmware (sent instead of CSV)
        if data == "NO_DATA_IN_FLASH":
            # Clear any partial buffer and show a friendly message
            self._ble_dump_active = False
            self._ble_dump_lines = []
            self.data_manager.clear_data()
            self.data_panel.clear_visualization()
            self.data_panel.update_extracted_data_table(self.data_manager.get_flight_data())
            self.log_message("Device reports no stored samples in flash")
            # Progress back to idle
            self.data_panel.update_export_progress(0, 0)
            self.control_panel.update_extract_progress(0, 0)
            return

        # End marker from firmware: end of current chunk or full dump
        if data.startswith("=== END FLASH DUMP"):
            self._ble_dump_active = False
            if self._file_export_active:
                # Mark current chunk as completed
                self._file_last_completed_chunk = self._file_next_chunk

                # Update progress based on completed chunks
                done_chunks = self._file_next_chunk + 1
                est_done_samples = min(
                    done_chunks * self._file_samples_per_chunk,
                    self._file_total_samples or done_chunks * self._file_samples_per_chunk,
                )
                total_samples = self._file_total_samples or (self._file_total_chunks * self._file_samples_per_chunk)
                self.data_panel.update_export_progress(est_done_samples, total_samples)
                self.control_panel.update_extract_progress(est_done_samples, total_samples)

                # Completed one chunk; decide whether to request the next
                self._file_next_chunk += 1
                if self._file_next_chunk < self._file_total_chunks:
                    self.log_message(
                        f"Requesting next chunk {self._file_next_chunk}/{self._file_total_chunks}"
                    )
                    self.log_message(f"[TX] FGET:{self._file_next_chunk}")
                    # Small pacing between chunks to avoid hammering BLE
                    QTimer.singleShot(
                        200,
                        lambda idx=self._file_next_chunk: self.ble_manager.send_command(f"FGET:{idx}")
                    )
                else:
                    # All chunks fetched; process entire CSV buffer
                    self._file_export_active = False
                    if self._ble_dump_lines:
                        self._handle_ble_dump_complete()
                    else:
                        self.log_message("Flash dump ended but no CSV lines were received")
                        # Reset progress indicators
                        self.data_panel.update_export_progress(0, 0)
                        self.control_panel.update_extract_progress(0, 0)
            else:
                # Legacy single-shot dump behaviour
                if self._ble_dump_lines:
                    self._handle_ble_dump_complete()
                else:
                    self.log_message("Flash dump ended but no CSV lines were received")
                    # Reset progress indicators
                    self.data_panel.update_export_progress(0, 0)
                    self.control_panel.update_extract_progress(0, 0)
            return

        # While an export is active, accumulate CSV rows
        if self._ble_dump_active and "," in data:
            self._ble_dump_lines.append(data)
            return
        elif self._file_export_active:
            # Ignore unexpected non-CSV noise during an active export
            self.log_message(f"⚠️ Ignoring unexpected line during export: {data}")
            return

        # Handle export progress
        if data.startswith("EXPORT_PROGRESS:"):
            progress_parts = data.split(":")
            if len(progress_parts) > 1:
                progress_info = progress_parts[1].split("/")
                if len(progress_info) == 2:
                    current = int(progress_info[0])
                    total = int(progress_info[1])
                    self.expected_samples = total
                    progress_percent = (current / total) * 100 if total > 0 else 0
                    self.log_message(f"Export progress: {current}/{total} ({progress_percent:.1f}%)")
                    self.data_panel.update_export_progress(current, total)
                    self.control_panel.update_extract_progress(current, total)

                    # Safety net: if progress reaches 100% but we never see
                    # an "=== END FLASH DUMP ===" line (e.g. due to a lost
                    # final packet), still attempt to finalize using whatever
                    # CSV lines we have buffered.
                    if total > 0 and current >= total and self._ble_dump_lines:
                        self._ble_dump_active = False
                        self._handle_ble_dump_complete()
                        return
            return
            
        # Process memory status
        if data.startswith("MEMORY:"):
            print("🔄 Processing memory data")
            self.process_memory_data(data)
            return

        # Process configuration status (e.g. sample rate)
        if data.startswith("CONFIG:"):
            self.process_config_data(data)
            return
            
        # Handle heartbeat
        if "DEVICE_ALIVE" in data:
            print("💓 Heartbeat received")
            if not self.is_connected or not self.connection_verified:
                self.is_connected = True
                self.connection_verified = True
                self.control_panel.update_connection_status("connected", "Device connected")
            return
            
        # Handle memory cleared
        if data == "MEMORY_CLEARED":
            print("Memory cleared confirmation received")
            self.data_manager.process_incoming_data(data)
            memory_status = self.data_manager.get_memory_status()
            self.control_panel.update_memory_display(memory_status)
            self.data_panel.update_extracted_data_table(self.data_manager.get_flight_data())
            self.data_panel.clear_visualization()
            self.log_message("Memory cleared on device")
            return
            
        # Handle data export control messages
        if data.startswith("t_ms,") or data.startswith("timestamp,"):
            # CSV header from firmware - ignore, processor handles data lines only
            return
        
        if data == "BEGIN_DATA_EXPORT":
            print("🚀 Data export started")
            self.is_exporting_data = True
            self.exported_samples = 0
            self.expected_samples = 0
            self.log_message("📥 Arduino started controlled data export...")
            # Clear previous data
            self.data_manager.clear_data()
            self.data_panel.update_extracted_data_table(self.data_manager.get_flight_data())
            return
            
        elif data == "END_DATA_EXPORT":
            print("🏁 Data export ended")
            self.log_message("📦 Arduino finished sending data")
            return
            
        elif data == "DATA_EXPORT_COMPLETE":
            print("✅ Data export completed")
            self.is_exporting_data = False
            self.log_message("✅ Arduino data export completed!")
            
            # Debug the export data before processing
            self.data_manager.data_processor.debug_export_data()
            
            # Force immediate processing
            self.process_data_export_complete()
            return
            
        # Handle CSV data lines - SIMPLIFIED PROCESSING
        if self._is_csv_data(data):
            self.exported_samples += 1
            if self.exported_samples % 50 == 0:
                self.log_message(f"📥 Received {self.exported_samples} samples...")
                
            # Process through data_manager - SIMPLE AND DIRECT
            self.data_manager.process_incoming_data(data)
            return
            
        # Process other data types
        self.data_manager.process_incoming_data(data)
            
        # Log other messages
        if not data.startswith("TELEMETRY:") and not data.startswith("STATUS:"):
            self.log_message(f"📨 {data}")

        """
    def _is_csv_data(self, data):
        """Check if data is CSV format"""
        if (',' in data and 
            not data.startswith('STATUS:') and 
            not data.startswith('MEMORY:') and
            data != 'BEGIN_DATA_EXPORT' and
            data != 'END_DATA_EXPORT' and
            data != 'DATA_EXPORT_COMPLETE' and
            not data.startswith('timestamp,altitude,acceleration') and
            not data.startswith('DEVICE_ALIVE') and
            not data.startswith('TELEMETRY:') and
            not data.startswith('EXPORT_PROGRESS:')):
            
            parts = data.split(',')
            if len(parts) >= 3:
                try:
                    int(parts[0])  # timestamp
                    float(parts[1])  # altitude
                    float(parts[2])  # acceleration
                    return True
                except:
                    return False
        return False
        
    def process_memory_data(self, data):
        """Process memory status data"""
        print(f"🔄 Processing memory: {data}")
        processed_data = self.data_manager.data_processor.process_raw_data(data)
        if processed_data and processed_data.get("data_type") == "memory":
            memory_status = self.data_manager.data_processor.get_memory_status(processed_data)
            self.control_panel.update_memory_display(memory_status)
            # Remember how many samples are stored so progress bars can
            # track real-time extraction progress during a dump.
            self.expected_samples = memory_status.get("total_samples", 0)
            self.log_message(
                f"💾 Memory: {memory_status['total_samples']} samples ({memory_status['usage_percent']}% used)"
            )
        else:
            print(f"❌ Failed to process memory data: {data}")

    def process_config_data(self, data: str) -> None:
        """Process configuration status data (e.g. sample rate)."""
        # Expected format: CONFIG:sampleRateHz=NN
        if not data.startswith("CONFIG:"):
            return
        payload = data[len("CONFIG:"):]
        parts = payload.split("=")
        if len(parts) != 2:
            return
        key, value = parts[0].strip(), parts[1].strip()
        if key.lower() == "sampleratehz":
            try:
                rate = int(value)
            except ValueError:
                return
            self.control_panel.update_sample_rate_display(rate)
            # Also update the visualization stats bar's sample-rate field
            if hasattr(self.data_panel, "update_sample_rate"):
                self.data_panel.update_sample_rate(rate)
            self.log_message(f"⚙️ Device sample rate: {rate} Hz")

    def _handle_ble_dump_complete(self) -> None:
        """Convert BLE CSV dump (time_s,alt_m,ax_ms2,ay_ms2,az_ms2) into flight_data.

        This is used for both legacy single-shot dumps and the newer
        chunked FINFO/FGET path. For chunked exports, we also validate
        that the final row count matches the device-reported totalSamples
        from FILEINFO so we never silently accept truncated data.
        """
        if not self._ble_dump_lines:
            self.log_message("❌ Flash dump ended but no data lines captured")
            return

        # Some lines may be corrupted or contain unexpected extra fields
        # (e.g. due to partial packets or spurious text). The firmware
        # always sends exactly 5 comma-separated fields per CSV row, but in
        # practice we sometimes see extra fragments appended. We try to
        # salvage these cases by truncating to the first 5 numeric fields
        # where possible, and only drop lines that cannot be repaired.
        cleaned_lines: list[str] = []
        skipped_malformed = 0
        fixed_malformed = 0
        for ln in self._ble_dump_lines:
            if ln.startswith("time_s,"):
                cleaned_lines.append(ln)
                continue

            comma_count = ln.count(",")
            if comma_count == 4:
                cleaned_lines.append(ln)
                continue

            if comma_count > 4:
                # Attempt to salvage by taking only the first 5 comma-
                # separated fields if they all parse as floats.
                parts = ln.split(",")
                if len(parts) >= 5:
                    candidate = ",".join(parts[:5])
                    try:
                        _ = [float(x) for x in parts[:5]]
                        cleaned_lines.append(candidate)
                        fixed_malformed += 1
                        self.log_message(
                            f"⚠️ Salvaged malformed CSV line by truncating extra fields: {ln}"
                        )
                        continue
                    except Exception:  # noqa: BLE001
                        # fall through to skipping
                        pass

            # If we reach here, the line could not be interpreted as a
            # single well-formed CSV row.
            skipped_malformed += 1
            self.log_message(f"⚠️ Skipping malformed CSV line: {ln}")

        if len(cleaned_lines) <= 1:
            self.log_message("❌ No valid CSV rows after filtering malformed lines")
            return

        csv_text = "\n".join(cleaned_lines)
        try:
            df = pd.read_csv(StringIO(csv_text))
        except Exception as exc:  # noqa: BLE001
            self.log_message(f"❌ Failed to parse dump CSV: {exc}")
            return

        # Coerce numeric columns and drop bad rows (like in read_flight_log.py)
        for col in ["time_s", "alt_m", "ax_ms2", "ay_ms2", "az_ms2"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=["time_s", "alt_m", "ax_ms2", "ay_ms2", "az_ms2"]).reset_index(drop=True)

        parsed_rows = len(df)
        self.log_message(f"🔎 Parsed {parsed_rows} rows from BLE dump before filtering")

        # If this dump came from the chunked FILEINFO/FGET path and the
        # firmware reported a non-zero totalSamples, compare that count to
        # what we actually reconstructed. We account for any lines we had
        # to drop as irreparable so small, localized corruption can be
        # reported but does not silently slip by.
        if self._file_total_samples and self._file_total_samples > 0:
            effective = parsed_rows + skipped_malformed
            # Allow a small tolerance for missing samples so that tiny
            # gaps caused by one-off corrupted lines do not block the
            # whole export. If the gap is larger than the tolerance,
            # treat it as a hard failure.
            if effective < self._file_total_samples:
                missing = self._file_total_samples - effective
                # Tolerance: at least 5 samples, or 1% of expected
                allowed_missing = max(5, int(self._file_total_samples * 0.01))
                if missing > allowed_missing:
                    self.log_message(
                        "❌ Export inconsistent: device FILEINFO reported "
                        f"{self._file_total_samples} samples but desktop parsed "
                        f"{parsed_rows} (" + str(skipped_malformed) + " irreparable lines skipped). "
                        "Gap exceeds tolerance; data will not be used."
                    )
                    from PyQt6.QtWidgets import QMessageBox as _QMessageBox  # local import to avoid cycles
                    _QMessageBox.warning(
                        self,
                        "Export Incomplete",
                        "The BLE export appears to be incomplete or corrupted.\\n"
                        "Expected " + str(self._file_total_samples) +
                        " samples, but only " + str(parsed_rows) + " were parsed.\\n"
                        "Irreparable malformed lines: " + str(skipped_malformed) + ".\\n"
                        "Please retry the extraction. No partial dataset was loaded."
                    )
                    # Reset progress indicators and buffered lines; keep existing
                    # flight_data untouched so plots/tables remain valid.
                    self.data_panel.update_export_progress(0, 0)
                    self.control_panel.update_extract_progress(0, 0)
                    self._ble_dump_lines = []
                    self._file_export_active = False
                    return

                # Within tolerance: warn but continue and use the data.
                self.log_message(
                    "⚠️ Export missing " + str(missing) + " sample(s) relative to FILEINFO "
                    f"(tolerance {allowed_missing}). Proceeding with available data."
                )

            elif effective > self._file_total_samples:
                # Should not normally happen, but log and continue if we
                # somehow reconstructed more rows than reported.
                extra = effective - self._file_total_samples
                self.log_message(
                    "⚠️ Export reconstructed " + str(extra) +
                    " more samples than FILEINFO reported; using parsed data."
                )

            # If we reach here, either we matched the expected sample
            # count exactly, or the mismatch was within the allowed
            # tolerance. In both cases, log any malformed-line stats.
            if skipped_malformed or fixed_malformed:
                self.log_message(
                    f"⚠️ Export contained {fixed_malformed} salvaged and "
                    f"{skipped_malformed} discarded malformed line(s)."
                )

        # First-sample altitude sanity filter
        if len(df) >= 2:
            first_alt = df.loc[0, "alt_m"]
            second_alt = df.loc[1, "alt_m"]
            if first_alt > 1000.0 and second_alt < 500.0:
                df = df.iloc[1:].reset_index(drop=True)

        # Some devices can wrap the circular flash buffer so that a tail
        # of an old session appears before the new session that starts
        # near time_s == 0. To keep plots and CSV clean, drop any leading
        # rows that come *before* the smallest time_s value.
        if "time_s" in df.columns and not df.empty:
            try:
                t_series = df["time_s"].astype(float)
                idx0 = int(t_series.idxmin())
                if idx0 > 0:
                    df = df.iloc[idx0:].reset_index(drop=True)
            except Exception:
                # If anything goes wrong, keep the original data rather
                # than risking dropping valid samples.
                pass

        if df.empty:
            # No valid rows – treat as "no data" from device
            self.data_manager.clear_data()
            self.data_panel.clear_visualization()
            self.data_panel.update_extracted_data_table(self.data_manager.get_flight_data())
            self.log_message("Device reports no stored samples in flash")
            return

        # Adapt to merged_app flight_data schema
        df["device_timestamp"] = (df["time_s"] * 1000.0).round().astype(int)
        df["altitude"] = df["alt_m"]
        df["acceleration"] = np.sqrt(df["ax_ms2"] ** 2 + df["ay_ms2"] ** 2 + df["az_ms2"] ** 2)

        # Store into DataManager / DataProcessor
        try:
            self.data_manager.set_flight_data(df)
        except Exception as exc:  # noqa: BLE001
            self.log_message(f"❌ Failed to store flight data from BLE dump: {exc}")
            return

        # Derive memory status from number of samples using the same
        # firmware TOTAL_SAMPLES constant as config.py so the desktop UI
        # and device stay in sync.
        try:
            from config import TOTAL_SAMPLES  # type: ignore

            samples = len(df)
            usage = int((samples / TOTAL_SAMPLES) * 100) if TOTAL_SAMPLES > 0 else 0
            memory_status = {
                "total_samples": samples,
                "usage_percent": usage,
                "max_capacity": TOTAL_SAMPLES,
                "is_full": samples >= TOTAL_SAMPLES,
                "data_points": samples,
            }
            self.control_panel.update_memory_display(memory_status)
        except Exception:
            pass

        # Reuse existing handler to update tables, plots, stats, and message
        self.process_data_export_complete(source="device")

        # Once processed, clear buffered lines so subsequent END markers or
        # retries won't re-run the same dataset.
        self._ble_dump_lines = []
        
    def process_data_export_complete(self, source: str | None = None) -> None:
        """Handle completion of a dataset load (device dump or CSV import)."""
        if source is None:
            source = getattr(self, "_last_data_source", "device")
        self._last_data_source = source

        flight_data = self.data_manager.get_flight_data()
        samples_count = len(flight_data)

        self.log_message(f"Processing {samples_count} samples from {source}...")

        # Reset progress display
        self.data_panel.update_export_progress(0, 0)
        self.control_panel.update_extract_progress(0, 0)

        if samples_count <= 0:
            self.log_message("❌ No data is available to display")
            QMessageBox.warning(
                self,
                "No Data",
                "No flight data is available. The device may be empty or the file was invalid.",
            )
            return

        # Update the extracted data table
        self.data_panel.update_extracted_data_table(flight_data)

        # Update statistics and plots
        stats = self.data_manager.get_statistics()
        self.control_panel.update_statistics(stats)
        phases = self.data_manager.get_flight_phases()
        self.data_panel.update_visualization(flight_data, phases)

        # Compute total duration in seconds from device_timestamp when available
        duration_s = 0.0
        if "device_timestamp" in flight_data.columns and len(flight_data["device_timestamp"]) > 1:
            ts = flight_data["device_timestamp"].astype(float)
            duration_s = float((ts.max() - ts.min()) / 1000.0)

        if source == "csv":
            title = "CSV Loaded"
            body = (
                "CSV file loaded successfully.\n\n"
                f"Samples: {samples_count}\n"
                f"Total duration: {duration_s:.1f} s"
            )
        else:
            title = "Data Extracted"
            body = (
                "Data extracted successfully from the Altimeter.\n\n"
                f"Samples: {samples_count}\n"
                f"Total duration: {duration_s:.1f} s"
            )

        self.log_message(f"{title}: {samples_count} samples, {duration_s:.1f} s")
        QMessageBox.information(self, title, body)
        # Switch to extracted data tab
        self.data_panel.switch_to_extracted_tab()
        
    def scan_devices(self):
        """Scan for Altimeter devices on USB serial ports."""
        self.log_message("Scanning for serial ports...")
        self.ble_manager.scan_devices()
        
    def connect_device(self, address):
        """Connect to the Altimeter on the selected serial port."""
        if not address:
            self.show_message("Please select a serial port first")
            return
        
        self.log_message(f"Connecting to {address}...")
        self.ble_manager.connect_to_device(address)
        
    def disconnect_device(self):
        """Disconnect from the Altimeter."""
        self.log_message("Disconnecting...")
        self.ble_manager.disconnect_device()

    def on_sample_rate_changed(self, rate_hz: int) -> None:
        """Handle user-requested sample rate change from the control panel."""
        if not self.ble_manager.is_connected():
            self.show_message("Not connected to any device")
            return
        self.log_message(f"Setting device sample rate to {rate_hz} Hz...")
        try:
            # Firmware command: R10 / R25 / R50
            self.ble_manager.send_command(f"R{rate_hz}")
        except Exception as e:
            self.log_message(f"❌ Failed to send sample rate command: {e}")
        
    def check_memory(self):
        """Request a flash memory status update from the device."""
        if not self.ble_manager.is_connected():
            self.show_message("Not connected to any device")
            return
        
        self.log_message("Checking memory status...")
        self.ble_manager.send_command(CMD_MEMORY_STATUS)
        
    def erase_memory(self):
        """Erase flash memory on the Altimeter."""
        if not (self.ble_manager.is_connected() or self.is_connected):
            self.show_message("Not connected to any device")
            return
        
        reply = QMessageBox.question(
            self, "Confirm Erase", 
            "⚠️ This will erase ALL stored data!\nThis action cannot be undone.\n\nAre you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.log_message("Sending memory erase command...")
            self.ble_manager.send_command(CMD_CLEAR_MEMORY)
            # UI will be updated when MEMORY_CLEARED is received
            
    def generate_test_data(self):
        """Generate test data in Arduino flash memory"""
        if not self.ble_manager.is_connected():
            self.show_message("Not connected to any device")
            return
            
        reply = QMessageBox.question(
            self, "Generate Test Data", 
            "🎯 This will generate 100 test samples in the Arduino's flash memory.\nThis is useful for testing data extraction.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.ble_manager.send_command("GENERATE_TEST_DATA")
            self.log_message("🎯 Test data generation command sent")
            
    def extract_data(self):
        """Extract data from the Altimeter's flash memory over USB serial."""
        if not (self.ble_manager.is_connected() or self.is_connected):
            self.show_message("Not connected to any device")
            return
        
        reply = QMessageBox.question(
            self,
            "Extract Data",
            "This will extract all data stored in flash memory.\n"
            "This may take a few moments.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Clear previous data and UI safely
                self.data_manager.clear_data()
                if hasattr(self.data_panel, "clear_visualization"):
                    self.data_panel.clear_visualization()
                self.data_panel.update_extracted_data_table(self.data_manager.get_flight_data())
                
                # Reset dump state before starting a new export
                self._ble_dump_active = False
                self._ble_dump_lines = []
                
                # Begin export
                self.is_exporting_data = True
                self.exported_samples = 0
                # expected_samples is set from the latest MEMORY: response;
                # if it is zero we will fall back to counting lines.
                self.control_panel.update_extract_progress(0, self.expected_samples)
                self.data_panel.update_export_progress(0, self.expected_samples)
                self.log_message("Starting data download from the Altimeter. This may take a few seconds...")

                # Send the simple 'D' command to stream the CSV dump.
                self.log_message(f"[TX] {CMD_EXTRACT_DATA}")
                self.ble_manager.send_command(CMD_EXTRACT_DATA)
            except Exception as e:
                self.log_message(f"❌ Error starting extraction: {e}")
            
    def plot_data(self):
        """Plot the extracted data"""
        flight_data = self.data_manager.get_flight_data()
        if flight_data.empty:
            self.show_message("No data to plot. Please extract data from flash first.")
            return
            
        phases = self.data_manager.get_flight_phases()
        self.data_panel.update_visualization(flight_data, phases)
        self.log_message("Plotting extracted data...")
        
    def export_to_csv(self):
        """Export currently loaded flight data to a CSV file.

        The exported CSV has exactly the same structure as the Extracted
        Data tab:

        - device_timestamp (seconds, 2 decimals)
        - altitude, acceleration, ax_ms2, ay_ms2, az_ms2 (raw values)
        - altitude_filtered, acceleration_filtered, velocity_filtered
          (processed values used for plotting)
        """
        flight_data = self.data_manager.get_flight_data()
        if flight_data.empty:
            self.show_message("No data to export. Please extract data or import a CSV first.")
            return

        from datetime import datetime
        default_name = f"flight_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", default_name, "CSV Files (*.csv)"
        )
        if not filename:
            return

        # Canonical column order shared with DataPanel.update_extracted_data_table()
        base_columns = [
            "device_timestamp",  # seconds in the CSV
            "altitude",
            "acceleration",
            "ax_ms2",
            "ay_ms2",
            "az_ms2",
            "altitude_filtered",
            "acceleration_filtered",
            "velocity_filtered",
        ]

        df = flight_data.copy()

        # Ensure we have a millisecond timestamp column; visible/exported
        # time will be seconds.
        if "device_timestamp" not in df.columns:
            import numpy as _np

            for alt_time_col in ("time_s", "t_ms", "timestamp_ms"):
                if alt_time_col in df.columns:
                    series = _np.asarray(df[alt_time_col], dtype=float)
                    if alt_time_col == "time_s":
                        df["device_timestamp"] = _np.round(series * 1000.0).astype(int)
                    else:
                        df["device_timestamp"] = series.astype(int)
                    break

        # Build processed series so that altitude_filtered / etc match the
        # graphs. This reuses the same helper as DataPanel.
        processed, _stats = self.data_panel._build_processed_from_dataframe(df)
        has_processed = processed is not None and bool(getattr(processed, "time", []))

        import numpy as _np
        import pandas as _pd

        n_rows = len(df)
        if n_rows == 0:
            self.show_message("No data to export.")
            return

        # Time in seconds is derived from device_timestamp milliseconds.
        ts_ms = _np.asarray(df.get("device_timestamp", _np.arange(n_rows)), dtype=float)
        time_s = ts_ms / 1000.0

        data_dict: dict[str, list] = {"device_timestamp": [round(float(t), 2) for t in time_s]}

        # Helper to safely pull a raw column if present
        def _col_or_nan(name: str) -> list:
            if name in df.columns:
                return [df[name].iloc[i] for i in range(n_rows)]
            return [float("nan")] * n_rows

        for raw_name in ["altitude", "acceleration", "ax_ms2", "ay_ms2", "az_ms2"]:
            if raw_name in df.columns:
                data_dict[raw_name] = _col_or_nan(raw_name)

        if has_processed:
            alt_f = processed.altitude_smooth
            vel_f = processed.velocity_smooth
            acc_f = processed.acceleration_smooth

            data_dict["altitude_filtered"] = [
                float(alt_f[i]) if i < len(alt_f) else float("nan") for i in range(n_rows)
            ]
            data_dict["acceleration_filtered"] = [
                float(acc_f[i]) if i < len(acc_f) else float("nan") for i in range(n_rows)
            ]
            data_dict["velocity_filtered"] = [
                float(vel_f[i]) if i < len(vel_f) else float("nan") for i in range(n_rows)
            ]

        export_df = _pd.DataFrame(data_dict)

        # Enforce canonical column order and drop anything unexpected.
        final_columns = [c for c in base_columns if c in export_df.columns]
        export_df = export_df[final_columns]

        try:
            # Format device_timestamp with exactly two decimals by casting
            # to strings; other columns are left numeric.
            export_df["device_timestamp"] = export_df["device_timestamp"].map(
                lambda v: f"{float(v):.2f}"
            )
            export_df.to_csv(filename, index=False)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Export Failed", f"Could not write CSV file:\n{exc}")
            return

        self.log_message(f"Data exported to {filename}")
        # Inform the user that the CSV contains both raw and filtered data.
        QMessageBox.information(
            self,
            "CSV Exported",
            "The CSV file was exported successfully and contains both raw "
            "sensor data (directly from the hardware) and filtered altitude, "
            "velocity, and acceleration columns generated by the desktop application.",
        )
                
    def import_csv(self):
        """Import a CSV file for offline analysis (no hardware required)."""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Import Altimeter CSV",
            "",
            "CSV Files (*.csv);;All Files (*)",
        )
        if not filename:
            return

        try:
            df = pd.read_csv(filename)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Import Failed", f"Could not read CSV file:\n{exc}")
            return

        # Normalize column names for matching
        cols = {c.lower(): c for c in df.columns}

        # Time column: the new format uses a single device_timestamp
        # column in seconds with two decimals. Internally we still work
        # in milliseconds.
        if "device_timestamp" in cols:
            device_ts_col = cols["device_timestamp"]
            time_s = df[device_ts_col].astype(float)
            df["device_timestamp"] = (time_s * 1000.0).round().astype(int)
        elif "time_s" in cols:
            time_s_col = cols["time_s"]
            df["device_timestamp"] = (
                df[time_s_col].astype(float) * 1000.0
            ).round().astype(int)
        else:
            QMessageBox.warning(
                self,
                "Import Failed",
                "CSV must contain a 'device_timestamp' or 'time_s' column.",
            )
            return

        # Altitude column: altitude or alt_m
        if "altitude" in cols:
            alt_col = cols["altitude"]
        elif "alt_m" in cols:
            alt_m_col = cols["alt_m"]
            df["altitude"] = df[alt_m_col].astype(float)
            alt_col = "altitude"
        else:
            QMessageBox.warning(
                self,
                "Import Failed",
                "CSV must contain an 'altitude' or 'alt_m' column.",
            )
            return

        # Acceleration column: use existing or compute magnitude from ax/ay/az
        if "acceleration" in cols:
            accel_col = cols["acceleration"]
        else:
            ax_col = cols.get("ax_ms2")
            ay_col = cols.get("ay_ms2")
            az_col = cols.get("az_ms2")
            if ax_col and ay_col and az_col:
                df["acceleration"] = np.sqrt(
                    df[ax_col].astype(float) ** 2
                    + df[ay_col].astype(float) ** 2
                    + df[az_col].astype(float) ** 2
                )
            else:
                df["acceleration"] = 0.0

        # Apply the same "start-of-flight" trimming used for device dumps so
        # that imported CSVs also drop any leading wrapped/stale samples. We
        # look for the smallest time value and discard rows before it.
        try:
            if "time_s" in cols:
                t_series = df[cols["time_s"]].astype(float)
            else:
                # device_timestamp is in milliseconds; convert to seconds for
                # the same comparison behaviour.
                t_series = (df["device_timestamp"].astype(float) / 1000.0)

            idx0 = int(t_series.idxmin())
            if idx0 > 0:
                df = df.iloc[idx0:].reset_index(drop=True)
        except Exception:
            # If anything fails here, keep original data rather than risk
            # dropping valid rows.
            pass

        # The new combined format already includes the filtered
        # columns. Keep them as-is if present so plots and the table can
        # show both raw and filtered data.
        # No special tagging is required; we simply propagate the
        # columns into the internal flight_data DataFrame.

        try:
            self.data_manager.set_flight_data(df)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(
                self,
                "Import Failed",
                f"Could not load CSV into data model:\n{exc}",
            )
            return

        self._last_data_source = "csv"
        self.process_data_export_complete(source="csv")

    def view_all_data(self):
        """View all extracted data"""
        flight_data = self.data_manager.get_flight_data()
        if flight_data.empty:
            self.show_message("No data to display. Extract data from flash first.")
            return
            
        self.data_panel.update_extracted_data_table(flight_data)
        self.data_panel.switch_to_extracted_tab()
        self.log_message(f"Displaying {len(flight_data)} data samples")
        
    def set_auto_scroll(self, enabled):
        """Set auto-scroll for logs"""
        self.auto_scroll = enabled
        
    def clear_logs(self):
        """Clear communication logs"""
        self.data_panel.clear_logs()
        self.log_message("Logs cleared")
        
    def handle_refresh(self) -> None:
        """Clear current data, plots and logs ready for a new extraction."""
        self.data_manager.clear_data()
        self.data_panel.clear_visualization()
        self.data_panel.update_extracted_data_table(self.data_manager.get_flight_data())
        self.data_panel.clear_logs()
        self.data_panel.update_export_progress(0, 0)
        self.control_panel.update_extract_progress(0, 0)
        # Reset expected sample count until the next MEMORY: response
        self.expected_samples = 0
        self.log_message("Refresh requested: cleared data, plots, and logs. Ready for a new download.")
        
    def save_logs(self):
        """Save logs to file"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Logs", "communication_log.txt", "Text Files (*.txt);;All Files (*)"
        )
        if filename:
            try:
                log_content = self.data_panel.communication_log.toPlainText()
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(log_content)
                self.log_message(f"Logs saved to {filename}")
            except Exception as e:
                self.show_message(f"Error saving logs: {e}")
                
    def update_display(self):
        """Update display with current statistics"""
        stats = self.data_manager.get_statistics()
        self.control_panel.update_statistics(stats)
        
    def log_message(self, message: str) -> None:
        """Append a line to the communication log."""
        self.data_panel.add_log_message(message)
        if self.auto_scroll:
            scrollbar = self.data_panel.communication_log.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        
    def show_message(self, message):
        """Show information message box"""
        QMessageBox.information(self, "Information", message)
        
    def closeEvent(self, event):
        """Handle application close event"""
        self.log_message("Shutting down...")
        if hasattr(self, 'ble_manager'):
            self.ble_manager.disconnect_device()
            self.ble_manager.stop()
            self.ble_manager.wait(3000)
        event.accept()