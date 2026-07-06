"""One-click PERMANENT public tunnel via an ngrok reserved (static) domain.

Unlike the Cloudflare quick tunnel (scripts/run_tunnel.py), the URL here never
changes -- it uses the free static domain you claim once at
https://dashboard.ngrok.com/domains and store in config.json under
mirror.ngrok_domain. Prints the ready-to-share /friend URL with the token/PIN
pulled from config.json. Just keep the window open; close it to drop the tunnel.

Launched by start_tunnel_ngrok.bat. Stdlib only.
"""
import json
import os
import shutil
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
domain = (mirror.get("ngrok_domain") or "").strip()
domain = domain.replace("https://", "").replace("http://", "").strip("/")
basic = (mirror.get("ngrok_basic_auth") or "").strip()  # optional "user:pass" edge gate

if not domain:
    print("ERROR: no reserved ngrok domain set in config.json.\n")
    print("  1. Claim a free static domain (one per account):")
    print("       https://dashboard.ngrok.com/domains")
    print("  2. Add it to config.json under \"mirror\", e.g.:")
    print('       "mirror": { "ngrok_domain": "your-name.ngrok-free.app", ... }')
    print("  3. Re-run start_tunnel_ngrok.bat.")
    sys.exit(1)

base = f"https://{domain}"
friend = base + "/friend" + (f"?token={token}" if token else "")

def _resolve_ngrok():
    """Return a launchable ngrok executable.

    On this dev box `ngrok` on PATH is a pyenv shim (ngrok.bat -> `pyenv exec
    ngrok`) that subprocess can't CreateProcess and that silently breaks once
    the project venv is activated. So prefer the REAL ngrok.exe; fall back to
    the bare name (run via the shell) only as a last resort.
    """
    override = (mirror.get("ngrok_path") or "").strip()
    if override and os.path.isfile(override):
        return override
    exe = shutil.which("ngrok.exe")  # real Windows binary on PATH
    if exe:
        return exe
    local = os.environ.get("LOCALAPPDATA")
    if local:
        cand = os.path.join(local, "ngrok", "ngrok.exe")
        if os.path.isfile(cand):  # standard pyngrok / ngrok install dir
            return cand
    generic = shutil.which("ngrok")  # Linux/Mac real binary (or a Win shim)
    if generic and not generic.lower().endswith(".bat"):
        return generic
    return "ngrok"  # last resort: let the shell resolve it


NGROK = _resolve_ngrok()
use_shell = NGROK == "ngrok"
if use_shell:
    cmd = f"ngrok http {port} --url={domain}"
    if basic:
        cmd += f" --basic-auth={basic}"
else:
    cmd = [NGROK, "http", str(port), f"--url={domain}"]
    if basic:
        cmd.append(f"--basic-auth={basic}")

bar = "=" * 70
print(bar)
print("  PERMANENT NGROK TUNNEL  --  this link never changes")
print(bar)
print(f"  CHAT:        {friend}" + (f"   (PIN: {pin})" if pin else ""))
if admin:
    print(f"  RECOGNITION: {base}/recognition?api_key={admin}")
print(f"  RAW URL:     {base}")
if basic:
    print(f"  EDGE AUTH:   browser prompts for {basic.split(':')[0]}:*** before load")
print(bar)
print(f"  NGROK BIN:   {NGROK}")
print(f"\nStarting ngrok -> http://localhost:{port} ... keep this window open.\n")

try:
    subprocess.run(cmd, shell=use_shell)
except KeyboardInterrupt:
    pass
