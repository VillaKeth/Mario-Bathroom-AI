import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
from audio_distress import init_detector, is_available, detect_distress

print("Loading PANNs model...")
init_detector(device="cpu")
print(f"PANNs available: {is_available()}")

if is_available():
    raw_path = os.path.join(os.path.dirname(__file__), "test_retch_raw.pcm")
    with open(raw_path, "rb") as f:
        audio_bytes = f.read()
    print(f"\nTesting synthetic audio: {len(audio_bytes)} bytes")
    result = detect_distress(audio_bytes, sample_rate=16000)
    print(f"  is_distress: {result['is_distress']}")
    print(f"  confidence:  {result['confidence']:.3f}")
    print(f"  speech_score: {result.get('speech_score', 'N/A')}")
    if result.get('top_classes'):
        print(f"  Top 15 classes:")
        for name, score in result['top_classes'][:15]:
            print(f"    {name}: {score:.4f}")
    if result.get('distress_classes'):
        print(f"  Distress classes triggered:")
        for name, score in result['distress_classes']:
            print(f"    {name}: {score:.4f}")
