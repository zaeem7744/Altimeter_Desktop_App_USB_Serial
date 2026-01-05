# main.py
import sys
import asyncio
import os
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
import qasync

# Add current directory to path to import local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ui_dashboard import TelemetryDashboard

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('altimeter_flight_data.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

class AltimeterFlightDataApp:
    def __init__(self):
        self.app = None
        self.dashboard = None
        self.loop = None
        
    def setup_application(self):
        """Setup the Qt application and event loop"""
        print("🚀 Starting Altimeter Flight Data Viewer - USB Serial Dashboard...")
        
        # Create Qt Application
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("Altimeter Flight Data Viewer")
        self.app.setApplicationVersion("1.0.0")
        
        try:
            # Set up asyncio event loop for Qt
            self.loop = qasync.QEventLoop(self.app)
            asyncio.set_event_loop(self.loop)
            print("✅ Asyncio event loop configured")
        except Exception as e:
            print(f"⚠️  Asyncio setup warning: {e}")
            print("📱 Running in synchronous mode")
            self.loop = None
        
        # Create and show main window
        self.dashboard = TelemetryDashboard()
        self.dashboard.show()
        
        # Setup cleanup on exit
        self.app.aboutToQuit.connect(self.cleanup)
        
        print("✅ Dashboard initialized successfully!")
        print("=" * 60)
        print("🎯 System Ready for Operation")
        print("📊 Features Available:")
        print("   • USB serial device connection & management")
        print("   • Real-time flight data visualization")
        print("   • Flash memory status & management")
        print("   • Data extraction to CSV from the Altimeter")
        print("   • Offline CSV import and analysis")
        print("   • Live communication logging")
        print("=" * 60)
        
        return self.app.exec()
    
    def cleanup(self):
        """Cleanup resources before exit"""
        print("\n🔌 Shutting down Altimeter Flight Data Viewer...")
        if self.dashboard and hasattr(self.dashboard, 'ble_client'):
            try:
                # Ensure proper disconnection
                if self.loop and self.loop.is_running():
                    async def disconnect():
                        await self.dashboard.ble_client.disconnect()
                    
                    # Run disconnect coroutine
                    if self.dashboard.is_connected:
                        asyncio.ensure_future(disconnect())
            except Exception as e:
                print(f"⚠️  Cleanup warning: {e}")
        
        print("👋 Goodbye! Altimeter Flight Data Viewer shut down successfully.")
    
    def run(self):
        """Main application entry point"""
        try:
            if self.loop:
                # Run with asyncio event loop
                with self.loop:
                    return self.loop.run_until_complete(self._async_run())
            else:
                # Run without asyncio
                return self.setup_application()
        except KeyboardInterrupt:
            print("\n🛑 Application interrupted by user")
            return 0
        except Exception as e:
            print(f"💥 Critical error: {e}")
            logging.exception("Application crash")
            return 1
    
    async def _async_run(self):
        """Async version of run method"""
        try:
            return self.setup_application()
        except Exception as e:
            print(f"💥 Async error: {e}")
            return 1

def check_dependencies():
    """Check if all required dependencies are available.
    In a frozen (packaged) app, skip interactive checks to avoid stdin issues.
    """
    # If running as a packaged executable, assume bundled deps and skip checks
    if getattr(sys, 'frozen', False):
        return True

    required_packages = {
        'PyQt6': 'PyQt6',
        'pandas': 'pandas', 
        'numpy': 'numpy',
        'pyqtgraph': 'pyqtgraph',
        'qasync': 'qasync',
        'pyserial': 'serial'
    }
    
    missing = []
    for package, import_name in required_packages.items():
        try:
            if package == 'pyserial':
                __import__('serial')
            else:
                __import__(import_name)
            print(f"✅ {package} - OK")
        except ImportError:
            missing.append(package)
            print(f"❌ {package} - MISSING")
    
    if missing:
        print(f"\n⚠️  Missing packages: {', '.join(missing)}")
        print("💡 Install with: pip install " + " ".join(missing))
        return False
    return True

def main():
    """Main application entry point"""
    print("🔍 Checking dependencies...")
    
    if not check_dependencies():
        print("\n❌ Some dependencies are missing. Please install them first.")
        response = input("🚀 Attempt to install missing packages? (y/n): ")
        if response.lower() == 'y':
            try:
                import subprocess
                subprocess.check_call([sys.executable, "-m", "pip", "install", 
                                      "PyQt6", "pandas", "numpy", 
                                      "pyqtgraph", "qasync", "pyserial"])
                print("✅ Dependencies installed successfully!")
            except Exception as e:
                print(f"❌ Failed to install dependencies: {e}")
                return 1
        else:
            return 1
    
    # Create and run application
    app = AltimeterFlightDataApp()
    return app.run()

if __name__ == "__main__":
    # Set working directory to script location
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Run the application
    exit_code = main()
    
    # In a GUI packaged app, do not wait for stdin (no console attached)
    sys.exit(exit_code)
