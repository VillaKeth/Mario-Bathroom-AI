@echo off
REM ============================================================
REM  Start ONLY the on-screen character window (the "client").
REM  Use this if the server is already running in another window.
REM  Most people should just use start.bat, which launches BOTH.
REM ============================================================
cd /d "%~dp0"

if not exist "%~dp0venv\Scripts\python.exe" (
    echo [ERROR] Setup has not been run yet.
    echo         Double-click setup.bat first, then try again.
    pause
    exit /b 1
)

call "%~dp0venv\Scripts\activate.bat"
echo Opening the character window...
python "%~dp0client\main.py"
pause
