"""Persistent Fish Speech synthesis server.

Loads the Fish Speech v1.5.1 engine ONCE, then serves synthesis over local HTTP
so per-utterance latency is seconds, not a full model load. Started as a
subprocess by server/fish_speech_tts.py (the runtime TTS engine wrapper).

Endpoints:
    GET  /health      -> {"status": "ok", "loaded": true}
    POST /synthesize  -> WAV bytes
        JSON body: {"text": ..., "ref": <wav path>, "ref_text": ...,
                    "temperature": 0.9, "top_p": 0.85, "repetition_penalty": 1.4}

Run: fish_speech_env/Scripts/python.exe scripts/fish_server.py [port]
"""
import io
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CKPT = os.path.join(BASE, "fish_speech_ckpts")
DECODER = os.path.join(CKPT, "firefly-gan-vq-fsq-8x1024-21hz-generator.pth")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("FISH_PORT", "7861"))

_engine = None
_lock = threading.Lock()


def get_engine():
    global _engine
    if _engine is not None:
        return _engine
    import torch
    from fish_speech.inference_engine import TTSInferenceEngine
    from fish_speech.models.text2semantic.inference import launch_thread_safe_queue
    from fish_speech.models.vqgan.inference import load_model as load_decoder_model

    device = "cuda" if torch.cuda.is_available() else "cpu"
    precision = torch.half if device == "cuda" else torch.float32
    print(f"[fish_server] loading engine (device={device})...", flush=True)
    llama_queue = launch_thread_safe_queue(
        checkpoint_path=CKPT, device=device, precision=precision, compile=False)
    decoder = load_decoder_model(
        config_name="firefly_gan_vq", checkpoint_path=DECODER, device=device)
    _engine = TTSInferenceEngine(
        llama_queue=llama_queue, decoder_model=decoder, compile=False, precision=precision)
    print("[fish_server] engine ready", flush=True)
    return _engine


def synthesize(req: dict) -> bytes | None:
    from fish_speech.utils.schema import ServeTTSRequest, ServeReferenceAudio
    import numpy as np
    import soundfile as sf

    engine = get_engine()
    with open(req["ref"], "rb") as f:
        ref_bytes = f.read()
    tts_req = ServeTTSRequest(
        text=req["text"],
        references=[ServeReferenceAudio(audio=ref_bytes, text=req.get("ref_text", ""))],
        reference_id=None,
        max_new_tokens=1024, chunk_length=200,
        top_p=float(req.get("top_p", 0.85)),
        repetition_penalty=float(req.get("repetition_penalty", 1.4)),
        temperature=float(req.get("temperature", 0.9)),
        format="wav",
    )
    with _lock:
        audio = None
        for result in engine.inference(tts_req):
            if result.code == "final":
                audio = result.audio
                break
            if result.code == "error":
                print(f"[fish_server] inference error: {result.error}", flush=True)
                return None
    if audio is None:
        return None
    sr, data = audio
    if data.dtype != np.float32:
        data = data.astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, data, sr, format="WAV")
    return buf.getvalue()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/health"):
            body = json.dumps({"status": "ok", "loaded": _engine is not None}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if not self.path.startswith("/synthesize"):
            self.send_response(404); self.end_headers(); return
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n) or b"{}")
            wav = synthesize(req)
            if wav:
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(len(wav)))
                self.end_headers()
                self.wfile.write(wav)
            else:
                self.send_response(500)
                self.end_headers()
        except Exception as e:
            print(f"[fish_server] error: {e}", flush=True)
            try:
                self.send_response(500); self.end_headers()
            except Exception:
                pass


def main():
    get_engine()  # warm before accepting traffic
    srv = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"[fish_server] serving on http://127.0.0.1:{PORT}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
