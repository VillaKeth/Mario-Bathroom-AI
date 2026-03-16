"""Measure end-to-end latency for Mario AI pipeline."""
import time
import requests

BASE = "http://localhost:8765"

def test_cached_tts():
    t0 = time.time()
    r = requests.get(f"{BASE}/tts", params={"text": "It's-a me, Mario!"})
    elapsed = time.time() - t0
    print(f"[Cached TTS]  {elapsed:.2f}s  (status={r.status_code}, {len(r.content)} bytes)")
    return elapsed

def test_novel_tts():
    t0 = time.time()
    r = requests.get(f"{BASE}/tts", params={
        "text": "Hey there friend, welcome to the bathroom party!",
        "nocache": "1"
    })
    elapsed = time.time() - t0
    print(f"[Novel TTS]   {elapsed:.2f}s  (status={r.status_code}, {len(r.content)} bytes)")
    return elapsed

def test_llm_only():
    """Test LLM response time via Ollama directly."""
    try:
        t0 = time.time()
        r = requests.post("http://localhost:11434/api/generate", json={
            "model": "llama3",
            "prompt": "You are Mario. Tell me a short joke about the bathroom.",
            "stream": False,
            "options": {"num_predict": 35}
        }, timeout=30)
        elapsed = time.time() - t0
        data = r.json()
        resp = data.get("response", "")[:100]
        print(f"[LLM Only]    {elapsed:.2f}s  -> {resp}")
        return elapsed
    except Exception as e:
        print(f"[LLM Only]    FAILED: {e}")
        return -1

def test_chat_endpoint():
    """Test full pipeline: text -> LLM -> TTS -> audio."""
    t0 = time.time()
    r = requests.post(f"{BASE}/chat", json={
        "text": "Hey Mario, tell me a joke!",
        "speaker_id": "latency_test"
    }, timeout=60)
    elapsed = time.time() - t0
    if r.status_code == 200:
        data = r.json()
        text = data.get("text", "")[:100]
        has_audio = "audio" in data or "audio_url" in data
        print(f"[Full Chat]   {elapsed:.2f}s  audio={has_audio}  -> {text}")
    else:
        print(f"[Full Chat]   {elapsed:.2f}s  status={r.status_code}")
    return elapsed

def test_health():
    t0 = time.time()
    r = requests.get(f"{BASE}/health")
    elapsed = time.time() - t0
    data = r.json()
    print(f"[Health]      {elapsed:.2f}s  status={data.get('status')}")
    return elapsed

if __name__ == "__main__":
    print("=" * 60)
    print("Mario AI Latency Test")
    print("=" * 60)
    
    test_health()
    print()
    
    # Run each test 2 times
    for i in range(2):
        print(f"--- Run {i+1} ---")
        test_cached_tts()
        test_novel_tts()
        test_llm_only()
        test_chat_endpoint()
        print()
    
    print("Done!")
