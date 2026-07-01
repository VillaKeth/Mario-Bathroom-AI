@echo off
REM ============================================================
REM  Start ONLY the screen-watching process (Rudi watches your game).
REM  Requires start_server.bat (and usually start_client.bat) already running.
REM  Closing this window stops watching AND unloads the llava vision model.
REM ============================================================
cd /d "%~dp0"

if not exist "%~dp0venv\Scripts\python.exe" (
    echo [ERROR] Setup has not been run yet. Run setup.bat first.
    pause
    exit /b 1
)

call "%~dp0venv\Scripts\activate.bat"
echo Starting screen watcher... (close this window to stop and free the vision model)
python "%~dp0server\screen_watcher.py"
pause
