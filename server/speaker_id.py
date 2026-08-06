"""Speaker identification using voice embeddings (resemblyzer) + SQLite storage."""

import logging
import sqlite3
import json
import os
import numpy as np

# Sibling import: this repo loads server/ modules as both bare top-level copies
# and server.* package copies (independent module instances). recognition_config
# holds a module-global cache, so every module in a process must resolve the
# SAME instance of it. Mirrors server/face_memory.py and server/mario_prompt.py:409-412.
if __package__:
    from server import recognition_config
else:
    import recognition_config

# Fix numpy deprecation in resemblyzer (np.bool removed in numpy 1.24+)
import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    if not hasattr(np, 'bool') or type(np.bool) != type:
        np.bool = bool

# resemblyzer is required for speaker identification but optional for basic chat
_HAS_RESEMBLYZER = False
try:
    from resemblyzer import VoiceEncoder, preprocess_wav
    _HAS_RESEMBLYZER = True
except ImportError:
    VoiceEncoder = None
    preprocess_wav = None
    logging.getLogger(__name__).warning(
        "[speaker_id] resemblyzer not installed — speaker identification disabled. "
        "Install with: pip install resemblyzer"
    )

DEBUG_SPEAKER = os.environ.get("DEBUG_SPEAKER", "").lower() in ("1", "true", "yes")
logger = logging.getLogger(__name__)

# Cosine similarity threshold for matching (configurable via config.json -> server.speaker_similarity_threshold).
# Tuned to 0.65: real enrollment audio is the short "my name is X" utterance (~1.5-2s), which yields a
# same-speaker self-similarity of only ~0.70-0.74 — the old 0.75 default NEVER matched returning guests
# (verified empirically). Observed different-speaker scores stay ~0.49-0.56, so 0.65 keeps a safe margin
# while making voice ID actually functional. Raise toward 0.72 if false matches appear at a noisy party.
SIMILARITY_THRESHOLD = 0.65
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "voices.db")

# Allow config.json to override threshold
_spk_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
if os.path.exists(_spk_config_path):
    try:
        import json as _json_mod
        with open(_spk_config_path, encoding="utf-8") as _f:
            _spk_cfg = _json_mod.load(_f).get("server", {})
            SIMILARITY_THRESHOLD = _spk_cfg.get("speaker_similarity_threshold", SIMILARITY_THRESHOLD)
    except Exception:
        pass

# Minimum RMS energy (int16 scale) for a chunk to count as speech. Below this the
# audio is treated as silence/noise: no embedding, no match, no enrollment (F5).
# Conservative default — only rejects near-silence; override via SPEAKER_MIN_RMS.
try:
    MIN_SPEECH_RMS = float(os.environ.get("SPEAKER_MIN_RMS", "120") or 120)
except (TypeError, ValueError):
    MIN_SPEECH_RMS = 120.0

_encoder = None


def _audio_rms(audio_data: bytes) -> float:
    """Root-mean-square amplitude of int16 PCM bytes (0.0 for empty/silent)."""
    if not audio_data:
        return 0.0
    samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float64)
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples * samples)))


def _has_speech_energy(audio_data: bytes, min_rms: float = None) -> bool:
    """True if the chunk is loud enough to plausibly contain speech (F5 gate)."""
    floor = MIN_SPEECH_RMS if min_rms is None else min_rms
    return _audio_rms(audio_data) >= floor


def spectral_flatness(samples: np.ndarray) -> float:
    """Wiener entropy: geometric mean / arithmetic mean of the magnitude spectrum.

    Near 1.0 for noise-like signals (white noise, room hiss, dense music), low for
    the peaky harmonic structure of speech. Costs one FFT and no embedding.
    """
    if samples is None or samples.size == 0:
        return 1.0
    windowed = samples.astype(np.float64) * np.hanning(len(samples))
    spectrum = np.abs(np.fft.rfft(windowed))
    spectrum = spectrum[spectrum > 1e-10]
    if spectrum.size == 0:
        return 1.0
    geometric = np.exp(np.mean(np.log(spectrum)))
    arithmetic = np.mean(spectrum)
    return float(geometric / arithmetic) if arithmetic > 0 else 1.0


def stage_a_ok(samples_int16: np.ndarray, min_rms: float = None,
               max_flatness: float = None) -> bool:
    """Cheap pre-embedding gate: enough speech energy, not noise-like.

    Splits the chunk into 3 windows. Requires at least 2 of 3 above the speech
    energy floor (rejects mostly-silent chunks) and a mean spectral flatness under
    the ceiling (rejects music and room noise). No embedding cost.
    """
    if samples_int16 is None or len(samples_int16) < 3:
        return False
    if max_flatness is None:
        max_flatness = recognition_config.get("voice_max_flatness")
    floor = MIN_SPEECH_RMS if min_rms is None else min_rms

    third = len(samples_int16) // 3
    windows = [samples_int16[i * third:(i + 1) * third] for i in range(3)]

    loud = 0
    for window in windows:
        vals = window.astype(np.float64)
        if vals.size and float(np.sqrt(np.mean(vals * vals))) >= floor:
            loud += 1
    if loud < 2:
        return False

    mean_flatness = float(np.mean([spectral_flatness(w.astype(np.float64)) for w in windows]))
    return mean_flatness <= max_flatness


def _average_embeddings(embeddings):
    """L2-normalized mean of several voice embeddings (multi-sample enrollment, F5).

    Averaging multiple clips into one print is far more robust than a single short
    utterance. Ignores None entries; returns None if nothing usable.
    """
    arr = [np.asarray(e, dtype=np.float64) for e in embeddings if e is not None]
    if not arr:
        return None
    mean = np.mean(arr, axis=0)
    norm = np.linalg.norm(mean)
    return mean / norm if norm > 0 else mean


def is_available() -> bool:
    """True if speaker identification (resemblyzer + encoder) is ready."""
    return _HAS_RESEMBLYZER and _encoder is not None


def init_speaker_id(collection_name: str = "mario_voices"):
    """Initialize the voice encoder and SQLite database.

    `collection_name` is retained for back-compat with existing callers; it is
    unused now that matching is SQLite-only.
    """
    global _encoder
    if not _HAS_RESEMBLYZER:
        logger.warning("[speaker_id] Skipping init — resemblyzer not installed")
        return
    if DEBUG_SPEAKER:
        logger.info("[DEBUG_SPEAKER] init_speaker_id: START")

    _encoder = VoiceEncoder("cpu")

    # Initialize SQLite database
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS speakers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                embedding BLOB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

    if DEBUG_SPEAKER:
        logger.info("[DEBUG_SPEAKER] init_speaker_id: END")


def get_embedding(audio_data: bytes, sample_rate: int = 16000) -> np.ndarray:
    """Extract voice embedding from audio data.

    Args:
        audio_data: Raw PCM int16 mono audio bytes
        sample_rate: Sample rate of the audio

    Returns:
        256-dimensional voice embedding vector
    """
    if _encoder is None:
        raise RuntimeError("Speaker ID not initialized. Call init_speaker_id() first.")

    # Reject near-silent / no-speech chunks before embedding (F5): a silent buffer
    # otherwise yields a meaningless embedding that pollutes matching and enrollment.
    if not _has_speech_energy(audio_data):
        if DEBUG_SPEAKER:
            logger.info(f"[DEBUG_SPEAKER] get_embedding: below speech-energy floor (rms={_audio_rms(audio_data):.0f})")
        return None

    audio_np = np.frombuffer(audio_data, dtype=np.int16)

    # Stage A (W6): no embedding cost — reject noise/music/mostly-silence outright.
    if not stage_a_ok(audio_np):
        if DEBUG_SPEAKER:
            logger.info("[DEBUG_SPEAKER] get_embedding: rejected by stage A (energy/flatness)")
        return None

    processed = preprocess_wav(audio_np.astype(np.float32) / 32768.0, source_sr=sample_rate)

    if len(processed) < sample_rate * 1.0:
        if DEBUG_SPEAKER:
            logger.info("[DEBUG_SPEAKER] get_embedding: audio too short for embedding")
        return None

    # Stage B (W6): two extra CPU embeddings. Halves, not thirds — resemblyzer's
    # partial-utterance window is 1.6s, so 1.0s thirds would be zero-padded and
    # noisy. Disagreement between halves means two speakers or heavy interference.
    half = len(processed) // 2
    first, second = processed[:half], processed[half:]
    if min(len(first), len(second)) >= sample_rate * 1.0:
        emb_a = _encoder.embed_utterance(first)
        emb_b = _encoder.embed_utterance(second)
        denominator = np.linalg.norm(emb_a) * np.linalg.norm(emb_b)
        if denominator > 0:
            agreement = float(np.dot(emb_a, emb_b) / denominator)
            tau = recognition_config.get("voice_consistency_tau")
            if agreement < tau:
                if DEBUG_SPEAKER:
                    logger.info(f"[DEBUG_SPEAKER] get_embedding: rejected by stage B "
                                f"(agreement {agreement:.3f} < {tau})")
                return None

    embedding = _encoder.embed_utterance(processed)
    if DEBUG_SPEAKER:
        logger.info(f"[DEBUG_SPEAKER] get_embedding: shape={embedding.shape}")
    return embedding


def identify_speaker(audio_data: bytes, sample_rate: int = 16000) -> dict:
    """Identify who is speaking from audio via a SQLite cosine-similarity scan.

    Returns:
        dict with 'name' (str or None), 'speaker_id' (int or None),
        'confidence' (float), 'is_new' (bool)
    """
    if not _HAS_RESEMBLYZER or _encoder is None:
        return {"name": None, "speaker_id": None, "confidence": 0.0, "is_new": True}
    if DEBUG_SPEAKER:
        logger.info("[DEBUG_SPEAKER] identify_speaker: START")

    try:
        embedding = get_embedding(audio_data, sample_rate)
    except (ValueError, RuntimeError) as e:
        logger.warning(f"[DEBUG_SPEAKER] identify_speaker: embedding failed: {e}")
        return {"name": None, "speaker_id": None, "confidence": 0.0, "is_new": True}
    if embedding is None:
        return {"name": None, "speaker_id": None, "confidence": 0.0, "is_new": True}

    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute("SELECT id, name, embedding FROM speakers")
        rows = cursor.fetchall()
    except Exception as e:
        logger.error(f"[DEBUG_SPEAKER] identify_speaker: DB error: {e}")
        return {"name": None, "speaker_id": None, "confidence": 0.0, "is_new": True}
    finally:
        conn.close()

    # W4: reduce to the BEST similarity per distinct NAME, not per row. The
    # `speakers` table can hold multiple rows for the same person — register_speaker
    # and register_speaker_multi each INSERT a new row, so a guest who enrolls twice
    # has two rows under one name. Ranking raw rows would make that guest's own
    # second print look like a competing runner-up and wrongly reject her own
    # match as ambiguous, so the reduction happens BEFORE ranking (mirrors
    # face_memory.find_match's per-person reduction).
    best_per_name = {}

    for row_id, name, emb_blob in rows:
        try:
            stored_embedding = np.frombuffer(emb_blob, dtype=np.float32)
            if stored_embedding.shape != embedding.shape:
                logger.warning(f"[DEBUG_SPEAKER] Shape mismatch for {name}: stored={stored_embedding.shape} vs current={embedding.shape}, skipping")
                continue
            norm_product = np.linalg.norm(embedding) * np.linalg.norm(stored_embedding)
            if norm_product == 0:
                continue
            similarity = np.dot(embedding, stored_embedding) / norm_product
        except Exception as e:
            logger.error(f"[DEBUG_SPEAKER] Error comparing embedding for {name}: {e}")
            continue
        if DEBUG_SPEAKER:
            logger.info(f"[DEBUG_SPEAKER] identify_speaker SQLite: {name} similarity={similarity:.3f}")

        current = best_per_name.get(name)
        if current is None or similarity > current[0]:
            best_per_name[name] = (similarity, row_id)

    ranked = sorted(best_per_name.items(), key=lambda kv: kv[1][0], reverse=True)
    best_similarity = ranked[0][1][0] if ranked else -1.0

    if ranked and best_similarity >= SIMILARITY_THRESHOLD:
        best_name, (_, best_row_id) = ranked[0]
        # W4: refuse an ambiguous call. Only DIFFERENT people compete — `ranked` is
        # already reduced to one entry per name, so two prints of the same
        # returning guest can never look like a tie.
        if len(ranked) >= 2:
            second_similarity = ranked[1][1][0]
            margin = recognition_config.get("voice_match_margin")
            if (best_similarity - second_similarity) < margin:
                if DEBUG_SPEAKER:
                    logger.info(f"[DEBUG_SPEAKER] ambiguous: {best_similarity:.3f} vs "
                                f"{second_similarity:.3f} (margin {margin}) — treating as new")
                return {"name": None, "speaker_id": None,
                        "confidence": float(best_similarity), "is_new": True}
        if DEBUG_SPEAKER:
            logger.info(f"[DEBUG_SPEAKER] matched {best_name} ({best_similarity:.3f})")
        return {
            "name": best_name,
            "speaker_id": best_row_id,
            "confidence": float(best_similarity),
            "is_new": False,
        }

    if DEBUG_SPEAKER:
        logger.info(f"[DEBUG_SPEAKER] identify_speaker: no match (best={best_similarity:.3f})")
    return {"name": None, "speaker_id": None, "confidence": float(best_similarity), "is_new": True}


def register_speaker(name: str, audio_data: bytes, sample_rate: int = 16000) -> int:
    """Register a new speaker's voice.

    Returns:
        The new speaker's database ID
    """
    if not _HAS_RESEMBLYZER or _encoder is None:
        raise ValueError("Speaker identification not available — resemblyzer not installed")
    if DEBUG_SPEAKER:
        logger.info(f"[DEBUG_SPEAKER] register_speaker: START name={name}")

    embedding = get_embedding(audio_data, sample_rate)
    if embedding is None:
        raise ValueError("Audio too short to create voice embedding")

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "INSERT INTO speakers (name, embedding) VALUES (?, ?)",
            (name, embedding.tobytes()),
        )
        speaker_id_val = cursor.lastrowid
        conn.commit()

    if DEBUG_SPEAKER:
        logger.info(f"[DEBUG_SPEAKER] register_speaker: END id={speaker_id_val}")
    return speaker_id_val


def register_speaker_multi(name: str, audio_chunks, sample_rate: int = 16000) -> int:
    """Enroll a speaker from MULTIPLE clips, storing their averaged embedding (F5).

    Far more robust than the single short "my name is X" utterance: averaging several
    clips cancels per-clip noise/variation, which lets matching survive party noise.
    Unusable / too-quiet clips are skipped. Raises ValueError if none are usable.
    """
    if not _HAS_RESEMBLYZER or _encoder is None:
        raise ValueError("Speaker identification not available — resemblyzer not installed")

    embeddings = []
    for chunk in audio_chunks:
        try:
            emb = get_embedding(chunk, sample_rate)
        except (ValueError, RuntimeError):
            emb = None
        if emb is not None:
            embeddings.append(emb)

    mean = _average_embeddings(embeddings)
    if mean is None:
        raise ValueError("No usable audio to create voice embedding (all clips empty/too quiet)")

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "INSERT INTO speakers (name, embedding) VALUES (?, ?)",
            (name, mean.astype(np.float32).tobytes()),
        )
        speaker_id_val = cursor.lastrowid
        conn.commit()

    if DEBUG_SPEAKER:
        logger.info(f"[DEBUG_SPEAKER] register_speaker_multi: id={speaker_id_val} from {len(embeddings)} clips")
    return speaker_id_val


def update_speaker(speaker_id_val: int, audio_data: bytes, sample_rate: int = 16000):
    """Update an existing speaker's voice embedding with blended new audio (EMA)."""
    if DEBUG_SPEAKER:
        logger.info(f"[DEBUG_SPEAKER] update_speaker: START id={speaker_id_val}")

    new_embedding = get_embedding(audio_data, sample_rate)
    if new_embedding is None:
        raise ValueError("Audio too short to update voice embedding")

    # Blend with existing embedding using exponential moving average (80% old, 20% new)
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT embedding FROM speakers WHERE id = ?", (speaker_id_val,)).fetchone()
        if row:
            old_embedding = np.frombuffer(row[0], dtype=np.float32)
            blended = 0.8 * old_embedding + 0.2 * new_embedding
            blended = blended / np.linalg.norm(blended)  # Re-normalize
            conn.execute(
                "UPDATE speakers SET embedding = ? WHERE id = ?",
                (blended.tobytes(), speaker_id_val),
            )
        else:
            conn.execute(
                "UPDATE speakers SET embedding = ? WHERE id = ?",
                (new_embedding.tobytes(), speaker_id_val),
            )
        conn.commit()

    if DEBUG_SPEAKER:
        logger.info(f"[DEBUG_SPEAKER] update_speaker: END id={speaker_id_val} (blended)")


def delete_speaker(speaker_id_val: int):
    """Delete a speaker's voice data for privacy."""
    if DEBUG_SPEAKER:
        logger.info(f"[DEBUG_SPEAKER] delete_speaker: START id={speaker_id_val}")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM speakers WHERE id = ?", (speaker_id_val,))
        conn.commit()

    if DEBUG_SPEAKER:
        logger.info(f"[DEBUG_SPEAKER] delete_speaker: END id={speaker_id_val}")


def list_speakers() -> list:
    """List all registered speakers (name + id, no embeddings)."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute("SELECT id, name FROM speakers ORDER BY id").fetchall()
            return [{"id": r[0], "name": r[1]} for r in rows]
    except Exception as e:
        logger.error(f"list_speakers failed: {e}")
        return []
