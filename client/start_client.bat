@echo off
echo ===================================
echo   Mario AI Client - Let's-a Go!
echo ===================================
echo.
REM Activate virtual environment (created by setup.bat)
if exist "%~dp0..\venv\Scripts\activate.bat" (
    call "%~dp0..\venv\Scripts\activate.bat"
    echo [OK] Virtual environment activated
) else (
    echo [WARNING] No virtual environment found at venv\
    echo          Run setup.bat first for best results.
    echo          Falling back to system Python...
    echo.
)
REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found! Install Python 3.10+
    pause
    exit /b 1
)
REM Install/update dependencies
echo Checking client dependencies...
pip install -r "%~dp0requirements.txt" --quiet
echo.
REM Get server IP (default: localhost for same-machine setup)
set SERVER_IP=localhost
if not "%~1"=="" set SERVER_IP=%~1
echo Using server: %SERVER_IP%
echo.
echo ===================================
echo   Connecting to ws://%SERVER_IP%:8765/ws
echo   Press ESC or close window to quit
echo ===================================
echo.
cd /d "%~dp0"
python main.py --server ws://%SERVER_IP%:8765/ws
pause