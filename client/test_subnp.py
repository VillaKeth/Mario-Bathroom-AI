"""Test SubNP free image generation API."""
import requests
import time
import json

MODELS = ['flux-schnell', 'flux', 'magic']

for model in MODELS:
    print(f"\n--- Testing model: {model} ---")
    try:
        resp = requests.post(
            'https://subnp.com/api/free/generate',
            json={
                'prompt': 'Super Mario Nintendo character standing pose 3D render white background',
                'model': model
            },
            timeout=120,
            stream=True
        )
        print(f'Status: {resp.status_code}')
        for line in resp.iter_lines(decode_unicode=True):
            if line and line.startswith('data:'):
                data = json.loads(line[5:].strip())
                status = data.get('status', '?')
                print(f'  Status: {status}')
                
                # Check for image URL in various possible fields
                img_url = data.get('image_url') or data.get('url') or data.get('imageUrl')
                if img_url:
                    print(f'  Image URL: {img_url}')
                    img = requests.get(img_url, timeout=30)
                    if img.status_code == 200 and len(img.content) > 1000:
                        path = f'mario_3d_assets/test_subnp_{model}.png'
                        with open(path, 'wb') as f:
                            f.write(img.content)
                        print(f'  SAVED: {path} ({len(img.content)} bytes)')
                    else:
                        print(f'  Download failed: {img.status_code}')
                elif data.get('error') or data.get('message'):
                    msg = data.get('error') or data.get('message')
                    print(f'  Message: {msg}')
                    
                # Print raw data for debugging
                if 'image' in str(data).lower() or 'url' in str(data).lower() or 'result' in str(data).lower():
                    print(f'  Raw: {json.dumps(data)[:300]}')
                    
    except Exception as e:
        print(f'  Error: {e}')
    
    print()
