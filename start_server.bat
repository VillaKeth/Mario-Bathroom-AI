@echo off
echo ===================================
echo   Mario AI Server - Starting Up!
echo ===================================
echo.

REM Check config.json exists
if not exist "%~dp0config.json" (
    echo.
    echo [ERROR] config.json not found!
    echo         Run setup.bat first, or copy config.example.json to config.json
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment (created by setup.bat)
if exist "%~dp0venv\Scripts\activate.bat" (
    call "%~dp0venv\Scripts\activate.bat"
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

REM Check Ollama
ollama --version >nul 2>&1
if errorlevel 1 (
    echo WARNING: Ollama not found! Install from https://ollama.ai
    echo Mario won't be able to think without it!
    echo.
)

REM Install/update dependencies
echo Checking server dependencies...
pip install -r "%~dp0server\requirements.txt" --quiet 2>nul

echo.
echo Checking Ollama model...
ollama list 2>nul | findstr "llama3" >nul
if errorlevel 1 (
    echo Pulling llama3 model (this may take a while)...
    ollama pull llama3
)

echo.
echo ===================================
echo   Starting Mario AI Server
echo   Listening on 0.0.0.0:8765
echo   Health check: http://localhost:8765/health
echo ===================================
echo.
cd /d "%~dp0server"
python main.py
pause
