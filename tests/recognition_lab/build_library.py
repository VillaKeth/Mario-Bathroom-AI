"""Build the recognition test-people library.

For each test person creates:
  people/<slug>/profile.json          name + assigned voice + face identity
  people/<slug>/voice/enroll.wav      "my name is X" enrollment utterance
  people/<slug>/voice/probe_NN.wav    different sentences, same voice (probes)
  people/<slug>/faces/enroll_front.jpg one pose used to enroll the face
  people/<slug>/faces/angle_NN.jpg     other poses of the SAME person (probe angles)

Plus assets/party_noise/*.wav  — synthetic cocktail-party babble beds.
Plus manifest.json + index.html (viewable contact sheet).

Faces  : sklearn Olivetti (40 real people x 10 poses each — varied angle/lighting/expression).
Voices : edge-tts distinct neural voices (one per person).

Idempotent: skips files that already exist unless --force.
"""
import os
import sys
import json
import glob
import asyncio
import argparse

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PEOPLE_DIR = os.path.join(HERE, "people")
NOISE_DIR = os.path.join(HERE, "assets", "party_noise")

# name, edge-tts voice, olivetti person id (0-39)
PEOPLE = [
    ("Ava",  "en-US-AriaNeural",     0),
    ("Ben",  "en-US-GuyNeural",      1),
    ("Cara", "en-US-JennyNeural",    2),
    ("Dan",  "en-GB-RyanNeural",     3),
    ("Eli",  "en-AU-WilliamNeural",  4),
    ("Fay",  "en-US-AnaNeural",      5),
]

PROBE_SENTENCES = [
    "Where is the bathroom in this place?",
    "This party is amazing and the music is so good.",
    "Can you tell me a really funny joke right now?",
]

# Generic crowd chatter for the party-noise beds (spoken by assorted voices).
CHATTER = [
    "Oh my gosh, did you see that?",
    "I cannot believe he actually said that out loud.",
    "Hey, can someone grab me another drink?",
    "This song is my absolute favorite, turn it up!",
    "Wait, who invited all of these people anyway?",
    "I am having such a great time tonight, honestly.",
    "Do you know where the snacks went, I am starving.",
    "Let us all do a toast for the birthday boy!",
]
CHATTER_VOICES = ["en-US-AriaNeural", "en-US-GuyNeural", "en-GB-SoniaNeural",
                  "en-US-JennyNeural", "en-AU-WilliamNeural", "en-CA-LiamNeural"]

SR = 16000


def slugify(name):
    return name.strip().lower().replace(" ", "_")


async def _edge_to_wav(text, voice, out_wav):
    """Synthesize text with edge-tts and write a 16k mono PCM16 wav. Returns float audio."""
    import edge_tts
    import librosa
    import soundfile as sf
    mp3 = out_wav[:-4] + ".mp3"
    await edge_tts.Communicate(text, voice).save(mp3)
    y, _ = librosa.load(mp3, sr=SR, mono=True)
    sf.write(out_wav, y, SR, subtype="PCM_16")
    try:
        os.remove(mp3)
    except OSError:
        pass
    return y


def _olivetti_face_rgb(images, idx, size=256):
    import cv2
    img = (images[idx] * 255).astype("uint8")
    big = cv2.resize(img, (size, size), interpolation=cv2.INTER_CUBIC)
    return cv2.cvtColor(big, cv2.COLOR_GRAY2RGB)


def _encodes(rgb):
    """True if dlib can find+encode a face (tries upsample fallback)."""
    import face_recognition
    locs = face_recognition.face_locations(rgb, model="hog")
    if not locs:
        locs = face_recognition.face_locations(rgb, model="hog", number_of_times_to_upsample=2)
    return bool(locs and face_recognition.face_encodings(rgb, locs))


def _pink_noise(n):
    from scipy.signal import lfilter
    white = np.random.randn(n)
    b = [0.049922, -0.095993, 0.050612, -0.004408]
    a = [1.0, -2.494956, 2.017265, -0.522189]
    out = lfilter(b, a, white)
    return out / (np.abs(out).max() + 1e-9)


async def build_party_beds(n_beds=3, dur_s=14.0, force=False):
    import soundfile as sf
    import librosa
    os.makedirs(NOISE_DIR, exist_ok=True)
    made = []
    for b in range(n_beds):
        out = os.path.join(NOISE_DIR, f"party_bed_{b+1:02d}.wav")
        made.append(out)
        if os.path.exists(out) and not force:
            continue
        n = int(dur_s * SR)
        bed = _pink_noise(n) * 0.06  # faint room hiss
        # overlay several chatter utterances at random offsets/gains
        for k in range(4):
            voice = CHATTER_VOICES[(b * 4 + k) % len(CHATTER_VOICES)]
            line = CHATTER[(b * 3 + k) % len(CHATTER)]
            tmp = os.path.join(NOISE_DIR, f"_chatter_{b}_{k}.wav")
            y = await _edge_to_wav(line, voice, tmp)
            try:
                os.remove(tmp)
            except OSError:
                pass
            gain = 0.25 + 0.12 * k
            off = np.random.randint(0, max(1, n - len(y)))
            seg = y[: max(0, n - off)]
            bed[off: off + len(seg)] += seg[: len(bed[off: off + len(seg)])] * gain
        bed = bed / (np.abs(bed).max() + 1e-9) * 0.9
        sf.write(out, bed.astype(np.float32), SR, subtype="PCM_16")
        print(f"  party bed -> {os.path.relpath(out, HERE)} ({dur_s:.0f}s)")
    return made


async def build_people(force=False):
    from sklearn.datasets import fetch_olivetti_faces
    import cv2
    print("Loading Olivetti faces...")
    ds = fetch_olivetti_faces()
    images, target = ds.images, ds.target

    manifest = []
    for name, voice, person_id in PEOPLE:
        slug = slugify(name)
        pdir = os.path.join(PEOPLE_DIR, slug)
        vdir = os.path.join(pdir, "voice")
        fdir = os.path.join(pdir, "faces")
        for d in (vdir, fdir):
            os.makedirs(d, exist_ok=True)
        print(f"\n[{name}] voice={voice} olivetti_person={person_id}")

        # ---- faces: all 10 poses of this olivetti person ----
        idxs = [i for i in range(len(target)) if target[i] == person_id]
        face_files, angles = [], []
        for j, idx in enumerate(idxs):
            rgb = _olivetti_face_rgb(images, idx)
            usable = _encodes(rgb)
            fname = "enroll_front.jpg" if j == 0 else f"angle_{j:02d}.jpg"
            fpath = os.path.join(fdir, fname)
            if force or not os.path.exists(fpath):
                cv2.imwrite(fpath, rgb)  # grayscale-derived -> BGR==RGB
            rel = os.path.relpath(fpath, HERE).replace("\\", "/")
            face_files.append(rel)
            angles.append({"file": rel, "role": "enroll" if j == 0 else "probe",
                           "encodes": bool(usable)})
        usable_n = sum(1 for a in angles if a["encodes"])
        print(f"  faces: {len(angles)} poses, {usable_n} dlib-encodable")

        # ---- voice: enroll + probes ----
        enroll_wav = os.path.join(vdir, "enroll.wav")
        if force or not os.path.exists(enroll_wav):
            await _edge_to_wav(f"Hi, my name is {name}. Nice to meet you.", voice, enroll_wav)
        probe_files = []
        for pi, sent in enumerate(PROBE_SENTENCES, 1):
            pw = os.path.join(vdir, f"probe_{pi:02d}.wav")
            if force or not os.path.exists(pw):
                await _edge_to_wav(sent, voice, pw)
            probe_files.append(os.path.relpath(pw, HERE).replace("\\", "/"))
        print(f"  voice: enroll + {len(probe_files)} probes")

        profile = {
            "name": name,
            "slug": slug,
            "voice_name": voice,
            "olivetti_person_id": person_id,
            "voice": {
                "enroll": os.path.relpath(enroll_wav, HERE).replace("\\", "/"),
                "probes": probe_files,
            },
            "faces": angles,
        }
        with open(os.path.join(pdir, "profile.json"), "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)
        manifest.append(profile)
    return manifest


def add_libri_voices(n_enroll=3, n_probe=3, force=False):
    """Add REAL voices (LibriSpeech test-clean) to each existing person as a
    `voice_real` block: n_enroll clips (for multi-sample enrollment) + n_probe probes.
    Faces stay paired with the same named person. Needs _corpus/ downloaded."""
    import soundfile as sf
    import librosa
    base = os.path.join(HERE, "_corpus", "LibriSpeech", "test-clean")
    if not os.path.isdir(base):
        print(f"  LibriSpeech not found at {base} — run _fetch_libri.py first")
        return None

    # speakers with enough utterances, lowest id first (stable)
    spk_flacs = {}
    for spk in sorted(os.listdir(base), key=lambda s: int(s) if s.isdigit() else 1 << 30):
        flacs = sorted(glob.glob(os.path.join(base, spk, "*", "*.flac")))
        if len(flacs) >= n_enroll + n_probe:
            spk_flacs[spk] = flacs
    chosen = list(spk_flacs.items())[: len(PEOPLE)]
    if len(chosen) < len(PEOPLE):
        print(f"  WARN: only {len(chosen)} suitable LibriSpeech speakers found")

    for (name, _voice, _pid), (spk, flacs) in zip(PEOPLE, chosen):
        slug = slugify(name)
        vdir = os.path.join(PEOPLE_DIR, slug, "voice_real")
        os.makedirs(vdir, exist_ok=True)
        enroll_files, probe_files = [], []
        for k, fl in enumerate(flacs[: n_enroll + n_probe]):
            y, sr = sf.read(fl, dtype="float32")
            if y.ndim > 1:
                y = y.mean(axis=1)
            if sr != SR:
                y = librosa.resample(y, orig_sr=sr, target_sr=SR)
            role = "enroll" if k < n_enroll else "probe"
            idx = k if k < n_enroll else k - n_enroll
            out = os.path.join(vdir, f"{role}_{idx+1:02d}.wav")
            if force or not os.path.exists(out):
                sf.write(out, y.astype(np.float32), SR, subtype="PCM_16")
            rel = os.path.relpath(out, HERE).replace("\\", "/")
            (enroll_files if role == "enroll" else probe_files).append(rel)

        ppath = os.path.join(PEOPLE_DIR, slug, "profile.json")
        with open(ppath, encoding="utf-8") as f:
            prof = json.load(f)
        prof["voice_real"] = {"libri_speaker": spk, "enroll": enroll_files, "probes": probe_files}
        with open(ppath, "w", encoding="utf-8") as f:
            json.dump(prof, f, indent=2)
        print(f"  {name:5s}: LibriSpeech speaker {spk} -> {len(enroll_files)} enroll + {len(probe_files)} probes")

    # reload all profiles for a fresh manifest
    manifest = []
    for prof in sorted(glob.glob(os.path.join(PEOPLE_DIR, "*", "profile.json"))):
        with open(prof, encoding="utf-8") as f:
            manifest.append(json.load(f))
    return manifest


def write_index_html(manifest):
    rows = []
    for p in manifest:
        thumbs = "".join(
            f'<figure><img src="{a["file"]}" width="96" '
            f'style="border:2px solid {"#2a2" if a["encodes"] else "#a22"}">'
            f'<figcaption>{os.path.basename(a["file"])}<br>'
            f'{"enroll" if a["role"]=="enroll" else "angle"} '
            f'{"OK" if a["encodes"] else "no-face"}</figcaption></figure>'
            for a in p["faces"]
        )
        probes = "".join(
            f'<audio controls src="{pp}" style="height:28px"></audio>' for pp in p["voice"]["probes"]
        )
        rows.append(f"""
    <section>
      <h2>{p['name']} <small>({p['voice_name']} · olivetti #{p['olivetti_person_id']})</small></h2>
      <div class="faces">{thumbs}</div>
      <div class="voice">
        <b>enroll:</b> <audio controls src="{p['voice']['enroll']}" style="height:28px"></audio>
        <b>probes:</b> {probes}
      </div>
    </section>""")
    html = f"""<!doctype html><meta charset="utf-8">
<title>Recognition Test-People Library</title>
<style>
 body{{font-family:system-ui,Arial;margin:24px;background:#111;color:#eee}}
 section{{border:1px solid #333;border-radius:10px;padding:14px;margin:14px 0;background:#1a1a1a}}
 h2 small{{color:#888;font-weight:normal;font-size:.6em}}
 .faces{{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0}}
 figure{{margin:0;text-align:center;font-size:10px;color:#aaa}}
 .voice{{margin-top:8px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}}
 audio{{vertical-align:middle}}
</style>
<h1>Recognition Test-People Library</h1>
<p>{len(manifest)} people. Green border = dlib can encode that face angle; red = no face found.
Faces: Olivetti (real). Voices: edge-tts (distinct neural voice per person).</p>
{''.join(rows)}
"""
    out = os.path.join(HERE, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nindex.html -> {out}")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--add-libri", action="store_true",
                    help="add real LibriSpeech voices to existing people (voice_real block)")
    args = ap.parse_args()
    os.makedirs(PEOPLE_DIR, exist_ok=True)

    if args.add_libri:
        print("Adding real LibriSpeech voices...")
        manifest = add_libri_voices(force=args.force)
        if manifest:
            beds = sorted(glob.glob(os.path.join(NOISE_DIR, "*.wav")))
            with open(os.path.join(HERE, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump({"people": manifest,
                           "party_noise": [os.path.relpath(b, HERE).replace("\\", "/") for b in beds]},
                          f, indent=2)
            write_index_html(manifest)
            print(f"\nDONE: real voices added to {len(manifest)} people.")
        return

    manifest = await build_people(force=args.force)
    print("\nBuilding party-noise beds...")
    beds = await build_party_beds(force=args.force)
    with open(os.path.join(HERE, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"people": manifest,
                   "party_noise": [os.path.relpath(b, HERE).replace("\\", "/") for b in beds]},
                  f, indent=2)
    write_index_html(manifest)
    print(f"\nDONE: {len(manifest)} people, {len(beds)} party beds.")


if __name__ == "__main__":
    asyncio.run(main())
