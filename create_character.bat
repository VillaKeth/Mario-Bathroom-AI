@echo off
echo Starting Character Creator Wizard...
echo.

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Run setup.bat first to install dependencies.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
echo Opening Character Creator in your browser...
start http://localhost:8766
python -m character_creator.server
pause
