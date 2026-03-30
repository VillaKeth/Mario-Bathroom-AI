"""Check if PANNs is loaded on the running server by examining startup behavior."""
import requests
import json

# Check health
r = requests.get("http://localhost:8765/health")
data = r.json()
print("Server health keys:", sorted(data.keys()))
print(f"Status: {data['status']}")
print(f"LLM model: {data.get('llm_model')}")

# Check if there's a debug/config endpoint
for endpoint in ["/stats", "/config"]:
    try:
        r = requests.get(f"http://localhost:8765{endpoint}", timeout=3)
        if r.status_code == 200:
            d = r.json()
            # Look for audio_distress info
            for k, v in d.items():
                if "audio" in str(k).lower() or "distress" in str(k).lower() or "panns" in str(k).lower():
                    print(f"  {endpoint} -> {k}: {v}")
    except Exception as e:
        pass

print("\nTo verify PANNs on server, we need real retching audio.")
print("Synthetic and TTS audio are classified as Music/Speech by PANNs.")
print("The model needs REAL human vomiting/gagging recordings.")
