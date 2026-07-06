@echo off
REM PERMANENT public ngrok tunnel for the party bot.
REM Uses your reserved static domain (config.json -> mirror.ngrok_domain) so the
REM share link NEVER changes. Prints the ready-to-share chat URL.
REM Claim a free domain once at https://dashboard.ngrok.com/domains
REM (Cloudflare random-URL version is start_tunnel.bat.)
REM Close this window to drop the tunnel.
cd /d "%~dp0"
if exist "%~dp0venv\Scripts\activate.bat" call "%~dp0venv\Scripts\activate.bat"
python "%~dp0scripts\run_tunnel_ngrok.py"
pause
