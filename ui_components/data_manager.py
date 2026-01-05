# ui_components/data_manager.py - COMPLETE REPLACEMENT
from PyQt6.QtCore import QObject, pyqtSignal
from data_processor import DataProcessor

class DataManager(QObject):
    data_updated = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.data_processor = DataProcessor()
        
    def process_incoming_data(self, raw_data):
        """Process incoming data - FIXED VERSION"""
        processed_data = self.data_processor.process_raw_data(raw_data)
        if processed_data:
            self.data_processor.add_data_point(processed_data)
            # Emit signal for ALL data types, not just telemetry
            self.data_updated.emit()
            
    def get_flight_data(self):
        return self.data_processor.get_flight_data()
        
    def set_flight_data(self, df):
        """Directly set flight_data for cases where we parse CSV externally (BLE dump)."""
        # Ensure a human-readable timestamp column exists for the table.
        try:
            from datetime import datetime, timedelta
            if "device_timestamp" in df.columns and "timestamp" not in df.columns:
                t0 = datetime.now() - timedelta(milliseconds=int(df["device_timestamp"].iloc[-1] or 0))
                df["timestamp"] = [t0 + timedelta(milliseconds=int(ms)) for ms in df["device_timestamp"]]
        except Exception:
            pass
        self.data_processor.flight_data = df
        # Mirror into current_export_data so stats/exports work as usual
        try:
            self.data_processor.current_export_data = df.to_dict("records")
        except Exception:  # noqa: BLE001
            pass
        self.data_updated.emit()
        
    def get_statistics(self):
        return self.data_processor.calculate_statistics()
        
    def get_flight_phases(self):
        return self.data_processor.detect_flight_phases()
        
    def get_memory_status(self):
        return self.data_processor.get_memory_status()
        
    def clear_data(self):
        self.data_processor.clear_data()
        self.data_updated.emit()
        
    def export_to_csv(self, filename):
        return self.data_processor.export_to_csv(filename)