@echo off
REM Build a Windows .exe for the Altimeter Flight Data Viewer (PyQt6 app)
REM This script should be run from a normal Command Prompt (cmd.exe), not PowerShell.

setlocal
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%.."

REM Check that main.py exists
if not exist "main.py" (
    echo main.py not found in project root. Aborting.
    pause
    exit /b 1
)

REM Run PyInstaller to create a single-file, windowed executable.
REM Output will appear in the dist/AltimeterFlightDataViewer.exe path.

pyinstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name AltimeterFlightDataViewer ^
  main.py

if %errorlevel% neq 0 (
    echo.
    echo PyInstaller build failed. Make sure PyInstaller is installed with:
    echo    pip install pyinstaller
    echo and that you are using the same Python environment where the app runs.
    pause
    exit /b %errorlevel%
)

echo.
echo Build completed successfully.
echo You should now have: dist\AltimeterFlightDataViewer.exe
pause
