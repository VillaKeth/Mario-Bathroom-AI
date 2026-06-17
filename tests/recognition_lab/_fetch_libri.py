"""Download LibriSpeech test-clean (real multi-speaker audio) via torchaudio.
~340MB one-time. Lands in tests/recognition_lab/_corpus/ (gitignored)."""
import os
import torchaudio

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_corpus")
os.makedirs(ROOT, exist_ok=True)
print(f"Downloading LibriSpeech test-clean to {ROOT} ...")
ds = torchaudio.datasets.LIBRISPEECH(ROOT, url="test-clean", download=True)
print(f"LIBRI READY: {len(ds)} utterances")
