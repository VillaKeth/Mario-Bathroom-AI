"""End-to-end quality and latency test for Mario AI."""
import time
import requests
import httpx

SERVER = "http://localhost:8765"

def test_health():
    print("=== TEST 1: Server Health ===")
    t0 = time.time()
    r = requests.get(f"{SERVER}/health")
    h = r.json()
    print(f"  Status: {h['status']} ({time.time()-t0:.1f}s)")
    print(f"  TTS: {h.get('tts_engine', '?')}")
    print(f"  Precache: {h.get('precache_done', '?')}")

def test_cached_tts():
    print("\n=== TEST 2: Cached TTS Latency ===")
    phrases = ["It's-a me, Mario!", "Wahoo!", "Mama mia!", "Hello there!", "Welcome, welcome!"]
    for phrase in phrases:
        t0 = time.time()
        r = requests.get(f"{SERVER}/tts", params={"text": phrase})
        lat = time.time() - t0
        size = len(r.content) if r.status_code == 200 else 0
        status = "OK" if size > 100 else "EMPTY"
        print(f"  [{status}] \"{phrase}\" -> {lat*1000:.0f}ms, {size:,} bytes")

def test_live_tts():
    print("\n=== TEST 3: Live TTS Generation ===")
    phrases = [
        "Hey there, how are you doing tonight?",
        "That's a really great question, let me think about it!",
        "Welcome to the party, have a wonderful time!",
    ]
    for phrase in phrases:
        t0 = time.time()
        r = requests.get(f"{SERVER}/tts", params={"text": phrase, "nocache": 1})
        lat = time.time() - t0
        size = len(r.content) if r.status_code == 200 else 0
        status = "OK" if size > 100 else "EMPTY"
        print(f"  [{status}] \"{phrase[:45]}\" -> {lat:.1f}s, {size:,} bytes")

def test_llm():
    print("\n=== TEST 4: LLM Response Quality ===")
    prompts = [
        "Tell me a joke about being in the bathroom",
        "What do you think about pineapple on pizza?",
        "I just got here, what should I do?",
    ]
    for prompt in prompts:
        t0 = time.time()
        r = httpx.post("http://localhost:11434/api/generate", json={
            "model": "llama3",
            "prompt": f"You are Mario from Nintendo. Stay in character. Keep response under 25 words. User says: {prompt}",
            "stream": False,
            "options": {"num_predict": 35, "temperature": 0.8}
        }, timeout=30)
        lat = time.time() - t0
        resp = r.json().get("response", "?").strip()
        print(f"  [{lat:.1f}s] Q: \"{prompt}\"")
        print(f"         A: \"{resp[:80]}\"")
        print()

def test_full_pipeline():
    print("=== TEST 5: Full Pipeline (LLM + TTS) ===")
    prompts = [
        "Hey Mario, tell me something funny!",
        "What's your favorite food?",
    ]
    for prompt in prompts:
        t0 = time.time()
        # LLM
        r = httpx.post("http://localhost:11434/api/generate", json={
            "model": "llama3",
            "prompt": f"You are Mario from Nintendo. Stay in character. Keep response under 25 words. User says: {prompt}",
            "stream": False,
            "options": {"num_predict": 35, "temperature": 0.8}
        }, timeout=30)
        llm_time = time.time() - t0
        resp = r.json().get("response", "").strip()

        # TTS
        t1 = time.time()
        r2 = requests.get(f"{SERVER}/tts", params={"text": resp})
        tts_time = time.time() - t1
        total = time.time() - t0
        size = len(r2.content) if r2.status_code == 200 else 0

        print(f"  Q: \"{prompt}\"")
        print(f"  A: \"{resp[:80]}\"")
        print(f"  LLM: {llm_time:.1f}s | TTS: {tts_time:.1f}s | Total: {total:.1f}s | Audio: {size:,} bytes")
        print()

if __name__ == "__main__":
    test_health()
    test_cached_tts()
    test_live_tts()
    test_llm()
    test_full_pipeline()
    print("=== ALL TESTS COMPLETE ===")
