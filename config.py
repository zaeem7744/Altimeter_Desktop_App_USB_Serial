# config.py - UPDATED
# BLE Configuration (matches Altimeter_Bluetooth_Firmware)
# Firmware uses: service 19B10000-..., RX (write) 19B10001-..., TX (notify) 19B10002-...
DEVICE_NAME = "Altimeter"
SERVICE_UUID = "19B10000-E8F2-537E-4F6C-D104768A1214"
# TX / notify characteristic used for streaming CSV lines back to the host
DATA_UUID = "19B10002-E8F2-537E-4F6C-D104768A1214"
# RX / write characteristic used for sending single-character commands (e.g. 'D')
COMMAND_UUID = "19B10001-E8F2-537E-4F6C-D104768A1214"

# Connection settings
SCAN_TIMEOUT = 5
CONNECTION_TIMEOUT = 5
RECONNECT_DELAY = 2

# Data processing
MAX_DATA_POINTS = 1000
SAMPLING_RATE = 10  # Hz

# Flash storage configuration (matches Arduino)
TOTAL_SAMPLES = 24576  # 96 sectors * 256 samples
SAMPLE_RATE_HZ = 50

# Commands for BLE bridge
# Altimeter_Bluetooth_Firmware only handles 'D' over BLE (flash dump).
# Other commands (A/B/S/C) are handled via serial or button, not BLE.
CMD_STATUS = "S"          # currently not handled over BLE, kept for compatibility
CMD_MEMORY_STATUS = "S"   # ditto; memory info is derived from dump size
CMD_EXTRACT_DATA = "D"    # trigger flash dump over BLE
CMD_CLEAR_MEMORY = "C"    # clear via serial/button; sending over BLE is a no-op

# Flight phases colors
PHASE_COLORS = {
    "Lift-off": "#00FF00",      # Green
    "Ascent": "#00FF00",        # Green  
    "Peak": "#FFFF00",          # Yellow
    "Descent": "#FF0000",       # Red
    "Ejection": "#FFA500",      # Orange
    "Touchdown": "#800080"      # Purple
}