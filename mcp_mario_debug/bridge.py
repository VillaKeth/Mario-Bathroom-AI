"""Pure bridge logic to the server (:8765) and client (:8770) debug surfaces.

No FastMCP import here, so it unit-tests with httpx.MockTransport. mss/pillow are
imported lazily inside screenshot_png() so this module imports without them.
"""
import base64

import httpx

DEFAULT_SERVER = "http://127.0.0.1:8765"
DEFAULT_CLIENT = "http://127.0.0.1:8770"


class Bridge:
    def __init__(self, server=DEFAULT_SERVER, client=DEFAULT_CLIENT, admin_key="", http=None):
        self.server = server.rstrip("/")
        self.client = client.rstrip("/")
        self.admin_key = admin_key
        self.http = http or httpx.Client(timeout=20.0)

    # ---- low level ----
    def _get(self, base, path, **params):
        try:
            r = self.http.get(base + path, params=params)
            return r.json()
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    def _post(self, base, path, payload):
        try:
            r = self.http.post(base + path, json=payload)
            return r.json()
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    def _keyed(self, payload):
        d = dict(payload)
        if self.admin_key:
            d["api_key"] = self.admin_key
        return d

    # ---- monitor ----
    def health(self):
        return self._get(self.server, "/api/health")

    def state(self):
        return self._get(self.client, "/state")

    def audio_out(self, n=10):
        r = self._get(self.client, "/audio", n=n)
        return r.get("clips", r) if isinstance(r, dict) else r

    def logs(self, source="both", n=200, grep="", level="DEBUG"):
        out = []
        if source in ("server", "both"):
            r = self._get(self.server, "/debug/log", n=n, grep=grep, level=level)
            out += [{**l, "src": "server"} for l in r.get("lines", [])] if isinstance(r, dict) else []
        if source in ("client", "both"):
            r = self._get(self.client, "/log", n=n, grep=grep, level=level)
            out += [{**l, "src": "client"} for l in r.get("lines", [])] if isinstance(r, dict) else []
        return out

    def screenshot_png(self):
        """Return PNG bytes: client frame first, else OS window grab (mss)."""
        try:
            r = self.http.get(self.client + "/frame.png")
            if r.status_code == 200 and r.content[:4] == b"\x89PNG":
                return r.content
        except Exception:
            pass
        try:
            import mss
            import mss.tools
            with mss.mss() as sct:
                shot = sct.grab(sct.monitors[1])
                return mss.tools.to_png(shot.rgb, shot.size)
        except Exception:
            return None

    # ---- control ----
    def send_text(self, text):
        return self._post(self.server, "/admin/simulate_text", self._keyed({"text": text}))

    def inject_audio(self, wav_bytes):
        b64 = base64.b64encode(wav_bytes).decode()
        return self._post(self.server, "/admin/inject_audio", self._keyed({"wav_b64": b64}))

    def inject_frame(self, image_bytes):
        b64 = base64.b64encode(image_bytes).decode()
        return self._post(self.client, "/inject_frame", {"image_b64": b64})

    def set_emotion(self, emotion):
        return self._post(self.server, "/admin/set_emotion", self._keyed({"emotion": emotion}))

    def trigger_event(self, name):
        return self._post(self.server, f"/admin/trigger_event/{name}", self._keyed({}))

    def set_night_phase(self, phase):
        return self._post(self.server, "/admin/set_night_phase", self._keyed({"phase": phase}))
