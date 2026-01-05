# ui_components/control_panel.py - UPDATED
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QComboBox, QGroupBox, QProgressBar, QStyle)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont

class ControlPanel(QWidget):
    # Signals
    scan_requested = pyqtSignal()
    connect_requested = pyqtSignal(str)
    disconnect_requested = pyqtSignal()
    memory_check_requested = pyqtSignal()
    memory_erase_requested = pyqtSignal()
    generate_test_data_requested = pyqtSignal()
    extract_data_requested = pyqtSignal()
    export_requested = pyqtSignal()
    view_data_requested = pyqtSignal()
    sample_rate_apply_requested = pyqtSignal(int)
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout = layout
        
        # Connection Status
        status_group = self.create_status_group()
        layout.addWidget(status_group)
        
        # Device Management
        device_group = self.create_device_group()
        layout.addWidget(device_group)
        
        # Memory Management
        memory_group = self.create_memory_group()
        layout.addWidget(memory_group)
        
        # Data Controls
        data_group = self.create_data_group()
        layout.addWidget(data_group)
        
        # Sample Rate / Next Flight Settings
        stats_group = self.create_stats_group()
        layout.addWidget(stats_group)
        
        # Placeholder: logs group will be inserted just above this stretch
        layout.addStretch()
        
    def create_status_group(self):
        group = QGroupBox("Connection Status")
        layout = QVBoxLayout(group)
        
        self.connection_status = QLabel("Disconnected")
        self.connection_status.setStyleSheet("font-size: 16px; font-weight: bold; color: red;")
        layout.addWidget(self.connection_status)
        
        self.device_info = QLabel("No device connected")
        layout.addWidget(self.device_info)
        
        return group
        
    def create_device_group(self):
        group = QGroupBox("Device Management")
        layout = QVBoxLayout(group)
        
        self.device_combo = QComboBox()
        self.device_combo.setPlaceholderText("Select a device...")
        layout.addWidget(self.device_combo)
        
        # Device control buttons in a single horizontal row
        btn_row = QHBoxLayout()
        
        self.btn_scan = QPushButton("Scan")
        self.btn_scan.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.btn_scan.clicked.connect(self.scan_requested.emit)
        btn_row.addWidget(self.btn_scan)
        
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogYesButton))
        self.btn_connect.clicked.connect(self._on_connect_clicked)
        btn_row.addWidget(self.btn_connect)
        
        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton))
        self.btn_disconnect.clicked.connect(self.disconnect_requested.emit)
        btn_row.addWidget(self.btn_disconnect)
        
        btn_row.addStretch()
        layout.addLayout(btn_row)
        
        return group
        
    def create_memory_group(self):
        group = QGroupBox("Flash Memory Status")
        layout = QVBoxLayout(group)
        
        self.memory_status = QLabel("Memory: Not checked")
        self.memory_status.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.memory_status)
        
        self.memory_progress = QProgressBar()
        self.memory_progress.setMaximum(100)
        layout.addWidget(self.memory_progress)
        
        info_layout = QHBoxLayout()
        info_layout.addWidget(QLabel("Capacity:"))
        self.capacity_label = QLabel(f"{24576} samples")
        info_layout.addWidget(self.capacity_label)
        info_layout.addStretch()
        layout.addLayout(info_layout)
        
        btn_layout = QHBoxLayout()
        btn_check_memory = QPushButton("Check Memory")
        btn_check_memory.clicked.connect(self.memory_check_requested.emit)
        btn_layout.addWidget(btn_check_memory)
        
        btn_erase_memory = QPushButton("Erase Memory")
        btn_erase_memory.clicked.connect(self.memory_erase_requested.emit)
        btn_erase_memory.setStyleSheet("background-color: #ff4444; color: white;")
        btn_layout.addWidget(btn_erase_memory)
        
        layout.addLayout(btn_layout)
        
        return group
        
    def create_data_group(self):
        group = QGroupBox("Flash Data Management")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)
        
        # Three primary actions in a single horizontal row
        btn_row = QHBoxLayout()

        btn_extract_data = QPushButton("Extract Data from Flash")
        btn_extract_data.clicked.connect(self.extract_data_requested.emit)
        btn_extract_data.setStyleSheet(
            "background-color: #2563eb;"
            "color: white;"
            "font-weight: bold;"
            "padding: 6px 10px;"
            "border-radius: 6px;"
        )
        btn_row.addWidget(btn_extract_data)

        btn_export_csv = QPushButton("Export to CSV")
        btn_export_csv.clicked.connect(self.export_requested.emit)
        btn_row.addWidget(btn_export_csv)
        
        btn_view_data = QPushButton("View All Data")
        btn_view_data.clicked.connect(self.view_data_requested.emit)
        btn_row.addWidget(btn_view_data)

        layout.addLayout(btn_row)

        # Extraction progress bar (graphical) below the row of actions
        self.extract_progress = QProgressBar()
        self.extract_progress.setRange(0, 100)
        self.extract_progress.setValue(0)
        self.extract_progress.setFormat("No extraction in progress")
        self.extract_progress.setTextVisible(True)
        self.extract_progress.setStyleSheet(
            "QProgressBar {"
            "  border: 1px solid #d0d7de;"
            "  border-radius: 6px;"
            "  background-color: #f3f4f6;"
            "  text-align: center;"
            "  padding: 2px;"
            "  color: #000000;"
            "}"
            "QProgressBar::chunk {"
            "  background-color: #2563eb;"
            "  border-radius: 6px;"
            "}"
        )
        layout.addWidget(self.extract_progress)
        
        return group
        
    def create_stats_group(self):
        group = QGroupBox("Next Flight Sample Rate")
        layout = QVBoxLayout(group)

        # Sample rate display and selector
        self.sample_rate_label = QLabel("Sample rate for next flight: -- Hz")
        self.sample_rate_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.sample_rate_label)

        rate_row = QHBoxLayout()
        rate_row.addWidget(QLabel("Select sample rate:"))
        from PyQt6.QtWidgets import QComboBox  # local import to avoid circulars
        self.sample_rate_combo = QComboBox()
        self.sample_rate_combo.addItems(["10 Hz", "25 Hz", "50 Hz"])
        rate_row.addWidget(self.sample_rate_combo)
        rate_row.addStretch()
        layout.addLayout(rate_row)

        # Apply button - only sends to hardware when clicked
        self.sample_rate_apply_btn = QPushButton("Set sample rate for next flight")
        self.sample_rate_apply_btn.setStyleSheet("background-color: #2563eb; color: white; padding: 4px 8px; border-radius: 4px;")
        self.sample_rate_apply_btn.clicked.connect(self._on_sample_rate_apply_clicked)
        layout.addWidget(self.sample_rate_apply_btn)

        # Demo explanatory text (you can edit later with real capacity numbers)
        demo = QLabel(
            "<ul>"
            "<li>10 Hz – lower resolution, longer recording time</li>"
            "<li>25 Hz – balanced detail vs. memory usage</li>"
            "<li>50 Hz – highest detail, shortest recording window</li>"
            "</ul>"
        )
        demo.setStyleSheet("color: #4b5563; font-size: 11px;")
        demo.setWordWrap(True)
        layout.addWidget(demo)

        return group
        
        
    def _on_connect_clicked(self):
        if self.device_combo.currentData():
            address = self.device_combo.currentData()
            self.connect_requested.emit(address)
            
    def update_connection_status(self, status, message):
        if status == "connected":
            self.connection_status.setText("Connected")
            self.connection_status.setStyleSheet("color: green; font-size: 16px; font-weight: bold;")
            self.device_info.setText(message)
        elif status == "disconnected":
            self.connection_status.setText("Disconnected")
            self.connection_status.setStyleSheet("color: red; font-size: 16px; font-weight: bold;")
            self.device_info.setText("No device connected")
        elif status == "error":
            self.connection_status.setText("Error")
            self.connection_status.setStyleSheet("color: orange; font-size: 16px; font-weight: bold;")
            
    def update_devices_list(self, devices):
        self.device_combo.clear()
        if not devices:
            self.device_combo.addItem("No devices found")
            return
            
        for device in devices:
            display_text = f"{device['name']} ({device['address']})"
            if device['rssi'] != 'N/A':
                display_text += f" - RSSI: {device['rssi']}"
            self.device_combo.addItem(display_text, device['address'])
            
    def update_memory_display(self, memory_status):
        """Update memory display with flash storage info"""
        total_samples = memory_status.get("total_samples", 0)
        usage_percent = memory_status.get("usage_percent", 0)
        max_capacity = memory_status.get("max_capacity", 24576)
        is_full = memory_status.get("is_full", False)

        status_text = f"{total_samples} / {max_capacity} samples"
        if is_full:
            status_text += "  (FULL)"

        self.memory_status.setText(status_text)
        self.memory_progress.setValue(usage_percent)

        # Update capacity label
        self.capacity_label.setText(f"{max_capacity} samples")
        
    def update_statistics(self, stats):
        """Left panel no longer shows numeric stats; handled above the graphs."""
        pass

    def _get_selected_sample_rate(self) -> int:
        """Return current selection from the sample rate combo as an int Hz."""
        if not hasattr(self, 'sample_rate_combo'):
            return 50
        text = self.sample_rate_combo.currentText()
        if text.startswith("10"):
            return 10
        elif text.startswith("25"):
            return 25
        else:
            return 50

    def _on_sample_rate_apply_clicked(self):
        rate = self._get_selected_sample_rate()
        self.sample_rate_apply_requested.emit(rate)

    def update_sample_rate_display(self, rate_hz):
        """Update label and combo to reflect device-reported sample rate."""
        self.sample_rate_label.setText(f"Sample rate: {rate_hz} Hz")
        if hasattr(self, 'sample_rate_combo'):
            mapping = {10: 0, 25: 1, 50: 2}
            idx = mapping.get(rate_hz)
            if idx is not None:
                blocked = self.sample_rate_combo.blockSignals(True)
                self.sample_rate_combo.setCurrentIndex(idx)
                self.sample_rate_combo.blockSignals(blocked)

    def update_extract_progress(self, current, total):
        """Update the graphical progress bar for data extraction."""
        if total > 0 and current >= 0:
            percent = int((current / total) * 100)
            self.extract_progress.setValue(percent)
            self.extract_progress.setFormat(f"Extracting: {percent}%")
        else:
            self.extract_progress.setValue(0)
            self.extract_progress.setFormat("No extraction in progress")

    def add_logs_group(self, logs_group):
        """Insert the live communication logs group below the sample rate settings."""
        if not hasattr(self, "main_layout"):
            return
        # Insert just before the final stretch item so logs appear near the bottom
        index = max(0, self.main_layout.count() - 1)
        self.main_layout.insertWidget(index, logs_group)
