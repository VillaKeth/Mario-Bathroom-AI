"""Create placeholder sprites for characters that don't have AI-generated poses yet."""
from PIL import Image, ImageDraw, ImageFont
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))

def create_placeholder(path, text, bg_color, text_color='white'):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img = Image.new('RGBA', (250, 250), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([25, 25, 225, 225], fill=bg_color)
    try:
        font = ImageFont.truetype('arial.ttf', 14)
    except Exception:
        font = ImageFont.load_default()
    lines = text.split('\n')
    y_offset = 110
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((250 - tw) // 2, y_offset), line, fill=text_color, font=font)
        y_offset += 20
    img.save(path, 'PNG')

RUDI_POSES = {
    'neutral/idle': '#7B2FBE', 'positive/smirk': '#00D4FF', 'positive/hyped': '#00D4FF',
    'positive/cracking_up': '#00D4FF', 'positive/charmed': '#00D4FF', 'positive/confident': '#00D4FF',
    'negative/unimpressed': '#FF3366', 'negative/disappointed': '#FF3366', 'negative/facepalm': '#FF3366',
    'negative/grossed_out': '#FF3366', 'negative/fired_up': '#FF3366', 'negative/uneasy': '#FF3366',
    'negative/startled': '#FF3366', 'negative/flustered': '#FF3366',
    'thinking/pondering': '#7B2FBE', 'thinking/questioning': '#7B2FBE', 'thinking/scheming': '#7B2FBE',
    'thinking/focused': '#7B2FBE', 'thinking/intrigued': '#7B2FBE', 'thinking/lightbulb': '#7B2FBE',
    'speech/talking': '#00D4FF', 'speech/explaining': '#00D4FF', 'speech/listening': '#00D4FF',
    'greeting/casual_wave': '#7B2FBE', 'greeting/peace_out': '#7B2FBE',
    'reactions/double_take': '#FF3366', 'reactions/jaw_drop': '#FF3366', 'reactions/mind_blown': '#FF3366',
    'reactions/sassy': '#FF3366', 'reactions/cringe': '#FF3366', 'reactions/impressed': '#00D4FF',
    'sleep/bored_yawn': '#1A1A2E', 'sleep/powered_down': '#1A1A2E',
    'movement/vibing': '#7B2FBE', 'movement/arriving': '#7B2FBE',
    'party/celebrate': '#FF3366', 'party/birthday': '#FF3366',
    'toast/raising_glass': '#7B2FBE', 'memorial/respectful': '#1A1A2E',
}

SONIC_POSES = {
    'neutral/idle': '#1E90FF', 'positive/thumbs_up': '#FFD700', 'positive/hyped': '#FFD700',
    'positive/cracking_up': '#FFD700', 'positive/charmed': '#FFD700', 'positive/confident': '#FFD700',
    'negative/impatient': '#DC143C', 'negative/bummed': '#DC143C', 'negative/grossed_out': '#DC143C',
    'negative/fired_up': '#DC143C', 'negative/uneasy': '#DC143C', 'negative/startled': '#DC143C',
    'negative/flustered': '#DC143C',
    'thinking/pondering': '#1E90FF', 'thinking/head_scratch': '#1E90FF', 'thinking/smirk': '#1E90FF',
    'thinking/focused': '#1E90FF', 'thinking/intrigued': '#1E90FF', 'thinking/lightbulb': '#1E90FF',
    'speech/talking': '#FFD700', 'speech/explaining': '#FFD700', 'speech/listening': '#FFD700',
    'greeting/wave': '#1E90FF', 'greeting/peace_out': '#1E90FF',
    'reactions/double_take': '#DC143C', 'reactions/jaw_drop': '#DC143C', 'reactions/mind_blown': '#DC143C',
    'reactions/sassy': '#DC143C', 'reactions/cringe': '#DC143C', 'reactions/impressed': '#FFD700',
    'sleep/dozing': '#191970', 'sleep/impatient': '#191970',
    'movement/running': '#1E90FF', 'movement/speed_entry': '#1E90FF',
    'party/celebrate': '#FFD700', 'party/birthday': '#FFD700',
    'toast/raising_glass': '#1E90FF', 'memorial/respectful': '#191970',
}

if __name__ == "__main__":
    for pose, color in RUDI_POSES.items():
        path = os.path.join(PROJECT_ROOT, 'characters', 'rudi', 'sprites', f'{pose}.png')
        label = pose.split('/')[-1].replace('_', ' ')
        create_placeholder(path, f'RUDI\n{label}', color)

    for pose, color in SONIC_POSES.items():
        path = os.path.join(PROJECT_ROOT, 'characters', 'sonic', 'sprites', f'{pose}.png')
        label = pose.split('/')[-1].replace('_', ' ')
        create_placeholder(path, f'SONIC\n{label}', color)

    print(f'Created {len(RUDI_POSES)} Rudi + {len(SONIC_POSES)} Sonic placeholder sprites')
