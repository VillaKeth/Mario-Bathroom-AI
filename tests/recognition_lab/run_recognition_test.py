"""Drive the REAL recognition pipeline against the test-people library.

Uses real LibriSpeech voices when present (voice_real block), else the edge-tts
voices. Scenarios:
  A. VOICE ONLY  — single vs MULTI-sample enrollment, across party-noise SNRs (F5).
  B. FACE ONLY   — enroll one pose, match the OTHER angles.
  C. VOICE+FACE  — simultaneous, fused via recognition_fusion (SNR-aware, F5/F6).
  C2. cross-modal enroll — unknown face + known voice -> learn (F1/F2).
  D. IMPOSTER    — un-enrolled voice AND face must NOT be falsely accepted.

Real modules: speaker_id, face_memory.FaceMemory, face_enrollment, recognition_fusion.
Voice + face stores are isolated in a temp dir (live server data untouched).
"""
import os
import sys
import json
import glob
import sqlite3
import tempfile

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "server"))

SR = 16000
SNR_LEVELS = [None, 10, 5, 0]          # None = clean
HELD_OUT_OLIVETTI = [7, 8]              # face imposters (not enrolled)


# ----------------------------- audio helpers -----------------------------
def load_float(path):
    y, sr = sf.read(path, dtype="float32")
    if y.ndim > 1:
        y = y.mean(axis=1)
    return y


def rms(x):
    return float(np.sqrt(np.mean(x * x)) + 1e-12)


def to_pcm16(x):
    return (np.clip(x, -1.0, 1.0) * 32767).astype(np.int16).tobytes()


def mix_party(sig, noise, snr_db):
    if snr_db is None:
        return sig
    if len(noise) < len(sig):
        noise = np.tile(noise, int(np.ceil(len(sig) / len(noise))))
    noise = noise[: len(sig)]
    target = rms(sig) / (10 ** (snr_db / 20.0))
    out = sig + noise * (target / rms(noise))
    peak = np.abs(out).max()
    return out / peak if peak > 1 else out


def snr_to_noise(snr_db):
    if snr_db is None:
        return 0.0
    return max(0.0, min(1.0, (20 - snr_db) / 20.0))


def label(snr):
    return "clean" if snr is None else f"{snr}dB"


# ----------------------------- face helpers ------------------------------
def face_encoding(path):
    import face_recognition
    img = face_recognition.load_image_file(path)
    locs = face_recognition.face_locations(img, model="hog")
    if not locs:
        locs = face_recognition.face_locations(img, model="hog", number_of_times_to_upsample=2)
    encs = face_recognition.face_encodings(img, locs) if locs else []
    return encs[0] if encs else None


# ----------------------------- library load ------------------------------
def load_people():
    people = []
    for prof in sorted(glob.glob(os.path.join(HERE, "people", "*", "profile.json"))):
        with open(prof, encoding="utf-8") as f:
            people.append(json.load(f))
    return people


def abspath(rel):
    return os.path.join(HERE, rel)


def voice_block(p, source):
    """Return (enroll_files: list, probe_files: list) for the chosen source."""
    if source == "real" and "voice_real" in p:
        b = p["voice_real"]
        return list(b["enroll"]), list(b["probes"])
    b = p["voice"]
    return [b["enroll"]], list(b["probes"])


# ----------------------------- enrollment --------------------------------
def reset_speakers(speaker_id):
    with sqlite3.connect(speaker_id.DB_PATH) as conn:
        conn.execute("DELETE FROM speakers")
        conn.commit()


def enroll_voices(speaker_id, people, source, mode):
    for p in people:
        enroll_files, _ = voice_block(p, source)
        chunks = [to_pcm16(load_float(abspath(f))) for f in enroll_files]
        if mode == "multi":
            speaker_id.register_speaker_multi(p["name"], chunks)
        else:
            speaker_id.register_speaker(p["name"], chunks[0])


def voice_only_curve(speaker_id, people, source, beds):
    acc = {}
    for snr in SNR_LEVELS:
        correct = total = 0
        for pi, p in enumerate(people):
            _, probes = voice_block(p, source)
            for probe in probes:
                sig = load_float(abspath(probe))
                bed = beds[pi % len(beds)] if beds else np.zeros(len(sig))
                info = speaker_id.identify_speaker(to_pcm16(mix_party(sig, bed, snr)))
                total += 1
                correct += 1 if info["name"] == p["name"] else 0
        acc[label(snr)] = (correct, total)
    return acc


# ----------------------------- main --------------------------------------
def main():
    import speaker_id
    import face_enrollment
    import recognition_fusion as rf
    from face_memory import FaceMemory

    tmp = tempfile.mkdtemp(prefix="reclab_")
    speaker_id.DB_PATH = os.path.join(tmp, "voices.db")
    print(f"[isolated stores in {tmp}]")
    print("Loading voice encoder...")
    speaker_id.init_speaker_id(collection_name="reclab_voices")
    if not speaker_id.is_available():
        print("FATAL: voice encoder unavailable"); return
    face_db = FaceMemory(os.path.join(tmp, "faces.db"), collection_name="reclab_faces")

    people = load_people()
    beds = [load_float(p) for p in glob.glob(os.path.join(HERE, "assets", "party_noise", "*.wav"))]
    source = "real" if all("voice_real" in p for p in people) else "tts"
    print(f"{len(people)} people | voice source: {source.upper()} | {len(beds)} party beds\n")

    results = {"voice_source": source}

    # face enroll (front pose) — used by B, C
    for p in people:
        front = next((a for a in p["faces"] if a["role"] == "enroll" and a["encodes"]), None)
        enc = face_encoding(abspath(front["file"])) if front else None
        if enc is not None:
            face_db.learn_guest(p["name"], enc)

    # ---- A. VOICE ONLY: single vs multi-sample enrollment ----
    print("== A. VOICE ONLY — single vs multi-sample enrollment ==")
    curves = {}
    for mode in ("single", "multi"):
        reset_speakers(speaker_id)
        enroll_voices(speaker_id, people, source, mode)
        curves[mode] = voice_only_curve(speaker_id, people, source, beds)
    hdr = "  enroll   " + "".join(f"{label(s):>8}" for s in SNR_LEVELS)
    print(hdr)
    for mode in ("single", "multi"):
        row = "  " + f"{mode:8s} "
        for s in SNR_LEVELS:
            c, t = curves[mode][label(s)]
            row += f"{(c/t*100):7.0f}%"
        print(row)
    results["voice_only"] = {m: {k: v[0] / v[1] for k, v in curves[m].items()} for m in curves}

    # keep the better (multi) enrollment for the rest
    reset_speakers(speaker_id)
    enroll_voices(speaker_id, people, source, "multi")

    # ---- B. FACE ONLY ----
    print("\n== B. FACE ONLY (match other angles) ==")
    fcorrect = ftotal = 0
    for p in people:
        pc = pt = 0
        for a in p["faces"]:
            if a["role"] != "probe" or not a["encodes"]:
                continue
            enc = face_encoding(abspath(a["file"]))
            if enc is None:
                continue
            m = face_db.find_match(enc)
            pt += 1; ftotal += 1
            if m and m["name"] == p["name"]:
                pc += 1; fcorrect += 1
        print(f"  {p['name']:5s}: {pc}/{pt} angles matched")
    results["face_only"] = fcorrect / ftotal if ftotal else 0
    print(f"  OVERALL: {fcorrect}/{ftotal} = {results['face_only']*100:.0f}%")

    # ---- C. VOICE+FACE fused (SNR-aware) ----
    print("\n== C. VOICE + FACE (simultaneous, fused @5dB) ==")
    nl = snr_to_noise(5)
    fused_correct = voice_only_correct = total = 0
    for pi, p in enumerate(people):
        _, probes = voice_block(p, source)
        sig = load_float(abspath(probes[0]))
        bed = beds[pi % len(beds)] if beds else np.zeros(len(sig))
        v = speaker_id.identify_speaker(to_pcm16(mix_party(sig, bed, 5)))
        face_a = next((a for a in p["faces"] if a["role"] == "probe" and a["encodes"]), None)
        enc = face_encoding(abspath(face_a["file"])) if face_a else None
        fm = face_db.find_match(enc) if enc is not None else None
        decision = rf.fuse_identity(voice=v, face=fm, noise_level=nl)
        total += 1
        fused_correct += 1 if decision["name"] == p["name"] else 0
        voice_only_correct += 1 if v["name"] == p["name"] else 0
        print(f"  {p['name']:5s}: voice={str(v['name']):6s}(c={v['confidence']:.2f}) "
              f"face={str(fm['name']) if fm else 'None':6s} -> {str(decision['name']):6s} "
              f"[{decision['source']}] {'OK' if decision['name'] == p['name'] else 'MISS'}")
    results["voice_face_fused"] = fused_correct / total
    print(f"  fused: {fused_correct}/{total} = {fused_correct/total*100:.0f}%   "
          f"(voice-alone would be {voice_only_correct}/{total} = {voice_only_correct/total*100:.0f}%)")

    # ---- C2. cross-modal enroll ----
    print("\n== C2. cross-modal enroll (unknown face + known voice -> learn) ==")
    fresh = FaceMemory(os.path.join(tmp, "faces2.db"), collection_name="reclab_faces2")
    p = people[0]
    angs = [a for a in p["faces"] if a["role"] == "probe" and a["encodes"]]
    enc0 = face_encoding(abspath(angs[0]["file"]))
    before = fresh.find_match(enc0)
    face_enrollment.resolve_faces([{"encoding": enc0.tolist(), "confidence": 0.9}], fresh, p["name"])
    after = fresh.find_match(face_encoding(abspath(angs[1]["file"])))
    ok = bool(after and after["name"] == p["name"])
    print(f"  {p['name']}: before={before} ; after learns -> other-angle={after['name'] if after else None}  "
          f"[{'works' if ok else 'FAILED'}]")
    results["cross_modal_enroll"] = ok

    # ---- D. IMPOSTER (voice + face) ----
    print("\n== D. IMPOSTER (un-enrolled -> expect rejection) ==")
    # face imposters: held-out olivetti identities
    import face_recognition, cv2
    from sklearn.datasets import fetch_olivetti_faces
    ds = fetch_olivetti_faces()
    face_false = face_total = 0
    for person_id in HELD_OUT_OLIVETTI:
        idx = next(i for i in range(len(ds.target)) if ds.target[i] == person_id)
        rgb = cv2.cvtColor(cv2.resize((ds.images[idx] * 255).astype("uint8"), (256, 256),
                           interpolation=cv2.INTER_CUBIC), cv2.COLOR_GRAY2RGB)
        locs = face_recognition.face_locations(rgb, model="hog") or \
            face_recognition.face_locations(rgb, model="hog", number_of_times_to_upsample=2)
        encs = face_recognition.face_encodings(rgb, locs) if locs else []
        if not encs:
            continue
        m = face_db.find_match(encs[0])
        face_total += 1; face_false += 1 if m else 0
        print(f"  face olivetti#{person_id}: {'FALSE-ACCEPT ' + m['name'] if m else 'rejected'}")
    # voice imposter: a LibriSpeech speaker not enrolled
    voice_false = voice_total = 0
    if source == "real":
        enrolled = {p["voice_real"]["libri_speaker"] for p in people if "voice_real" in p}
        base = os.path.join(HERE, "_corpus", "LibriSpeech", "test-clean")
        for spk in sorted(os.listdir(base)):
            if spk in enrolled or not spk.isdigit():
                continue
            flacs = glob.glob(os.path.join(base, spk, "*", "*.flac"))
            if not flacs:
                continue
            y, sr = sf.read(flacs[0], dtype="float32")
            info = speaker_id.identify_speaker(to_pcm16(y))
            # Open-set gate (the LIVE policy): no face, party noise floor.
            decision = rf.fuse_identity(voice=info, face=None, noise_level=rf.LIVE_PARTY_NOISE_LEVEL)
            raw = f"match {info['name']}" if not info["is_new"] else "rejected"
            voice_total += 1
            voice_false += 1 if decision["name"] else 0  # count AFTER the open-set gate
            print(f"  voice libri#{spk}: raw={raw}(c={info.get('confidence',0):.2f}) "
                  f"-> open-set gate={decision['name'] or 'rejected'}")
            break  # one is enough to demonstrate
    results["imposter"] = {"face_false": face_false, "face_total": face_total,
                           "voice_false": voice_false, "voice_total": voice_total}

    # ---- summary ----
    print("\n" + "=" * 60 + "\nSUMMARY  (voice source: " + source.upper() + ")")
    vs = results["voice_only"]
    print(f"  Voice only  single: clean {vs['single']['clean']*100:.0f}%  5dB {vs['single']['5dB']*100:.0f}%")
    print(f"  Voice only  MULTI : clean {vs['multi']['clean']*100:.0f}%  5dB {vs['multi']['5dB']*100:.0f}%")
    print(f"  Face only         : {results['face_only']*100:.0f}%")
    print(f"  Voice+Face fused  : {results['voice_face_fused']*100:.0f}%")
    print(f"  Cross-modal enroll: {'works' if results['cross_modal_enroll'] else 'FAILED'}")
    print(f"  Imposter false-acc: face {face_false}/{face_total}  voice {voice_false}/{voice_total}")

    with open(os.path.join(HERE, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\nresults.json written.")


if __name__ == "__main__":
    main()
