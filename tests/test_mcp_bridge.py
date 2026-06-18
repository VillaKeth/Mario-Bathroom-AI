import httpx

from mcp_mario_debug import bridge


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_health_passthrough():
    def h(req):
        return httpx.Response(200, json={"ws_connected": True, "tts": "ok"})
    b = bridge.Bridge(server="http://s", client="http://c", admin_key="", http=_client(h))
    assert b.health()["ws_connected"] is True


def test_send_text_posts_admin_key():
    seen = {}

    def h(req):
        seen["body"] = req.read().decode()
        return httpx.Response(200, json={"status": "ok"})
    b = bridge.Bridge(server="http://s", client="http://c", admin_key="K", http=_client(h))
    b.send_text("hi")
    assert '"api_key": "K"' in seen["body"] and '"text": "hi"' in seen["body"]


def test_audio_out_reads_client():
    def h(req):
        assert req.url.path == "/audio"
        return httpx.Response(200, json={"clips": [{"text": "hi", "engine_guess": "sovits"}]})
    b = bridge.Bridge(server="http://s", client="http://c", admin_key="", http=_client(h))
    assert b.audio_out(3)[0]["engine_guess"] == "sovits"


def test_logs_merge_both_sources():
    def h(req):
        src = "server" if req.url.host == "s" else "client"
        return httpx.Response(200, json={"lines": [{"msg": f"from {src}", "level": "INFO"}]})
    b = bridge.Bridge(server="http://s", client="http://c", admin_key="", http=_client(h))
    msgs = [l["msg"] for l in b.logs(source="both")]
    assert "from server" in msgs and "from client" in msgs


def test_client_down_returns_error_not_raise():
    def h(req):
        raise httpx.ConnectError("refused")
    b = bridge.Bridge(server="http://s", client="http://c", admin_key="", http=_client(h))
    assert "error" in b.state()


def test_screenshot_prefers_client_frame():
    png = b"\x89PNG\r\n\x1a\n" + b"x" * 20

    def h(req):
        return httpx.Response(200, content=png, headers={"content-type": "image/png"})
    b = bridge.Bridge(server="http://s", client="http://c", admin_key="", http=_client(h))
    assert b.screenshot_png() == png
