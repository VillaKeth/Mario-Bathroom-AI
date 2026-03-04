@echo off
echo ===================================
echo   Mario AI Server - Starting Up!
echo ===================================
echo.

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

REM Install dependencies
echo Installing server dependencies...
cd /d "%~dp0server"
pip install -r requirements.txt --quiet

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
echo ===================================
echo.
python main.py
pause
