@echo off
echo ===================================
echo   Mario AI Client - Let's-a Go!
echo ===================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found! Install Python 3.10+
    pause
    exit /b 1
)

REM Install dependencies
echo Installing client dependencies...
cd /d "%~dp0client"
pip install -r requirements.txt --quiet

echo.

REM Get server IP
if "%1"=="" (
    set /p SERVER_IP="Enter server IP address (or 'localhost' for testing): "
) else (
    set SERVER_IP=%1
)

echo.
echo ===================================
echo   Connecting to ws://%SERVER_IP%:8765/ws
echo   Press ESC or close window to quit
echo ===================================
echo.
python main.py --server ws://%SERVER_IP%:8765/ws
pause
