# Recognition Test-People Library

A self-contained lab for testing whether the bot recognizes returning guests by
**voice**, **face**, and **both at once** — under simulated party conditions
(party noise mixed into the voice, multiple face angles).

## The library

Each test person is a folder under `people/<name>/`:

```
people/ava/
  profile.json          name + assigned voice + face identity + which angles encode
  voice/
    enroll.wav          "Hi, my name is Ava" — the enrollment utterance
    probe_01..03.wav    different sentences, SAME voice — the probes
  faces/
    enroll_front.jpg    one pose, used to enroll the face
    angle_01..09.jpg    other poses of the SAME person — probe angles
```

- **Faces:** sklearn **Olivetti** — 6 real people, 10 poses each (varied angle /
  lighting / expression). Green border in `index.html` = dlib can encode that angle.
- **Voices:** **edge-tts** — one distinct neural voice per person.
- **Party noise:** `assets/party_noise/party_bed_*.wav` — synthetic cocktail-party
  babble (overlapped crowd chatter + room hiss). Drop real party clips in here to
  use them instead; the harness picks up any `.wav` in that folder.

Browse it: open **`index.html`** (face contact-sheet + playable voice clips), or
read **`manifest.json`**.

## Build / rebuild

```bash
venv\Scripts\python.exe tests/recognition_lab/build_library.py          # idempotent
venv\Scripts\python.exe tests/recognition_lab/build_library.py --force  # regenerate
```
(needs network: edge-tts for voices, one-time Olivetti download for faces.)

## Run the test

```bash
venv\Scripts\python.exe tests/recognition_lab/run_recognition_test.py
```
Drives the **real** pipeline (`speaker_id`, `face_memory.FaceMemory`,
`face_enrollment.resolve_faces`) on **isolated temp DBs** — the live server data is
never touched. Writes `results.json`. Scenarios:

| | What it tests |
|---|---|
| A. Voice only | enroll each voice → identify probes at SNR = clean / 10 / 5 / 0 dB |
| B. Face only | enroll one pose → match the *other* angles |
| C. Voice+Face | simultaneous noisy voice + a face image → fused decision |
| C2. Cross-modal enroll | unknown face + known voice → learn → match by face later (the F1/F2 fix) |
| D. Imposter | un-enrolled person must NOT be falsely accepted |

## Caveats (read before trusting the numbers)

These conditions are **kinder than a real party**, so treat high scores as a
ceiling, not a guarantee:

- **Voices are synthetic (edge-tts).** Distinct TTS timbres are easier to tell apart
  than real guests. Real-speaker accuracy will be lower — swap in a real multi-speaker
  corpus (e.g. LibriSpeech via torchaudio) to harden this.
- **Olivetti faces are clean** — centered, frontal-ish, even lighting. A real doorway
  camera (steep angles, backlight, motion blur, small faces) will detect/encode far
  fewer faces. The HOG detector is the bottleneck there (see audit F6).
- **Party noise is synthetic** and mixed at fixed SNRs. Real rooms vary.

The **relative** story is the real signal: voice degrades fast with noise, face holds
up, and the two together are far more robust than either alone.
