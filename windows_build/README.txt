Altimeter Flight Data Viewer - Windows EXE Build
===============================================

This folder contains helper files to build a standalone Windows .exe
for the Altimeter Flight Data Viewer (PyQt6 desktop app).

Prerequisites
-------------
1. Python 3.x installed.
2. All project dependencies installed in the same environment:
   pip install -r requirements.txt
   (or manually: PyQt6, pandas, numpy, pyqtgraph, qasync, pyserial)
3. PyInstaller installed:
   pip install pyinstaller

How to build the .exe
---------------------
1. Open a regular Command Prompt (cmd.exe), not PowerShell.
2. Change directory to the project root, for example:

   cd D:\Projects\Altimeter_Desktop_App_USB_Serial

3. Run the build script:

   windows_build\build_exe.bat

4. If the build succeeds, the executable will be created at:

   dist\AltimeterFlightDataViewer.exe

You can copy that .exe (plus any needed DLLs if you later switch away
from --onefile) to another Windows machine that does not have Python
installed.
