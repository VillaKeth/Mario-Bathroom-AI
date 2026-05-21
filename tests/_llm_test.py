"""Direct test of LLM + emotion extraction."""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

import httpx

async def main():
    # Test LLM directly via Ollama
    print("=== Direct Ollama LLM Test ===\n")
    
    prompt = """You are Mario from Nintendo at a bathroom party. Keep responses short and fun.

IMPORTANT: End every response with a JSON line on its own:
{"emotion": "<one of: happy, excited, surprised, confused, annoyed, sleepy, mischievous, laughing, sad, angry, nervous, scared, love, loving, proud, embarrassed, disgusted, determined, bored, worried, curious, thinking, shocked, idea, frustrated, neutral>", "energy": <0.0-1.0>}

Choose emotion based on your current mood and energy based on how animated/energetic you feel."""

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": "Tell me about your favorite pasta dish!"}
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post("http://localhost:11434/api/chat", json={
            "model": "llama3",
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.8, "num_ctx": 4096}
        })
        data = r.json()
        raw_response = data.get("message", {}).get("content", "")
        print(f"RAW LLM RESPONSE:\n{raw_response}\n")
        print(f"---")
        
        # Now test emotion extraction
        from emotions import extract_emotion_tag
        result = extract_emotion_tag(raw_response)
        print(f"Extracted emotion: {result['emotion']}")
        print(f"Extracted energy: {result['energy']}")
        print(f"Clean text: {result['clean_text']}")
    
    # Test 2: Negative prompt
    print("\n\n=== Test 2: Negative Prompt ===\n")
    messages2 = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": "You're so annoying and stupid, nobody likes you!"}
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post("http://localhost:11434/api/chat", json={
            "model": "llama3",
            "messages": messages2,
            "stream": False,
            "options": {"temperature": 0.8, "num_ctx": 4096}
        })
        data = r.json()
        raw_response = data.get("message", {}).get("content", "")
        print(f"RAW LLM RESPONSE:\n{raw_response}\n")
        
        result = extract_emotion_tag(raw_response)
        print(f"Extracted emotion: {result['emotion']}")
        print(f"Extracted energy: {result['energy']}")

if __name__ == "__main__":
    asyncio.run(main())
