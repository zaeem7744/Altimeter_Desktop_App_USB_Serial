# :mountain_snow: Altimeter -- Desktop App (USB Serial)

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![PyQt6](https://img.shields.io/badge/PyQt6-41CD52?style=flat-square&logo=qt&logoColor=white)
![USB](https://img.shields.io/badge/USB_Serial-333333?style=flat-square)

A **PyQt6 desktop application** for real-time telemetry visualization from the [Altimeter device](https://github.com/zaeem7744/Altimeter-Firmware-and-Design) via **USB Serial (COM port)** connection. Features live data plotting, flight phase detection, and includes a Windows executable build system.

> See also: [Altimeter Firmware & PCB](https://github.com/zaeem7744/Altimeter-Firmware-and-Design) | [Desktop App (Bluetooth)](https://github.com/zaeem7744/Altimeter_Desktop_App_Bluetooth)

---

## :wrench: Features

- **USB Serial Communication** -- Connects to Altimeter via COM port using `pyserial`
- **Real-Time Data Visualization** -- Live altitude/pressure plotting with `pyqtgraph`
- **Flight Phase Detection** -- Automatic detection and labeling of flight phases
- **Memory Status Monitoring** -- Reads device flash memory usage and status
- **Data Export** -- Save telemetry data to CSV with `pandas`
- **Windows Executable** -- Pre-built `.exe` via PyInstaller (see `dist/` and `windows_build/`)
- **Modular UI Architecture** -- Separated control panel, data manager, and data panel components

---

## :file_folder: Project Structure

```
Altimeter_Desktop_App_USB_Serial/
|-- main.py               # Application entry point
|-- ui_dashboard.py        # Main dashboard window
|-- config.py              # Serial port settings, baud rate, thresholds
|-- data_processor.py      # Telemetry data parsing and processing
|-- ui_components/
|   |-- ble_manager.py     # Serial port connection manager
|   |-- control_panel.py   # User controls (connect, start/stop, export)
|   |-- data_manager.py    # Data storage, CSV export, logging
|   +-- data_panel.py      # Real-time data visualization widgets
|-- dist/                  # Pre-built Windows executable
+-- windows_build/
    |-- build_exe.bat      # PyInstaller build script
    +-- README.txt         # Build instructions
```

---

## :hammer_and_wrench: Tech Stack

| Component | Technology |
|-----------|-----------|
| **GUI Framework** | PyQt6 |
| **Serial Library** | pyserial |
| **Data Visualization** | pyqtgraph (real-time plotting) |
| **Data Processing** | pandas, numpy |
| **Build System** | PyInstaller (Windows .exe) |

---

## :rocket: Quick Start

```bash
# Install dependencies
pip install PyQt6 pandas numpy pyqtgraph pyserial

# Run the application
python main.py
```

Or use the pre-built Windows executable from the `dist/` folder.

---

## :bust_in_silhouette: Author

**Muhammad Zaeem Sarfraz** -- Electronics & IoT Hardware Engineer

- :link: [LinkedIn](https://www.linkedin.com/in/zaeemsarfraz7744/)
- :email: Zaeem.7744@gmail.com
- :earth_africa: Vaasa, Finland
