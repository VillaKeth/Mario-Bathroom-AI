import requests, json

resp = requests.post('http://localhost:8766/api/content/generate', json={
    'character_name': 'Reze',
    'description': 'Reze is the Bomb Devil hybrid from Chainsaw Man. She appears as a sweet, kind cafe worker who befriends Denji, but is actually a trained Soviet assassin. She is playful, flirty, and manipulative, yet genuinely develops feelings.',
    'personality': 'Playful, flirty, and mysterious with a hint of danger. Sweet on the surface with dark humor underneath.',
    'char_dir': r'C:\Users\Vketh\Desktop\Mario_AI\characters\reze',
    'categories': ['idle', 'games', 'extras']
}, stream=True)

count = 0
for line in resp.iter_lines():
    if line:
        decoded = line.decode()
        if decoded.startswith('data:'):
            data = json.loads(decoded[5:].strip())
            if data.get('type') in ('pool_done', 'complete', 'error'):
                count += 1
                print(f"{data['type']}: {data.get('data',{}).get('current_pool','')} ({data.get('data',{}).get('percent',0)}%)")
                if data['type'] == 'complete':
                    break
                if count > 45:
                    break
