"""FastMCP server exposing the Mario AI app as debug tools.

Reads the admin key from config.json in-process (never logged). Talks to the
FastAPI server (:8765) and the flag-gated client debug server (:8770).
"""
import json
import os

from mcp.server.fastmcp import FastMCP, Image

from mcp_mario_debug.bridge import Bridge

mcp = FastMCP("mario-debug")


def _admin_key():
    try:
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(repo, "config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        return (cfg.get("server", cfg) or {}).get("admin_api_key", "") or cfg.get("admin_api_key", "")
    except Exception:
        return ""


_bridge = Bridge(admin_key=_admin_key())


@mcp.tool()
def mario_health() -> dict:
    """Server health: ws_connected, tts, emotion, uptime, cache stats."""
    return _bridge.health()


@mcp.tool()
def mario_state() -> dict:
    """What's on the pygame screen now: state, emotion, speaking, pose, full+shown text."""
    return _bridge.state()


@mcp.tool()
def mario_audio_out(n: int = 10) -> dict:
    """Last N played audio clips: text, duration, peak, rms, sample-rate, engine_guess, played_ok."""
    return {"clips": _bridge.audio_out(n)}


@mcp.tool()
def mario_logs(source: str = "both", grep: str = "", level: str = "DEBUG", n: int = 150) -> dict:
    """Tail server and/or client logs. source = server|client|both."""
    return {"lines": _bridge.logs(source=source, n=n, grep=grep, level=level)}


@mcp.tool()
def mario_screenshot() -> Image:
    """Screenshot of the pygame client (client frame, else OS window grab). Returns a PNG."""
    png = _bridge.screenshot_png()
    return Image(data=png or b"", format="png")


@mcp.tool()
def mario_send_text(text: str) -> dict:
    """Inject a typed user message into the live session (as if a guest typed it)."""
    return _bridge.send_text(text)


@mcp.tool()
def mario_inject_audio(wav_path: str) -> dict:
    """Simulate a guest SPEAKING: read a WAV file from disk, run it through STT -> reply."""
    try:
        with open(wav_path, "rb") as f:
            wav = f.read()
    except Exception as e:
        return {"error": f"read failed: {e}"}
    return _bridge.inject_audio(wav)


@mcp.tool()
def mario_inject_frame(image_path: str) -> dict:
    """Simulate a guest APPEARING: read an image, run it through person/face detection."""
    try:
        with open(image_path, "rb") as f:
            img = f.read()
    except Exception as e:
        return {"error": f"read failed: {e}"}
    return _bridge.inject_frame(img)


@mcp.tool()
def mario_set_emotion(emotion: str) -> dict:
    """Force the current emotion (e.g. happy, sad, excited, sleepy)."""
    return _bridge.set_emotion(emotion)


@mcp.tool()
def mario_trigger_event(name: str) -> dict:
    """Trigger a shot/ceremony event by name (e.g. deltarune, birthday_boy)."""
    return _bridge.trigger_event(name)


@mcp.tool()
def mario_set_night_phase(phase: str) -> dict:
    """Override night phase: WARM_UP | PARTY_MODE | UNHINGED | WIND_DOWN | AUTO."""
    return _bridge.set_night_phase(phase)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
