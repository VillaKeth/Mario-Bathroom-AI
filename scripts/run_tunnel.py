"""One-click public tunnel for the party bot.

Runs a Cloudflare *quick* tunnel (no account needed) to the local server and
prints the full, ready-to-share chat URL — with the token/PIN pulled from
config.json — instead of making you dig the random URL out of cloudflared's
log spam. Just keep the window open; close it to drop the tunnel.

Launched by start_tunnel.bat. Stdlib only.
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, "config.json")


def _load_cfg():
    try:
        with open(CFG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


cfg = _load_cfg()
server = cfg.get("server") or {}
mirror = cfg.get("mirror") or {}
port = server.get("port", 8765)
token = mirror.get("token", "")
pin = mirror.get("pin", "")
admin = server.get("admin_api_key", "")

print(f"Starting Cloudflare tunnel -> http://localhost:{port}")
print("No account needed. The URL is random and changes every run.")
print("WARNING: this exposes the WHOLE local server publicly. See docs/REMOTE_MIRROR.md.\n")

URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

proc = subprocess.Popen(
    ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1,
)

shown = False
try:
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        if not shown:
            m = URL_RE.search(line)
            if m:
                shown = True
                base = m.group(0)
                friend = base + "/friend" + (f"?token={token}" if token else "")
                bar = "=" * 70
                print("\n" + bar)
                print("  PUBLIC TUNNEL READY  --  share the chat link below")
                print(bar)
                print(f"  CHAT:        {friend}" + (f"   (PIN: {pin})" if pin else ""))
                if admin:
                    print(f"  RECOGNITION: {base}/recognition?api_key={admin}")
                print(f"  RAW URL:     {base}")
                print(bar + "\n")
except KeyboardInterrupt:
    pass
finally:
    try:
        proc.terminate()
    except Exception:
        pass
