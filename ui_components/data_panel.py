# ui_components/data_panel.py - FIXED CIRCULAR IMPORT
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTextEdit, QCheckBox, QGroupBox, QTabWidget, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QFileDialog)
from PyQt6.QtCore import pyqtSignal, QEvent, Qt, QTimer
from PyQt6.QtGui import QFont
import pyqtgraph as pg
import numpy as np
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

# Local flight-processing models and helpers (derived from previous python_app implementation)

@dataclass
class TelemetryDataPoint:
    timestamp: datetime
    device_timestamp: int
    altitude: float
    ax: float
    ay: float
    az: float

@dataclass
class ProcessedFlightData:
    time: List[float]
    altitude_raw: List[float]
    altitude_smooth: List[float]
    altitude_relative: List[float]
    velocity_raw: List[float]
    velocity_smooth: List[float]
    acceleration_mag: List[float]
    acceleration_net: List[float]
    acceleration_smooth: List[float]

@dataclass
class FlightStats:
    max_altitude: float
    max_velocity: float
    max_acceleration: float
    flight_duration: float
    apogee_time: float


def _rolling_mean(arr: List[float], window: int) -> List[float]:
    if window <= 1 or not arr:
        return list(arr)
    res: List[float] = []
    half = window // 2
    n = len(arr)
    for i in range(n):
        start = max(0, i - half)
        end = min(n, i + half + 1)
        sl = arr[start:end]
        res.append(sum(sl) / len(sl))
    return res


def _median(arr: List[float]) -> float:
    if not arr:
        return 0.0
    s = sorted(arr)
    mid = len(s) // 2
    if len(s) % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def process_flight_data(points: List[TelemetryDataPoint], remove_gravity: bool = True) -> ProcessedFlightData:
    if not points:
        return ProcessedFlightData([], [], [], [], [], [], [], [], [])

    time = [p.device_timestamp / 1000.0 for p in points]
    altitude = [p.altitude for p in points]
    ax = [p.ax for p in points]
    ay = [p.ay for p in points]
    az = [p.az for p in points]

    # Baseline altitude (first second)
    early_mask = [t <= 1.0 for t in time]
    early_altitudes = [altitude[i] for i, m in enumerate(early_mask) if m]
    if len(early_altitudes) >= 5:
        alt_baseline = _median(early_altitudes)
    else:
        alt_baseline = _median(altitude[: min(50, len(altitude))])

    altitude_relative = [a - alt_baseline for a in altitude]

    # Accel magnitude
    acceleration_mag = [float(np.sqrt(ax[i] ** 2 + ay[i] ** 2 + az[i] ** 2)) for i in range(len(ax))]

    # Gravity baseline
    early_acc = [acceleration_mag[i] for i, m in enumerate(early_mask) if m]
    if len(early_acc) >= 5:
        g0 = _median(early_acc)
    else:
        g0 = _median(acceleration_mag[: min(50, len(acceleration_mag))])

    acceleration_net = [a - g0 for a in acceleration_mag] if remove_gravity else list(acceleration_mag)

    window = 25
    altitude_smooth = _rolling_mean(altitude_relative, window)
    acceleration_smooth = _rolling_mean(acceleration_net, window)

    # Velocity from altitude derivative
    velocity_raw: List[float] = [0.0]
    for i in range(1, len(time)):
        dt = time[i] - time[i - 1]
        dalt = altitude_smooth[i] - altitude_smooth[i - 1]
        if dt > 0:
            vel = dalt / dt
            velocity_raw.append(vel if abs(vel) <= 500 else 0.0)
        else:
            velocity_raw.append(0.0)

    velocity_smooth = _rolling_mean(velocity_raw, window)

    return ProcessedFlightData(
        time=time,
        altitude_raw=altitude,
        altitude_smooth=altitude_smooth,
        altitude_relative=altitude_relative,
        velocity_raw=velocity_raw,
        velocity_smooth=velocity_smooth,
        acceleration_mag=acceleration_mag,
        acceleration_net=acceleration_net,
        acceleration_smooth=acceleration_smooth,
    )


def calculate_flight_stats(data: ProcessedFlightData) -> FlightStats:
    if not data.time:
        return FlightStats(0.0, 0.0, 0.0, 0.0, 0.0)

    max_altitude = max(data.altitude_relative) if data.altitude_relative else 0.0
    max_velocity = max((abs(v) for v in data.velocity_smooth), default=0.0)
    max_acceleration = max((abs(a) for a in data.acceleration_net), default=0.0)
    flight_duration = data.time[-1] - data.time[0]
    apogee_time = data.time[data.altitude_relative.index(max_altitude)] if data.altitude_relative else 0.0

    return FlightStats(
        max_altitude=max_altitude,
        max_velocity=max_velocity,
        max_acceleration=max_acceleration,
        flight_duration=flight_duration,
        apogee_time=apogee_time,
    )

# Remove the circular import - FlightVisualization will be imported elsewhere
# from visualization import FlightVisualization
 
class ScrollFriendlyPlotWidget(pg.PlotWidget):
    """PlotWidget whose mouse wheel only zooms after a click.

    If you just scroll over the plot, the event is ignored so the
    surrounding QScrollArea can handle vertical scrolling. Once the
    user left-clicks on the plot, wheel events zoom until the cursor
    leaves the widget.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._zoom_enabled = False

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._zoom_enabled = True
        super().mousePressEvent(ev)

    def leaveEvent(self, ev):
        # When the cursor leaves the plot area, go back to scroll mode.
        self._zoom_enabled = False
        super().leaveEvent(ev)

    def wheelEvent(self, ev):
        if self._zoom_enabled:
            # Normal zoom/pan behaviour from pyqtgraph
            super().wheelEvent(ev)
        else:
            # Let parent scroll area handle the wheel
            ev.ignore()


class DataPanel(QWidget):
    # Signals
    auto_scroll_changed = pyqtSignal(bool)
    clear_logs_requested = pyqtSignal()
    save_logs_requested = pyqtSignal()
    clear_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.flight_viz = None  # Will be set later
        self._last_x_max = None
        self._last_y_min = None
        self._last_y_max = None
        # Logging options
        self._log_show_timestamps = True
        self._log_max_width = 96
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Create tabs
        self.tabs = QTabWidget()
        
        # Real-time Data Tab (visualization-focused; logs are hosted in the left panel)
        realtime_tab = self.create_realtime_tab()
        self.tabs.addTab(realtime_tab, "Real-time Data")
        
        # Extracted Data Tab
        extracted_tab = self.create_extracted_tab()
        self.extracted_tab_index = self.tabs.addTab(extracted_tab, "Extracted Data")
        
        layout.addWidget(self.tabs)
        
    def create_realtime_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Visualization only; communication logs are placed in the control panel
        viz_group = self.create_viz_group()
        layout.addWidget(viz_group)
        
        return tab
        
    def create_extracted_tab(self):
        """Create tab for extracted flash data.

        The table shows one device timestamp column (seconds), the raw
        sensor values received from the hardware, and three filtered
        columns (altitude, acceleration, velocity) computed by the
        desktop application. The CSV export uses the exact same
        structure and column order.
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Progress indicator
        self.export_progress_label = QLabel("No data extraction in progress")
        self.export_progress_label.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(self.export_progress_label)

        # Short description of what the table contains
        self.extracted_info_label = QLabel(
            "This table shows the raw values from the hardware together with "
            "filtered altitude, velocity, and acceleration computed by the application."
        )
        self.extracted_info_label.setWordWrap(True)
        self.extracted_info_label.setStyleSheet(
            "color: #374151; padding: 6px 0 10px 0;"
        )
        layout.addWidget(self.extracted_info_label)

        # Data table for extracted data. Columns are configured
        # dynamically in update_extracted_data_table() so that they
        # always match the CSV export format.
        self.extracted_data_table = QTableWidget()
        self.extracted_data_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.extracted_data_table)

        return tab
        
    def create_log_group(self):
        group = QGroupBox("Live Communication Logs")
        layout = QVBoxLayout(group)
        
        # Log controls
        log_controls = QHBoxLayout()
        
        self.auto_scroll_check = QCheckBox("Auto Scroll")
        self.auto_scroll_check.setChecked(True)
        self.auto_scroll_check.stateChanged.connect(
            lambda state: self.auto_scroll_changed.emit(state == 2)
        )
        log_controls.addWidget(self.auto_scroll_check)

        self.show_timestamps_check = QCheckBox("Show timestamps")
        self.show_timestamps_check.setChecked(True)
        self.show_timestamps_check.stateChanged.connect(
            lambda state: setattr(self, "_log_show_timestamps", state == 2)
        )
        log_controls.addWidget(self.show_timestamps_check)
        
        self.btn_clear_logs = QPushButton("Clear Logs")
        self.btn_clear_logs.clicked.connect(self._on_clear_logs_clicked)
        log_controls.addWidget(self.btn_clear_logs)
        
        self.btn_save_logs = QPushButton("Save Logs")
        self.btn_save_logs.clicked.connect(self._on_save_logs_clicked)
        log_controls.addWidget(self.btn_save_logs)
        
        log_controls.addStretch()
        layout.addLayout(log_controls)
        
        self.communication_log = QTextEdit()
        self.communication_log.setMaximumHeight(200)
        self.communication_log.setFont(QFont("Courier", 9))
        layout.addWidget(self.communication_log)
        
        return group
        
    def create_viz_group(self):
        group = QGroupBox("Flight Data Visualization")
        layout = QVBoxLayout(group)
        # Extra spacing so each graph block has room; the right-hand panel
        # is already inside a QScrollArea, so additional height will make
        # the visualization scroll vertically like a long web page.
        layout.setSpacing(24)

        # --- Flight statistics bar ---
        stats_layout = QHBoxLayout()
        self.stats_labels = {}
        metric_defs = [
            ("Max Altitude", "max_alt"),
            ("Max Velocity", "max_vel"),
            ("Max Accel", "max_acc"),
            ("Flight Duration", "flight_dur"),
            ("Apogee Time", "apogee_time"),
            ("Data Points", "data_points"),
            ("Sample Rate", "sample_rate"),
        ]
        for label_text, key in metric_defs:
            card = QWidget()
            card.setStyleSheet(
                "background-color: #f9fafb;"
                "border: 1px solid #e5e7eb;"
                "border-radius: 8px;"
                "padding: 6px 10px;"
            )
            vbox = QVBoxLayout(card)
            vbox.setContentsMargins(6, 4, 6, 4)
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-size: 11px; color: #6b7280;")
            val_label = QLabel("--")
            val_label.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 13px; color: #111827;")
            vbox.addWidget(lbl)
            vbox.addWidget(val_label)
            stats_layout.addWidget(card)
            self.stats_labels[key] = val_label
        layout.addLayout(stats_layout)
        
        # Controls above the plot
        controls = QHBoxLayout()
        self.btn_set_origin = QPushButton("Set Origin (0,0)")
        self.btn_set_origin.clicked.connect(self.on_set_origin)
        controls.addWidget(self.btn_set_origin)

        self.btn_save_graph = QPushButton("Save Graph")
        self.btn_save_graph.clicked.connect(self.on_save_graph)
        controls.addWidget(self.btn_save_graph)

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setStyleSheet("background-color: #f97316; color: white;")
        self.btn_clear.clicked.connect(self._on_clear_clicked)
        controls.addWidget(self.btn_clear)

        # Gravity toggle (net vs total accel), mirrors python_app MainWindow
        self.gravity_toggle = QCheckBox("Net accel (gravity removed)")
        self.gravity_toggle.setChecked(True)
        self.gravity_toggle.stateChanged.connect(self.on_gravity_toggled)
        controls.addWidget(self.gravity_toggle)

        controls.addStretch()
        layout.addLayout(controls)
        
        # Three stacked pyqtgraph plots: altitude, velocity, acceleration
        pg.setConfigOptions(antialias=True)

        # --- Altitude plot and legend (legend row outside plot, above, left-aligned) ---
        alt_legend_row = QHBoxLayout()
        alt_legend_row.addWidget(self._create_legend_item("#2563eb", False, "Filtered"))
        alt_legend_row.addWidget(self._create_legend_item("#93c5fd", True, "Raw"))
        alt_legend_row.addStretch()
        layout.addLayout(alt_legend_row)

        self.alt_plot = ScrollFriendlyPlotWidget(title="Relative Altitude vs Time")
        self.alt_plot.setBackground("#ffffff")
        self.alt_plot.showGrid(x=True, y=True, alpha=0.12)
        # Give the altitude plot a comfortable minimum height so it
        # doesn't collapse when stacked with the others.
        self.alt_plot.setMinimumHeight(260)
        self.alt_alt_raw = self.alt_plot.plot(
            name="Altitude (raw)",
            pen=pg.mkPen("#93c5fd", width=1, style=pg.QtCore.Qt.PenStyle.DotLine)
        )
        self.alt_alt_smooth = self.alt_plot.plot(
            name="Altitude (filtered)",
            pen=pg.mkPen("#2563eb", width=2)
        )
        layout.addWidget(self.alt_plot)

        # --- Velocity plot and legend ---
        vel_legend_row = QHBoxLayout()
        vel_legend_row.addWidget(self._create_legend_item("#059669", False, "Filtered"))
        vel_legend_row.addWidget(self._create_legend_item("#a7f3d0", True, "Raw"))
        vel_legend_row.addStretch()
        layout.addLayout(vel_legend_row)

        self.vel_plot = ScrollFriendlyPlotWidget(title="Vertical Velocity vs Time (from Altitude)")
        self.vel_plot.setBackground("#ffffff")
        self.vel_plot.showGrid(x=True, y=True, alpha=0.12)
        self.vel_plot.setMinimumHeight(260)
        self.vel_raw = self.vel_plot.plot(
            name="Velocity (raw)",
            pen=pg.mkPen("#a7f3d0", width=1, style=pg.QtCore.Qt.PenStyle.DotLine)
        )
        self.vel_smooth = self.vel_plot.plot(
            name="Velocity (filtered)",
            pen=pg.mkPen("#059669", width=2)
        )
        layout.addWidget(self.vel_plot)

        # --- Acceleration plot and legend ---
        acc_legend_row = QHBoxLayout()
        acc_legend_row.addWidget(self._create_legend_item("#dc2626", False, "Filtered"))
        acc_legend_row.addWidget(self._create_legend_item("#fecaca", True, "Raw"))
        acc_legend_row.addStretch()
        layout.addLayout(acc_legend_row)

        self.acc_plot = ScrollFriendlyPlotWidget(title="Acceleration Magnitude vs Time")
        self.acc_plot.setBackground("#ffffff")
        self.acc_plot.showGrid(x=True, y=True, alpha=0.12)
        self.acc_plot.setMinimumHeight(260)
        self.acc_raw = self.acc_plot.plot(
            name="Acceleration (raw)",
            pen=pg.mkPen("#fecaca", width=1, style=pg.QtCore.Qt.PenStyle.DotLine)
        )
        self.acc_smooth = self.acc_plot.plot(
            name="Acceleration (filtered)",
            pen=pg.mkPen("#dc2626", width=2)
        )
        layout.addWidget(self.acc_plot)

        # Track last ranges for origin button
        self._last_time = None
        self._last_alt_min = None
        self._last_alt_max = None
        # Whether to subtract gravity from acceleration (net accel)
        # Default: show net acceleration (gravity removed)
        self.remove_gravity = True
        # Last known sample rate from device (Hz) for display only
        self.sample_rate_hz = None
        # Cache last flight data/phases so gravity toggle can re-process in real time
        self._cached_flight_data = None
        self._cached_phases = None

        return group
        
    def _create_legend_item(self, color: str, dashed: bool, text: str) -> QWidget:
        """Create a small legend item with a colored line and label.

        Placed outside the plot area in a horizontal legend row.
        """
        container = QWidget()
        h = QHBoxLayout(container)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)

        line = QLabel()
        line.setFixedSize(24, 3)
        if dashed:
            line.setStyleSheet(
                f"border-bottom: 2px dashed {color};"
                "background: transparent;"
            )
        else:
            line.setStyleSheet(
                f"background-color: {color};"
            )

        label = QLabel(text)
        label.setStyleSheet("font-size: 10px; color: #374151;")

        h.addWidget(line)
        h.addWidget(label)

        return container

    def _flash_button(self, button, highlight_css: str = "background-color: #1d4ed8; color: white;") -> None:
        """Temporarily tint a button to provide click feedback."""
        if not button:
            return
        original = button.styleSheet()
        combined = f"{original}; {highlight_css}" if original else highlight_css
        button.setStyleSheet(combined)
        QTimer.singleShot(150, lambda: button.setStyleSheet(original))

    def add_log_message(self, message: str) -> None:
        if message is None:
            return
        text = str(message)
        # Support multi-line messages
        lines = text.splitlines() or [""]
        for line in lines:
            entry = line
            if self._log_show_timestamps:
                ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                entry = f"[{ts}] {line}"
            if self._log_max_width and len(entry) > self._log_max_width:
                entry = entry[: self._log_max_width - 3] + "..."
            self.communication_log.append(entry)
        
    def clear_logs(self):
        self.communication_log.clear()
        
    def update_export_progress(self, current, total):
        """Update progress display during data export"""
        if total > 0:
            percent = (current / total) * 100
            self.export_progress_label.setText(
                f"Extracting data: {current}/{total} samples ({percent:.1f}%)"
            )
            self.export_progress_label.setStyleSheet("color: #0066cc; font-weight: bold; padding: 5px;")
        else:
            self.export_progress_label.setText("No data extraction in progress")
            self.export_progress_label.setStyleSheet("color: #666; padding: 5px;")
                
    def update_extracted_data_table(self, flight_data):
        """Update the extracted data table with flash data.

        The table and the CSV export share the same structure:

        - ``device_timestamp``  (seconds, formatted to 2 decimal places)
        - ``altitude``          (raw, from the hardware)
        - ``acceleration``      (raw, from the hardware)
        - ``ax_ms2``, ``ay_ms2``, ``az_ms2`` (raw axes, when available)
        - ``altitude_filtered``     (filtered altitude used in plots)
        - ``acceleration_filtered`` (filtered/net acceleration used in plots)
        - ``velocity_filtered``     (filtered velocity used in plots)
        """
        if flight_data.empty:
            self.extracted_data_table.clear()
            self.extracted_data_table.setRowCount(0)
            self.extracted_data_table.setColumnCount(0)
            self.extracted_info_label.setText(
                "No data extracted yet. Use 'Extract Data from Flash' to load data."
            )
            return

        import numpy as _np

        df = flight_data.copy()

        # Ensure we have an integer millisecond device timestamp for
        # processing. The visible time column will always be expressed
        # in seconds.
        if "device_timestamp" not in df.columns:
            # Fall back to any known time-like column
            for alt_time_col in ("time_s", "t_ms", "timestamp_ms"):
                if alt_time_col in df.columns:
                    series = _np.asarray(df[alt_time_col], dtype=float)
                    if alt_time_col == "time_s":
                        df["device_timestamp"] = _np.round(series * 1000.0).astype(int)
                    else:
                        df["device_timestamp"] = series.astype(int)
                    break

        # Build processed series using the same helper that powers the
        # graphs so the filtered values match what the user sees.
        processed, _stats = self._build_processed_from_dataframe(df)
        has_processed = processed is not None and bool(processed.time)

        # Canonical column order for table and CSV
        base_columns = [
            "device_timestamp",  # shown as seconds with 2 decimals
            "altitude",
            "acceleration",
            "ax_ms2",
            "ay_ms2",
            "az_ms2",
            "altitude_filtered",
            "acceleration_filtered",
            "velocity_filtered",
        ]

        # Only keep columns that are actually available / computable
        visible_columns: list[str] = []
        for name in base_columns:
            if name in ("altitude_filtered", "acceleration_filtered", "velocity_filtered"):
                if has_processed:
                    visible_columns.append(name)
            else:
                if name == "device_timestamp" and "device_timestamp" in df.columns:
                    visible_columns.append(name)
                elif name in df.columns:
                    visible_columns.append(name)

        n_rows = len(df)
        self.extracted_data_table.clear()
        self.extracted_data_table.setRowCount(n_rows)
        self.extracted_data_table.setColumnCount(len(visible_columns))

        # Map internal column names to short, professional headers.
        header_labels: list[str] = []
        for name in visible_columns:
            if name == "device_timestamp":
                label = "Time (s)"
            elif name == "altitude":
                label = "Alt (m)"
            elif name == "acceleration":
                label = "Accel (m/s²)"
            elif name == "ax_ms2":
                label = "Ax (m/s²)"
            elif name == "ay_ms2":
                label = "Ay (m/s²)"
            elif name == "az_ms2":
                label = "Az (m/s²)"
            elif name == "altitude_filtered":
                label = "Alt filt (m)"
            elif name == "acceleration_filtered":
                label = "Accel filt (m/s²)"
            elif name == "velocity_filtered":
                label = "Vel filt (m/s)"
            else:
                label = name
            header_labels.append(label)

        self.extracted_data_table.setHorizontalHeaderLabels(header_labels)
        # Make header text bold for clarity
        header_font = self.extracted_data_table.horizontalHeader().font()
        header_font.setBold(True)
        self.extracted_data_table.horizontalHeader().setFont(header_font)

        self.extracted_info_label.setText(
            f"Displaying {n_rows} samples extracted from flash memory"
        )

        # Prepare processed arrays aligned with the DataFrame index
        alt_f = vel_f = acc_f = None
        if has_processed:
            alt_f = processed.altitude_smooth
            vel_f = processed.velocity_smooth
            acc_f = processed.acceleration_smooth

        # Populate cells row by row
        for row_idx, (_, data_row) in enumerate(df.iterrows()):
            # Visible time in seconds (2 decimals), always from
            # device_timestamp milliseconds when available.
            ts_ms = data_row.get("device_timestamp", row_idx)
            try:
                t_sec = float(ts_ms) / 1000.0
            except Exception:
                t_sec = float(row_idx)

            for col_idx, col_name in enumerate(visible_columns):
                if col_name == "device_timestamp":
                    text = f"{t_sec:.2f}"
                elif col_name == "altitude_filtered" and has_processed and alt_f is not None:
                    val = alt_f[row_idx] if row_idx < len(alt_f) else _np.nan
                    text = "" if _np.isnan(val) else f"{float(val):.3f}"
                elif col_name == "velocity_filtered" and has_processed and vel_f is not None:
                    val = vel_f[row_idx] if row_idx < len(vel_f) else _np.nan
                    text = "" if _np.isnan(val) else f"{float(val):.3f}"
                elif col_name == "acceleration_filtered" and has_processed and acc_f is not None:
                    val = acc_f[row_idx] if row_idx < len(acc_f) else _np.nan
                    text = "" if _np.isnan(val) else f"{float(val):.3f}"
                else:
                    value = data_row.get(col_name, "")
                    if value is None:
                        text = ""
                    else:
                        if isinstance(value, (int, float)):
                            if isinstance(value, int) or float(value).is_integer():
                                text = str(int(value))
                            else:
                                text = f"{float(value):.3f}"
                        else:
                            text = str(value)

                self.extracted_data_table.setItem(
                    row_idx, col_idx, QTableWidgetItem(text)
                )

        # Auto-switch to extracted data tab
        self.switch_to_extracted_tab()
                
    def update_data_table(self, flight_data):
        # This method is kept for compatibility but we use update_extracted_data_table now
        pass
            
    def detect_phase_from_data(self, data_row):
        if "altitude" not in data_row:
            return "Unknown"
            
        alt = data_row["altitude"]
        if alt < 10:
            return "Lift-off"
        elif alt < 100:
            return "Ascent"
        else:
            return "Coasting"
            
    def _build_processed_from_dataframe(self, flight_data):
        """Convert merged_app flight_data DataFrame into processed series & stats.

        Uses python_app.data_processor so graphs & metrics match the Python app.
        """
        if flight_data.empty:
            return None, None

        points: List[TelemetryDataPoint] = []
        for _, row in flight_data.iterrows():  # type: ignore[attr-defined]
            try:
                ts_ms = int(row.get("device_timestamp", 0))
                alt = float(row.get("altitude", 0.0))
                ax = float(row.get("ax_ms2", 0.0))
                ay = float(row.get("ay_ms2", 0.0))
                az = float(row.get("az_ms2", 0.0))
                ts = row.get("timestamp")
                if not isinstance(ts, datetime):
                    ts = datetime.now()
                pt = TelemetryDataPoint(
                    timestamp=ts,
                    device_timestamp=ts_ms,
                    altitude=alt,
                    ax=ax,
                    ay=ay,
                    az=az,
                )
                points.append(pt)
            except Exception:
                continue

        if not points:
            return None, None

        processed = process_flight_data(points, remove_gravity=self.remove_gravity)
        stats = calculate_flight_stats(processed)
        return processed, stats

    def update_visualization(self, flight_data, phases=None):
        """Update the plots using the modern processing pipeline."""
        # Cache for gravity toggle
        self._cached_flight_data = flight_data.copy() if not flight_data.empty else None
        self._cached_phases = phases

        if flight_data.empty:
            # Clear plots & stats
            for curve in (
                self.alt_alt_raw,
                self.alt_alt_smooth,
                self.vel_raw,
                self.vel_smooth,
                self.acc_raw,
                self.acc_smooth,
            ):
                curve.setData([])
            for key, lbl in self.stats_labels.items():
                if key == "sample_rate" and self.sample_rate_hz is not None:
                    lbl.setText(f"{self.sample_rate_hz} Hz")
                else:
                    lbl.setText("--")
            return

        processed, stats = self._build_processed_from_dataframe(flight_data)
        if processed is None or not processed.time:
            return

        # Subsample to keep things responsive
        n = len(processed.time)
        step = max(1, n // 500)
        idx = list(range(0, n, step))
        t = [processed.time[i] for i in idx]

        alt_rel = [processed.altitude_relative[i] for i in idx]
        alt_s = [processed.altitude_smooth[i] for i in idx]
        vel_raw = [processed.velocity_raw[i] for i in idx]
        vel_s = [processed.velocity_smooth[i] for i in idx]
        acc_raw = [processed.acceleration_net[i] for i in idx]
        acc_s = [processed.acceleration_smooth[i] for i in idx]

        # Update plots
        self.alt_alt_raw.setData(t, alt_rel)
        self.alt_alt_smooth.setData(t, alt_s)
        self.vel_raw.setData(t, vel_raw)
        self.vel_smooth.setData(t, vel_s)
        self.acc_raw.setData(t, acc_raw)
        self.acc_smooth.setData(t, acc_s)

        # Cache ranges for Set Origin
        if t:
            self._last_time = float(max(t))
        if alt_rel:
            self._last_alt_min = float(min(alt_rel))
            self._last_alt_max = float(max(alt_rel))

        # Update stats labels
        if stats is not None:
            self.stats_labels["max_alt"].setText(f"{stats.max_altitude:.1f} m")
            self.stats_labels["max_vel"].setText(f"{stats.max_velocity:.1f} m/s")
            self.stats_labels["max_acc"].setText(f"{stats.max_acceleration:.1f} m/s²")
            self.stats_labels["flight_dur"].setText(f"{stats.flight_duration:.1f} s")
            self.stats_labels["apogee_time"].setText(f"{stats.apogee_time:.1f} s")
            # Data points from processed data length
            self.stats_labels["data_points"].setText(str(len(processed.time)))
            if self.sample_rate_hz is not None:
                self.stats_labels["sample_rate"].setText(f"{self.sample_rate_hz} Hz")
            
    def switch_to_extracted_tab(self):
        """Switch to the extracted data tab"""
        self.tabs.setCurrentIndex(self.extracted_tab_index)
        
    def clear_visualization(self):
        """Clear all plots and reset cached ranges"""
        for curve in (
            self.alt_alt_raw,
            self.alt_alt_smooth,
            self.vel_raw,
            self.vel_smooth,
            self.acc_raw,
            self.acc_smooth,
        ):
            curve.setData([])
        self._last_time = None
        self._last_alt_min = None
        self._last_alt_max = None
        for key, lbl in self.stats_labels.items():
            if key == "sample_rate" and self.sample_rate_hz is not None:
                lbl.setText(f"{self.sample_rate_hz} Hz")
            else:
                lbl.setText("--")

    def on_gravity_toggled(self, state):
        """Handle gravity toggle: apply/remove gravity in real time."""
        # When checked, show total acceleration (with gravity).
        # When unchecked, show net acceleration (gravity removed).
        if state:  # checked
            self.remove_gravity = False
            self.gravity_toggle.setText("Total accel (with gravity)")
        else:
            self.remove_gravity = True
            self.gravity_toggle.setText("Net accel (gravity removed)")

        # Recompute plots immediately using cached data
        if self._cached_flight_data is not None:
            self.update_visualization(self._cached_flight_data, self._cached_phases)

    def eventFilter(self, obj, event):
        # No special handling needed now; keep for future extensions
        return False
        
    def on_set_origin(self):
        """Reset/align view to origin and altitude extents"""
        # Provide visual feedback when invoked from the button
        sender = self.sender()
        if isinstance(sender, QPushButton):
            self._flash_button(sender)
        try:
            if self._last_time is not None and self._last_alt_min is not None and self._last_alt_max is not None:
                self.alt_plot.setXRange(0, self._last_time, padding=0.05)
                self.alt_plot.setYRange(self._last_alt_min, self._last_alt_max, padding=0.1)
            else:
                self.alt_plot.enableAutoRange(x=True, y=True)
        except Exception:
            pass
        
    def on_save_graph(self):
        """Save graphs as images with multiple options (alt/vel/acc/all/combined)."""
        sender = self.sender()
        if isinstance(sender, QPushButton):
            self._flash_button(sender)
        from PyQt6.QtWidgets import QInputDialog
        from datetime import datetime
        options = [
            "Altitude only",
            "Velocity only",
            "Acceleration only",
            "All three (separate files)",
            "Combined (single image)",
        ]
        choice, ok = QInputDialog.getItem(self, "Save Graphs", "Select export mode:", options, 0, False)
        if not ok or not choice:
            return

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_name = f"flight_plots_{ts}.png"
        base_filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Graph(s)",
            default_name,
            "PNG Files (*.png);;JPEG Files (*.jpg);;All Files (*)",
        )
        if not base_filename:
            return

        from pyqtgraph.exporters import ImageExporter
        import os

        def _export_widget(widget, filename):
            try:
                exporter = ImageExporter(widget.plotItem)
                exporter.parameters()['width'] = max(800, widget.width())
                exporter.export(filename)
            except Exception:
                try:
                    pix = widget.grab()
                    pix.save(filename)
                except Exception:
                    pass

        root, ext = os.path.splitext(base_filename)
        if not ext:
            ext = ".png"

        if choice == "Altitude only":
            _export_widget(self.alt_plot, root + ext)
        elif choice == "Velocity only":
            _export_widget(self.vel_plot, root + ext)
        elif choice == "Acceleration only":
            _export_widget(self.acc_plot, root + ext)
        elif choice == "All three (separate files)":
            _export_widget(self.alt_plot, root + "_alt" + ext)
            _export_widget(self.vel_plot, root + "_vel" + ext)
            _export_widget(self.acc_plot, root + "_acc" + ext)
        else:  # Combined (single image)
            # Grab the entire visualization group (stats + all plots)
            try:
                container = self.alt_plot.parentWidget()
                while container and container is not self:
                    if isinstance(container, QGroupBox):
                        break
                    container = container.parentWidget()
                if container is None:
                    container = self
                pix = container.grab()
                pix.save(root + ext)
            except Exception:
                # Fallback: stack altitude and velocity only
                _export_widget(self.alt_plot, root + ext)

    def _on_mouse_moved(self, pos):
        """(Optional) placeholder for future interactive tools."""
        return

    def update_sample_rate(self, rate_hz: int) -> None:
        """Store latest sample-rate info for display in stats bar."""
        self.sample_rate_hz = rate_hz
        if "sample_rate" in self.stats_labels and rate_hz is not None:
            self.stats_labels["sample_rate"].setText(f"{rate_hz} Hz")

    def _on_clear_logs_clicked(self) -> None:
        self._flash_button(self.btn_clear_logs, "background-color: #ef4444; color: white;")
        self.clear_logs_requested.emit()

    def _on_save_logs_clicked(self) -> None:
        self._flash_button(self.btn_save_logs)
        self.save_logs_requested.emit()

    def _on_clear_clicked(self) -> None:
        self._flash_button(self.btn_clear, "background-color: #f97316; color: white;")
        self.clear_requested.emit()
