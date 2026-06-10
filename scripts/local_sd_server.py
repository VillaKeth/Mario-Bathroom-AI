"""Local Stable Diffusion server exposing a minimal AUTOMATIC1111-compatible API.

Runs in gpt_sovits_env (torch+cuda already installed). The Character Creator
wizard's sprite_generator auto-detects an A1111 backend at http://localhost:7860
and POSTs to /sdapi/v1/txt2img — so once this is up, sprite generation works
100% offline/local with NO cloud (Pollinations is dead: HTTP 402 paywall).

Endpoints:
  GET  /sdapi/v1/sd-models   -> [{...}]                 (detection probe)
  POST /sdapi/v1/txt2img     -> {"images": ["<b64png>"]}

Model: SD 1.5 (non-gated community mirror), fp16, memory-sliced to fit the
4GB Quadro P1000 dev GPU. First run downloads ~4GB to the HF cache.

Run: gpt_sovits_env/Scripts/python.exe scripts/local_sd_server.py
"""
import base64
import io
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import torch
from diffusers import StableDiffusionPipeline, DPMSolverMultistepScheduler

MODEL_ID = os.environ.get("LOCAL_SD_MODEL", "stable-diffusion-v1-5/stable-diffusion-v1-5")
PORT = int(os.environ.get("LOCAL_SD_PORT", "7860"))

_pipe = None
_lock = threading.Lock()  # GPU can do one image at a time on 4GB


def get_pipe():
    global _pipe
    if _pipe is not None:
        return _pipe
    use_cuda = torch.cuda.is_available()
    dtype = torch.float16 if use_cuda else torch.float32
    print(f"[sd] loading {MODEL_ID} (cuda={use_cuda}, dtype={dtype}) ...", flush=True)
    pipe = StableDiffusionPipeline.from_pretrained(
        MODEL_ID, torch_dtype=dtype, safety_checker=None, requires_safety_checker=False,
    )
    pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config)
    if use_cuda:
        pipe = pipe.to("cuda")
        # Fit into ~2.5GB free on the P1000.
        pipe.enable_attention_slicing()
        try:
            pipe.enable_vae_slicing()
        except Exception:
            pass
    _pipe = pipe
    print("[sd] model ready", flush=True)
    return _pipe


_seed_counter = [0]


def render(prompt: str, negative: str, width: int, height: int, steps: int, cfg: float,
           seed: int | None = None) -> bytes:
    pipe = get_pipe()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    g = torch.Generator(device=dev)
    # Explicit per-request seed so output always varies, even if a fresh
    # Generator's default state were deterministic. Derive from the prompt +
    # a monotonic counter so identical inputs are reproducible but a batch of
    # distinct poses never collapses to one image.
    if seed is None:
        _seed_counter[0] += 1
        seed = (abs(hash(prompt)) + _seed_counter[0]) % (2**31 - 1)
    g.manual_seed(int(seed))
    with _lock:
        with torch.inference_mode():
            img = pipe(
                prompt=prompt, negative_prompt=negative or None,
                width=width, height=height,
                num_inference_steps=steps, guidance_scale=cfg,
                generator=g,
            ).images[0]
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass  # quiet

    def _json(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/sdapi/v1/sd-models"):
            self._json(200, [{"title": "local-sd15", "model_name": "local-sd15",
                              "hash": "local", "filename": MODEL_ID}])
        elif self.path.startswith("/health") or self.path == "/":
            self._json(200, {"status": "ok", "model": MODEL_ID,
                             "loaded": _pipe is not None})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.startswith("/sdapi/v1/txt2img"):
            self._json(404, {"error": "not found"})
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            self._json(400, {"error": f"bad request: {e}"})
            return
        try:
            png = render(
                prompt=req.get("prompt", ""),
                negative=req.get("negative_prompt", ""),
                width=int(req.get("width", 512)),
                height=int(req.get("height", 768)),
                steps=int(req.get("steps", 20)),
                cfg=float(req.get("cfg_scale", 7)),
                seed=req.get("seed"),
            )
            self._json(200, {"images": [base64.b64encode(png).decode("ascii")]})
        except Exception as e:
            print(f"[sd] render error: {e}", flush=True)
            self._json(500, {"error": str(e)})


def main():
    # Warm the model so the first wizard probe + request don't time out.
    get_pipe()
    srv = HTTPServer(("127.0.0.1", PORT), Handler)  # single-threaded: one GPU job at a time
    print(f"[sd] serving A1111-compatible API on http://127.0.0.1:{PORT}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    sys.exit(main())
