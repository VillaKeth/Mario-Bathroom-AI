@echo off
REM ============================================================
REM  One-click launcher used by the Character Creator wizard's
REM  "Start Server" button. Starts the AI server in its own
REM  window, waits for it to come up, then opens the pygame
REM  client so the active character is immediately on screen.
REM ============================================================
cd /d "%~dp0"

echo Launching AI server window...
start "Mario AI Server" cmd /k "%~dp0start_server.bat"

echo Waiting for server health on http://localhost:8765 ...
:waitloop
timeout /t 3 >nul
curl -s -o nul http://localhost:8765/health
if errorlevel 1 goto waitloop

echo Server is up. Launching pygame client...
if exist "%~dp0venv\Scripts\activate.bat" call "%~dp0venv\Scripts\activate.bat"
python "%~dp0client\main.py"
