"""Ralph Loop — 1000 iterations of Mario voice tuning.

Downloads additional Charles Martinet clips, creates reference audio variations,
sweeps XTTS v2 parameters, and applies different post-processing chains.
Generates an HTML comparison page for easy A/B listening.
"""

import os
import sys
import json
import time
import random
import wave
import io
import subprocess
import shutil
import logging
import traceback
import numpy as np
import torch
import torchaudio
import soundfile as sf
from scipy import signal as scipy_signal

# --- Monkey-patches (MUST run before TTS import) ---
_original_torch_load = torch.load
def _patched_torch_load(*args, **kwargs):
    kwargs.setdefault("weights_only", False)
    return _original_torch_load(*args, **kwargs)
torch.load = _patched_torch_load

def _soundfile_torchaudio_load(filepath, *args, **kwargs):
    data, sr = sf.read(str(filepath), dtype="float32")
    if data.ndim == 1:
        data = data[np.newaxis, :]
    else:
        data = data.T
    return torch.from_numpy(data), sr
torchaudio.load = _soundfile_torchaudio_load

os.environ["COQUI_TOS_AGREED"] = "1"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [ralph] %(message)s")
log = logging.getLogger("ralph")

# ─── Paths ───────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RESULTS_DIR = os.path.join(DATA_DIR, "ralph_results")
CLIPS_DIR = os.path.join(DATA_DIR, "ralph_clips")
REFS_DIR = os.path.join(DATA_DIR, "ralph_refs")
PROGRESS_FILE = os.path.join(RESULTS_DIR, "progress.json")
BASE_URL = "https://raw.githubusercontent.com/eros71-dev/mario-voice-dataset/main/wavs"

os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(CLIPS_DIR, exist_ok=True)
os.makedirs(REFS_DIR, exist_ok=True)

# ─── Test phrases ────────────────────────────────────────────────────
TEST_PHRASES = [
    "It's-a me, Mario! Wahoo!",
    "Welcome to the bathroom, my friend! Let's-a go!",
    "Mama mia! You scared me!",
    "Here we go! Another adventure!",
    "Thank you so much for playing!",
    "Oh yeah! Mario time!",
    "Okey dokey! Let's-a do this!",
    "So long, see you next time!",
    "Woo hoo! That was fun!",
    "Hey there! How's it going?",
]

# ─── Phase 1: Download clips ────────────────────────────────────────
def download_clips():
    """Download clips 1-100 from Mario voice dataset."""
    log.info("Phase 1: Downloading Mario voice clips...")
    downloaded = []
    failed = []

    for clip_id in range(1, 101):
        local_path = os.path.join(CLIPS_DIR, f"clip_{clip_id:03d}.wav")
        if os.path.exists(local_path) and os.path.getsize(local_path) > 1000:
            downloaded.append(clip_id)
            continue

        url = f"{BASE_URL}/{clip_id}.wav"
        try:
            result = subprocess.run(
                ["curl", "-L", "-o", local_path, url, "--connect-timeout", "10",
                 "--max-time", "15", "-s", "-f"],
                capture_output=True, timeout=20
            )
            if result.returncode == 0 and os.path.exists(local_path) and os.path.getsize(local_path) > 1000:
                downloaded.append(clip_id)
            else:
                failed.append(clip_id)
                if os.path.exists(local_path):
                    os.remove(local_path)
        except Exception:
            failed.append(clip_id)
            if os.path.exists(local_path):
                try:
                    os.remove(local_path)
                except OSError:
                    pass

    # Also copy existing clips
    for f in os.listdir(DATA_DIR):
        if f.startswith("mario_clip_") and f.endswith(".wav"):
            src = os.path.join(DATA_DIR, f)
            dst = os.path.join(CLIPS_DIR, f"existing_{f}")
            if not os.path.exists(dst):
                shutil.copy2(src, dst)

    log.info(f"Downloaded: {len(downloaded)} clips, Failed: {len(failed)}")
    return downloaded


def analyze_clips():
    """Analyze all downloaded clips — get duration, energy, quality."""
    clips = []
    for f in sorted(os.listdir(CLIPS_DIR)):
        if not f.endswith(".wav"):
            continue
        path = os.path.join(CLIPS_DIR, f)
        try:
            data, sr = sf.read(path, dtype="float32")
            if data.ndim > 1:
                data = data[:, 0]
            duration = len(data) / sr
            rms = float(np.sqrt(np.mean(data ** 2)))
            peak = float(np.max(np.abs(data)))
            # Skip very short or silent clips
            if duration < 1.0 or rms < 0.01:
                continue
            clips.append({
                "file": f,
                "path": path,
                "duration": duration,
                "rms": rms,
                "peak": peak,
                "sr": sr,
            })
        except Exception:
            continue

    clips.sort(key=lambda c: c["rms"], reverse=True)
    log.info(f"Analyzed {len(clips)} usable clips")
    return clips


# ─── Phase 2: Create reference variations ───────────────────────────
def create_reference_audio(clips, name, clip_indices, target_sr=22050):
    """Create a reference audio file from selected clips."""
    out_path = os.path.join(REFS_DIR, f"ref_{name}.wav")
    if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
        return out_path

    all_data = []
    for idx in clip_indices:
        if idx >= len(clips):
            continue
        data, sr = sf.read(clips[idx]["path"], dtype="float32")
        if data.ndim > 1:
            data = data[:, 0]
        # Resample if needed
        if sr != target_sr:
            num_samples = int(len(data) * target_sr / sr)
            data = scipy_signal.resample(data, num_samples).astype(np.float32)
        # Normalize
        peak = np.max(np.abs(data))
        if peak > 0:
            data = data / peak * 0.9
        all_data.append(data)
        # Add 0.3s silence between clips
        all_data.append(np.zeros(int(target_sr * 0.3), dtype=np.float32))

    if not all_data:
        return None

    combined = np.concatenate(all_data)
    sf.write(out_path, combined, target_sr)
    duration = len(combined) / target_sr
    log.info(f"Created reference '{name}': {duration:.1f}s from {len(clip_indices)} clips")
    return out_path


def create_all_references(clips):
    """Create 20 different reference audio variations."""
    refs = {}

    if not clips:
        # Use existing references as fallback
        existing_curated = os.path.join(DATA_DIR, "mario_reference_curated.wav")
        existing_full = os.path.join(DATA_DIR, "mario_reference.wav")
        if os.path.exists(existing_curated):
            refs["existing_curated"] = existing_curated
        if os.path.exists(existing_full):
            refs["existing_full"] = existing_full
        return refs

    n = len(clips)

    # 1. Top 1 clip (loudest/clearest)
    r = create_reference_audio(clips, "top1", [0])
    if r:
        refs["top1"] = r

    # 2. Top 3 clips
    r = create_reference_audio(clips, "top3", list(range(min(3, n))))
    if r:
        refs["top3"] = r

    # 3. Top 5 clips
    r = create_reference_audio(clips, "top5", list(range(min(5, n))))
    if r:
        refs["top5"] = r

    # 4. Top 10 clips
    r = create_reference_audio(clips, "top10", list(range(min(10, n))))
    if r:
        refs["top10"] = r

    # 5. All clips
    r = create_reference_audio(clips, "all", list(range(n)))
    if r:
        refs["all"] = r

    # 6-10. Clips sorted by duration (short to long)
    by_dur = sorted(range(n), key=lambda i: clips[i]["duration"])
    # Short clips only (<3s)
    short = [i for i in by_dur if clips[i]["duration"] < 3.0]
    r = create_reference_audio(clips, "short_only", short[:10])
    if r:
        refs["short_only"] = r

    # Long clips only (>4s)
    long_clips = [i for i in by_dur if clips[i]["duration"] > 4.0]
    r = create_reference_audio(clips, "long_only", long_clips[:5])
    if r:
        refs["long_only"] = r

    # 11-15. Random selections
    for seed in range(5):
        rng = random.Random(seed + 42)
        selection = rng.sample(range(n), min(5, n))
        r = create_reference_audio(clips, f"random_{seed}", selection)
        if r:
            refs[f"random_{seed}"] = r

    # 16-20. Energy-based selections
    by_energy = sorted(range(n), key=lambda i: clips[i]["rms"], reverse=True)
    r = create_reference_audio(clips, "high_energy", by_energy[:5])
    if r:
        refs["high_energy"] = r

    low_energy = by_energy[-5:] if len(by_energy) >= 5 else by_energy
    r = create_reference_audio(clips, "low_energy", low_energy)
    if r:
        refs["low_energy"] = r

    # Also include existing curated reference
    existing_curated = os.path.join(DATA_DIR, "mario_reference_curated.wav")
    existing_full = os.path.join(DATA_DIR, "mario_reference.wav")
    if os.path.exists(existing_curated):
        refs["existing_curated"] = existing_curated
    if os.path.exists(existing_full):
        refs["existing_full"] = existing_full

    log.info(f"Created {len(refs)} reference audio variations")
    return refs


# ─── Phase 3: Parameter generation ──────────────────────────────────
def generate_param_sets(n_total=1000, refs=None):
    """Generate 1000 parameter combinations using stratified random sampling."""
    if refs is None:
        refs = {}
    ref_names = list(refs.keys()) or ["existing_curated"]

    param_sets = []
    rng = random.Random(12345)

    for i in range(n_total):
        ref_name = ref_names[i % len(ref_names)]
        phrase_idx = i % len(TEST_PHRASES)

        params = {
            "iteration": i + 1,
            "ref_name": ref_name,
            "phrase_idx": phrase_idx,
            "phrase": TEST_PHRASES[phrase_idx],
            "gpt_cond_len": rng.choice([3, 4, 6, 8, 12]),
            "temperature": round(rng.uniform(0.1, 0.9), 2),
            "speed": round(rng.uniform(0.85, 1.5), 2),
            "pitch_semitones": rng.randint(-1, 6),
            "top_k": rng.choice([10, 20, 30, 50, 80]),
            "top_p": round(rng.uniform(0.5, 0.99), 2),
            "repetition_penalty": round(rng.uniform(1.5, 12.0), 1),
            "length_penalty": round(rng.uniform(0.8, 2.5), 1),
            # Post-processing
            "eq_boost_khz": rng.choice([0, 2.0, 3.0, 4.0, 5.0]),
            "eq_boost_db": round(rng.uniform(0, 6), 1) if rng.random() > 0.3 else 0,
            "compression": rng.choice([False, False, True]),
            "reverb_amount": round(rng.uniform(0, 0.15), 3) if rng.random() > 0.5 else 0,
        }
        param_sets.append(params)

    return param_sets


# ─── Phase 4: Audio generation ──────────────────────────────────────
def apply_pitch_shift(audio, sr, semitones):
    """Apply pitch shift via resampling."""
    if semitones == 0:
        return audio
    factor = 2 ** (semitones / 12.0)
    new_length = int(len(audio) / factor)
    if new_length < 10:
        return audio
    return scipy_signal.resample(audio, new_length).astype(np.float32)


def apply_eq_boost(audio, sr, center_freq_khz, boost_db):
    """Apply a parametric EQ boost at a specific frequency."""
    if boost_db <= 0 or center_freq_khz <= 0:
        return audio
    center_hz = center_freq_khz * 1000
    Q = 2.0
    w0 = 2 * np.pi * center_hz / sr
    alpha = np.sin(w0) / (2 * Q)
    A = 10 ** (boost_db / 40)

    b0 = 1 + alpha * A
    b1 = -2 * np.cos(w0)
    b2 = 1 - alpha * A
    a0 = 1 + alpha / A
    a1 = -2 * np.cos(w0)
    a2 = 1 - alpha / A

    b = np.array([b0 / a0, b1 / a0, b2 / a0])
    a = np.array([1.0, a1 / a0, a2 / a0])

    try:
        return scipy_signal.lfilter(b, a, audio).astype(np.float32)
    except Exception:
        return audio


def apply_compression(audio, threshold=-20, ratio=4.0):
    """Simple dynamic range compression."""
    threshold_linear = 10 ** (threshold / 20.0)
    result = audio.copy()
    mask = np.abs(result) > threshold_linear
    if np.any(mask):
        excess = np.abs(result[mask]) - threshold_linear
        compressed = threshold_linear + excess / ratio
        result[mask] = np.sign(result[mask]) * compressed
    # Normalize
    peak = np.max(np.abs(result))
    if peak > 0:
        result = result / peak * 0.95
    return result


def apply_reverb(audio, sr, amount):
    """Simple reverb via comb filter."""
    if amount <= 0:
        return audio
    delay_samples = int(sr * 0.03)  # 30ms delay
    result = audio.copy()
    if delay_samples < len(result):
        result[delay_samples:] += audio[:-delay_samples] * amount
    peak = np.max(np.abs(result))
    if peak > 0:
        result = result / peak * 0.95
    return result


def generate_single(model, ref_path, params, output_path):
    """Generate a single audio sample and save it."""
    text = params["phrase"]
    gpt_cond_len = params["gpt_cond_len"]

    # Compute conditioning latents for this reference
    gpt_cond_latents, speaker_embedding = model.synthesizer.tts_model.get_conditioning_latents(
        audio_path=ref_path,
        max_ref_length=30,
        gpt_cond_len=gpt_cond_len,
        gpt_cond_chunk_len=gpt_cond_len,
    )

    # Synthesize
    from contextlib import nullcontext
    ctx = torch.amp.autocast("cuda") if torch.cuda.is_available() else nullcontext()
    with ctx:
        result = model.synthesizer.tts_model.inference(
            text=text,
            language="en",
            gpt_cond_latent=gpt_cond_latents,
            speaker_embedding=speaker_embedding,
            temperature=params["temperature"],
            length_penalty=params["length_penalty"],
            repetition_penalty=params["repetition_penalty"],
            top_k=params["top_k"],
            top_p=params["top_p"],
            speed=params["speed"],
            enable_text_splitting=True,
        )

    audio = result["wav"]
    if hasattr(audio, 'cpu'):
        audio = audio.cpu().numpy()
    else:
        audio = np.array(audio, dtype=np.float32)
    if audio.ndim > 1:
        audio = audio.squeeze()

    sr = 24000  # XTTS output sample rate

    # Post-processing chain
    audio = apply_pitch_shift(audio, sr, params["pitch_semitones"])
    audio = apply_eq_boost(audio, sr, params["eq_boost_khz"], params["eq_boost_db"])
    if params["compression"]:
        audio = apply_compression(audio)
    audio = apply_reverb(audio, sr, params["reverb_amount"])

    # Normalize final
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak * 0.95

    # Save as WAV
    audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(audio_int16.tobytes())

    duration = len(audio_int16) / sr
    return duration


# ─── Phase 5: HTML generation ───────────────────────────────────────
def generate_html(results):
    """Create HTML comparison page for all results."""
    html_path = os.path.join(RESULTS_DIR, "index.html")

    # Group by reference
    by_ref = {}
    for r in results:
        ref = r["ref_name"]
        if ref not in by_ref:
            by_ref[ref] = []
        by_ref[ref].append(r)

    html = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>Ralph Loop — Mario Voice Tuning (1000 iterations)</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }
h1 { color: #e63946; text-align: center; font-size: 2em; margin-bottom: 5px; }
.subtitle { text-align: center; color: #888; margin-bottom: 20px; }
.stats { display: flex; justify-content: center; gap: 30px; margin-bottom: 20px; flex-wrap: wrap; }
.stat { background: #16213e; padding: 15px 25px; border-radius: 10px; text-align: center; }
.stat-val { font-size: 2em; color: #e63946; font-weight: bold; }
.stat-label { color: #888; font-size: 0.9em; }
.controls { background: #16213e; padding: 15px; border-radius: 10px; margin-bottom: 20px; display: flex; gap: 15px; flex-wrap: wrap; align-items: center; justify-content: center; }
.controls label { color: #aaa; }
.controls select, .controls input { background: #0f3460; color: #eee; border: 1px solid #333; padding: 5px 10px; border-radius: 5px; }
.ref-section { margin-bottom: 30px; }
.ref-title { color: #e6b800; font-size: 1.3em; margin: 15px 0 10px; border-bottom: 1px solid #333; padding-bottom: 5px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 10px; }
.card { background: #16213e; border-radius: 8px; padding: 12px; border: 1px solid #222; transition: border-color 0.2s; }
.card:hover { border-color: #e63946; }
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.card-num { color: #e63946; font-weight: bold; font-size: 1.1em; }
.card-dur { color: #888; font-size: 0.8em; }
.phrase { color: #aaddff; font-style: italic; font-size: 0.9em; margin-bottom: 8px; }
.params { font-size: 0.75em; color: #777; line-height: 1.4; }
.param-key { color: #aaa; }
.param-val { color: #e6b800; }
audio { width: 100%; height: 35px; margin: 5px 0; }
.star-btn { cursor: pointer; font-size: 1.5em; background: none; border: none; color: #555; }
.star-btn.starred { color: #e6b800; }
.favorites { background: #1e3a1e; padding: 15px; border-radius: 10px; margin-bottom: 20px; display: none; }
.favorites h2 { color: #4caf50; margin-bottom: 10px; }
</style>
</head><body>
<h1>🍄 Ralph Loop — Mario Voice Tuning</h1>
<p class="subtitle">1000 iterations of XTTS v2 parameter sweep</p>

<div class="stats">
  <div class="stat"><div class="stat-val">""" + str(len(results)) + """</div><div class="stat-label">Iterations</div></div>
  <div class="stat"><div class="stat-val">""" + str(len(by_ref)) + """</div><div class="stat-label">Reference Audios</div></div>
  <div class="stat"><div class="stat-val">""" + str(len(TEST_PHRASES)) + """</div><div class="stat-label">Test Phrases</div></div>
</div>

<div class="controls">
  <label>Filter ref: <select id="filterRef" onchange="filterCards()">
    <option value="all">All References</option>"""

    for ref_name in sorted(by_ref.keys()):
        html += f'\n    <option value="{ref_name}">{ref_name} ({len(by_ref[ref_name])})</option>'

    html += """
  </select></label>
  <label>Filter phrase: <select id="filterPhrase" onchange="filterCards()">
    <option value="all">All Phrases</option>"""

    for i, phrase in enumerate(TEST_PHRASES):
        html += f'\n    <option value="{i}">{phrase[:40]}...</option>'

    html += """
  </select></label>
  <label>Sort: <select id="sortBy" onchange="sortCards()">
    <option value="iteration">Iteration #</option>
    <option value="pitch">Pitch</option>
    <option value="speed">Speed</option>
    <option value="temp">Temperature</option>
    <option value="duration">Duration</option>
  </select></label>
  <button onclick="showFavorites()" style="background:#4caf50;color:#fff;border:none;padding:8px 15px;border-radius:5px;cursor:pointer;">⭐ Show Favorites</button>
</div>

<div id="favorites" class="favorites">
  <h2>⭐ Starred Favorites</h2>
  <div id="favGrid" class="grid"></div>
</div>

<div id="cardContainer">"""

    for ref_name in sorted(by_ref.keys()):
        html += f'\n<div class="ref-section" data-ref="{ref_name}">'
        html += f'\n<h3 class="ref-title">📎 Reference: {ref_name}</h3>'
        html += '\n<div class="grid">'

        for r in sorted(by_ref[ref_name], key=lambda x: x["iteration"]):
            it = r["iteration"]
            wav_file = f"iter_{it:04d}.wav"
            p = r
            html += f"""
<div class="card" data-ref="{ref_name}" data-phrase="{p['phrase_idx']}" data-iteration="{it}" data-pitch="{p['pitch_semitones']}" data-speed="{p['speed']}" data-temp="{p['temperature']}" data-duration="{r.get('duration', 0):.1f}">
  <div class="card-header">
    <span class="card-num">#{it:04d}</span>
    <button class="star-btn" onclick="toggleStar(this, {it})">☆</button>
    <span class="card-dur">{r.get('duration', 0):.1f}s / {r.get('gen_time', 0):.1f}s gen</span>
  </div>
  <div class="phrase">"{p['phrase']}"</div>
  <audio controls preload="none"><source src="{wav_file}" type="audio/wav"></audio>
  <div class="params">
    <span class="param-key">pitch:</span><span class="param-val">{p['pitch_semitones']}st</span> |
    <span class="param-key">speed:</span><span class="param-val">{p['speed']}</span> |
    <span class="param-key">temp:</span><span class="param-val">{p['temperature']}</span> |
    <span class="param-key">cond_len:</span><span class="param-val">{p['gpt_cond_len']}</span> |
    <span class="param-key">top_k:</span><span class="param-val">{p['top_k']}</span> |
    <span class="param-key">top_p:</span><span class="param-val">{p['top_p']}</span> |
    <span class="param-key">rep:</span><span class="param-val">{p['repetition_penalty']}</span> |
    <span class="param-key">eq:</span><span class="param-val">{p['eq_boost_khz']}kHz +{p['eq_boost_db']}dB</span> |
    <span class="param-key">comp:</span><span class="param-val">{'Y' if p['compression'] else 'N'}</span> |
    <span class="param-key">reverb:</span><span class="param-val">{p['reverb_amount']}</span>
  </div>
</div>"""

        html += '\n</div></div>'

    html += """
</div>

<script>
const favorites = new Set(JSON.parse(localStorage.getItem('ralph_favorites') || '[]'));

function filterCards() {
  const ref = document.getElementById('filterRef').value;
  const phrase = document.getElementById('filterPhrase').value;
  document.querySelectorAll('.ref-section').forEach(s => {
    if (ref === 'all' || s.dataset.ref === ref) {
      s.style.display = '';
      s.querySelectorAll('.card').forEach(c => {
        c.style.display = (phrase === 'all' || c.dataset.phrase === phrase) ? '' : 'none';
      });
    } else {
      s.style.display = 'none';
    }
  });
}

function sortCards() {
  const by = document.getElementById('sortBy').value;
  document.querySelectorAll('.grid').forEach(grid => {
    const cards = Array.from(grid.children);
    cards.sort((a, b) => parseFloat(a.dataset[by] || 0) - parseFloat(b.dataset[by] || 0));
    cards.forEach(c => grid.appendChild(c));
  });
}

function toggleStar(btn, it) {
  if (favorites.has(it)) { favorites.delete(it); btn.textContent = '☆'; btn.classList.remove('starred'); }
  else { favorites.add(it); btn.textContent = '★'; btn.classList.add('starred'); }
  localStorage.setItem('ralph_favorites', JSON.stringify([...favorites]));
}

function showFavorites() {
  const div = document.getElementById('favorites');
  const grid = document.getElementById('favGrid');
  div.style.display = div.style.display === 'none' ? '' : 'none';
  grid.innerHTML = '';
  favorites.forEach(it => {
    const card = document.querySelector(`.card[data-iteration="${it}"]`);
    if (card) grid.appendChild(card.cloneNode(true));
  });
}

// Restore stars
document.querySelectorAll('.card').forEach(c => {
  const it = parseInt(c.dataset.iteration);
  if (favorites.has(it)) {
    const btn = c.querySelector('.star-btn');
    btn.textContent = '★'; btn.classList.add('starred');
  }
});
</script>
</body></html>"""

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    log.info(f"HTML comparison page saved: {html_path}")


# ─── Main loop ───────────────────────────────────────────────────────
def load_progress():
    """Load progress from previous run."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {"completed": [], "results": []}


def save_progress(progress):
    """Save progress for resumability."""
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f)


def run():
    """Main ralph loop — 1000 iterations of voice tuning."""
    log.info("=" * 60)
    log.info("RALPH LOOP — Mario Voice Tuning (1000 iterations)")
    log.info("=" * 60)

    total_start = time.time()

    # Phase 1: Download clips
    downloaded_ids = download_clips()

    # Analyze clips
    clips = analyze_clips()

    # Phase 2: Create reference variations
    refs = create_all_references(clips)
    if not refs:
        log.error("No reference audio available! Cannot proceed.")
        return

    log.info(f"Available references: {list(refs.keys())}")

    # Phase 3: Generate parameter sets
    target = int(os.environ.get("RALPH_TARGET", 1000))
    param_sets = generate_param_sets(target, refs)

    # Load progress
    progress = load_progress()
    completed_set = set(progress["completed"])

    # Phase 4: Load model
    log.info("Loading XTTS v2 model...")
    model_start = time.time()
    from TTS.api import TTS as CoquiTTS
    model = CoquiTTS("tts_models/multilingual/multi-dataset/xtts_v2")
    if torch.cuda.is_available():
        model = model.to("cuda")
        log.info(f"Model on CUDA ({time.time() - model_start:.1f}s)")
    else:
        log.info(f"Model on CPU ({time.time() - model_start:.1f}s) — will be slow!")

    # Phase 5: Run iterations
    results = progress["results"]
    errors = 0
    batch_start = time.time()

    for i, params in enumerate(param_sets):
        it = params["iteration"]
        if it in completed_set:
            continue

        ref_name = params["ref_name"]
        ref_path = refs.get(ref_name)
        if ref_path is None or not os.path.exists(ref_path):
            log.warning(f"[{it}/1000] Skipping — reference '{ref_name}' not found")
            continue

        output_path = os.path.join(RESULTS_DIR, f"iter_{it:04d}.wav")

        try:
            gen_start = time.time()
            duration = generate_single(model, ref_path, params, output_path)
            gen_time = time.time() - gen_start

            result = {**params, "duration": round(duration, 2), "gen_time": round(gen_time, 2)}
            results.append(result)
            completed_set.add(it)

            elapsed = time.time() - total_start
            rate = len(completed_set) / max(elapsed, 1) * 3600
            eta = (target - len(completed_set)) / max(rate / 3600, 0.001)

            if it % 10 == 0 or it <= 5:
                log.info(
                    f"[{it:04d}/{target}] ✓ {duration:.1f}s audio in {gen_time:.1f}s | "
                    f"ref={ref_name} pitch={params['pitch_semitones']} speed={params['speed']} "
                    f"temp={params['temperature']} | ETA: {eta:.0f}min"
                )

        except Exception as e:
            errors += 1
            log.warning(f"[{it:04d}/{target}] ✗ Error: {str(e)[:80]}")
            if errors > 50:
                log.error("Too many errors, stopping early")
                break

        # Save progress every 25 iterations
        if len(completed_set) % 25 == 0:
            progress["completed"] = list(completed_set)
            progress["results"] = results
            save_progress(progress)

    # Final save
    progress["completed"] = list(completed_set)
    progress["results"] = results
    save_progress(progress)

    # Phase 6: Generate HTML
    log.info("Generating HTML comparison page...")
    generate_html(results)

    total_time = time.time() - total_start
    log.info("=" * 60)
    log.info(f"RALPH LOOP COMPLETE")
    log.info(f"  Iterations: {len(completed_set)}/{target}")
    log.info(f"  Errors: {errors}")
    log.info(f"  Total time: {total_time / 60:.1f} minutes")
    log.info(f"  Results: {RESULTS_DIR}")
    log.info(f"  HTML: {os.path.join(RESULTS_DIR, 'index.html')}")
    log.info("=" * 60)


if __name__ == "__main__":
    run()
