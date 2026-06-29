@echo off
REM One-click public Cloudflare tunnel for the party bot.
REM Prints the ready-to-share chat URL (token/PIN auto-filled from config.json)
REM instead of making you dig the random URL out of cloudflared's logs.
REM No Cloudflare account needed. Close this window to drop the tunnel.
cd /d "%~dp0"
if exist "%~dp0venv\Scripts\activate.bat" call "%~dp0venv\Scripts\activate.bat"
python "%~dp0scripts\run_tunnel.py"
pause
