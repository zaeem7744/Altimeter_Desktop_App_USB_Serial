# config.py - USB serial configuration for Altimeter Flight Data Viewer

# Human-friendly name advertised by the device (used for filtering ports)
DEVICE_NAME = "Altimeter"

# Serial port settings (must match firmware)
BAUD_RATE = 115200
SCAN_TIMEOUT = 5          # seconds to scan for serial ports
RECONNECT_DELAY = 2       # seconds between reconnect attempts

# Flash storage configuration (matches Arduino firmware FlashStorage.h)
# 96 sectors * 180 samples per sector = 17,280 samples total.
TOTAL_SAMPLES = 17280
SAMPLE_RATE_HZ = 50

# Commands sent over serial
CMD_STATUS = "S"            # request status / config summary
CMD_MEMORY_STATUS = "S"     # query flash memory usage
CMD_EXTRACT_DATA = "D"      # stream full flash dump as CSV
CMD_CLEAR_MEMORY = "C"      # erase flash memory
CMD_START_LOGGING = "A"     # (optional) start logging for next flight
CMD_STOP_LOGGING = "B"      # (optional) stop logging
CMD_SET_SAMPLE_RATE_PREFIX = "R"  # e.g. R10 / R25 / R50

# Flight phases colors (used in visualization)
PHASE_COLORS = {
    "Lift-off": "#00FF00",      # Green
    "Ascent": "#00FF00",        # Green  
    "Peak": "#FFFF00",          # Yellow
    "Descent": "#FF0000",       # Red
    "Ejection": "#FFA500",      # Orange
    "Touchdown": "#800080"      # Purple
}
