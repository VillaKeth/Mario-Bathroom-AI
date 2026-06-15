@echo off
echo Starting Cloudflare tunnel to http://localhost:8765 ...
echo Share the printed https URL as:  https://THAT-URL/friend?token=YOUR_TOKEN
echo WARNING: this exposes the WHOLE local server publicly. See docs/REMOTE_MIRROR.md Security.
cloudflared tunnel --url http://localhost:8765
