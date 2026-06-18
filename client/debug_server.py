"""Flag-gated localhost debug HTTP surface for the pygame client.

Enabled only when MARIO_DEBUG=1. Binds 127.0.0.1 so it is never reachable off
the box (and never via the Cloudflare tunnel). The MCP (mcp_mario_debug) calls it.
"""
import json
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)
DEBUG_PORT = 8770


def route(method: str, path: str, query: dict, body: bytes, provider):
    """Pure dispatcher -> (status:int, content_type:str, body:bytes). No sockets."""
    def js(obj, status=200):
        return status, "application/json", json.dumps(obj).encode()

    if method == "GET" and path == "/state":
        return js(provider.debug_state())
    if method == "GET" and path == "/audio":
        n = int((query.get("n") or ["10"])[0])
        return js({"clips": provider.audio_log_snapshot(n=n)})
    if method == "GET" and path == "/log":
        n = int((query.get("n") or ["200"])[0])
        grep = (query.get("grep") or [""])[0]
        level = (query.get("level") or ["DEBUG"])[0]
        return js({"lines": provider.log_snapshot(n=n, grep=grep, level=level)})
    if method == "GET" and path == "/frame.png":
        png = provider.latest_frame_png()
        if not png:
            return 503, "application/json", json.dumps({"error": "no frame yet"}).encode()
        return 200, "image/png", png
    if method == "POST" and path == "/inject_frame":
        try:
            data = json.loads(body or b"{}")
        except Exception as e:
            return js({"error": f"bad json: {e}"}, status=400)
        return js(provider.inject_frame_b64(data.get("image_b64", "")))
    return 404, "application/json", json.dumps({"error": "not found"}).encode()


def _make_handler(provider):
    class _H(BaseHTTPRequestHandler):
        def _handle(self, method):
            u = urlparse(self.path)
            length = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(length) if length else b""
            try:
                status, ctype, payload = route(method, u.path, parse_qs(u.query), body, provider)
            except Exception as e:
                status, ctype, payload = 500, "application/json", json.dumps({"error": str(e)}).encode()
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

        def log_message(self, *a):
            pass  # silence access logs

    return _H


def start_debug_server(provider, port: int = DEBUG_PORT):
    """Start the debug server on 127.0.0.1 if MARIO_DEBUG=1. Returns the server or None."""
    if os.environ.get("MARIO_DEBUG", "") != "1":
        return None
    srv = ThreadingHTTPServer(("127.0.0.1", port), _make_handler(provider))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    logger.info(f"[debug] client debug server on http://127.0.0.1:{port} (MARIO_DEBUG=1)")
    return srv
