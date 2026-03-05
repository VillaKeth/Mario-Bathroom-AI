"""Test free AI image generation APIs."""
import requests
import time
import os

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'mario_3d_assets')

def test_huggingface():
    """Try HuggingFace free inference API (no key for some models)."""
    API_URL = 'https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0'
    payload = {
        'inputs': 'Super Mario character, 3D render, standing pose, white background, Nintendo style, high quality'
    }
    print('Testing HuggingFace SDXL...')
    start = time.time()
    try:
        resp = requests.post(API_URL, json=payload, timeout=120)
        elapsed = time.time() - start
        print(f'  Status: {resp.status_code}, Size: {len(resp.content)}, Time: {elapsed:.1f}s')
        if resp.status_code == 200 and len(resp.content) > 1000:
            path = os.path.join(OUTPUT_DIR, 'test_hf_sdxl.png')
            with open(path, 'wb') as f:
                f.write(resp.content)
            print(f'  SUCCESS: Saved to {path}')
            return True
        else:
            print(f'  Response: {resp.text[:300]}')
    except Exception as e:
        print(f'  Error: {e}')
    return False

def test_huggingface_flux():
    """Try HuggingFace free inference with FLUX model."""
    API_URL = 'https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell'
    payload = {
        'inputs': 'Super Mario character from Nintendo, 3D render, expressive pose, clean white background'
    }
    print('Testing HuggingFace FLUX.1-schnell...')
    start = time.time()
    try:
        resp = requests.post(API_URL, json=payload, timeout=120)
        elapsed = time.time() - start
        print(f'  Status: {resp.status_code}, Size: {len(resp.content)}, Time: {elapsed:.1f}s')
        if resp.status_code == 200 and len(resp.content) > 1000:
            path = os.path.join(OUTPUT_DIR, 'test_hf_flux.png')
            with open(path, 'wb') as f:
                f.write(resp.content)
            print(f'  SUCCESS: Saved to {path}')
            return True
        else:
            print(f'  Response: {resp.text[:300]}')
    except Exception as e:
        print(f'  Error: {e}')
    return False

def test_puter_browser():
    """Test if Puter.js works (browser-only, just check availability)."""
    print('Testing Puter.js availability...')
    try:
        resp = requests.get('https://js.puter.com/v2/', timeout=10)
        print(f'  Puter.js CDN Status: {resp.status_code}, Size: {len(resp.content)}')
        if resp.status_code == 200:
            print('  Puter.js is available — we can use it via browser!')
            return True
    except Exception as e:
        print(f'  Error: {e}')
    return False

def test_together_free():
    """Test Together AI free tier (no key for playground)."""
    print('Testing Together AI...')
    try:
        API_URL = 'https://api.together.xyz/v1/images/generations'
        payload = {
            'model': 'black-forest-labs/FLUX.1-schnell-Free',
            'prompt': 'Super Mario character, 3D render, expressive happy pose',
            'width': 512,
            'height': 512,
            'steps': 4,
            'n': 1
        }
        resp = requests.post(API_URL, json=payload, timeout=60)
        print(f'  Status: {resp.status_code}')
        print(f'  Response: {resp.text[:300]}')
    except Exception as e:
        print(f'  Error: {e}')
    return False

if __name__ == '__main__':
    print("=" * 60)
    print("TESTING FREE AI IMAGE GENERATION APIS")
    print("=" * 60)
    
    results = {}
    results['huggingface_sdxl'] = test_huggingface()
    print()
    results['huggingface_flux'] = test_huggingface_flux()
    print()
    results['puter_js'] = test_puter_browser()
    print()
    results['together_ai'] = test_together_free()
    
    print("\n" + "=" * 60)
    print("RESULTS:")
    for name, ok in results.items():
        print(f"  {name}: {'✓ WORKS' if ok else '✗ FAILED'}")
    print("=" * 60)
