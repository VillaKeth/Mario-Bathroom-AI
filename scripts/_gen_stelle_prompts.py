"""One-off: write characters/stelle/sprite_prompts.txt for GPT (ChatGPT) — clean
portrait Stelle, NO gold/fire energy splash, NO ribbon trail, just her alone.
Run: venv/Scripts/python.exe scripts/_gen_stelle_prompts.py  (then delete)
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "characters" / "stelle" / "sprite_prompts.txt"

# Wiki-accurate + reference-verified (characters/stelle/stelle_ref.png). NO gold warp
# ribbon / energy trail (user: "none of the nonsense with the fire splash background").
DESC = (
    "Stelle, the female Trailblazer from Honkai Star Rail, a cool casual young woman rendered in "
    "the official Honkai Star Rail / HoYoverse anime splash-art style: realistic slender "
    "well-proportioned tall anime figure with a normal adult head-to-body ratio, NOT chibi, NOT "
    "super-deformed, NOT a child, NOT big-headed. Medium-length silvery-gray hair flowing loosely "
    "down past her shoulders, sleepy half-lidded golden-amber eyes, a calm cool casual expression. "
    "She wears a white inner shirt under an OPEN black short-sleeved trench coat with gold-yellow "
    "trim and lining, a black tight short skirt, a light-blue garter strap on her left thigh, black "
    "gloves, and dark heeled ankle boots. Casual cool aesthetic. ONLY Stelle, a single character "
    "alone."
)
TAIL = (
    ", detailed soft cel-shading, refined glossy gacha splash-art rendering, crisp clean lineart, "
    "full body shot, entire character fully visible from head to toe, centered composition, generous "
    "empty margin around the character, standing in frame, nothing cropped or cut off at the edges. "
    "PLAIN SOLID WHITE studio background. Absolutely NO background scenery, NO glowing energy, NO "
    "fire, NO flames, NO swirling light trails or ribbons, NO sparkles or magic effects, NO second "
    "person - just Stelle standing alone on a clean empty white background."
)

POSES = [
    ("sprites/positive/happy.png", "with a warm genuine smile, arms open, welcoming happy pose"),
    ("sprites/positive/excited.png", "jumping with excitement, fist pumped, huge grin"),
    ("sprites/positive/laughing.png", "laughing, head tilted back, genuine amusement"),
    ("sprites/positive/love.png", "with heart eyes, hands clasped near her face, love-struck expression"),
    ("sprites/positive/proud.png", "standing tall, hands on hips, chin up, supremely confident proud pose"),
    ("sprites/negative/sad.png", "looking down sadly, shoulders slumped, disappointed expression"),
    ("sprites/negative/angry.png", "with an intense angry expression, fists clenched, leaning forward"),
    ("sprites/negative/annoyed.png", "with arms crossed, one eyebrow raised, clearly unimpressed look"),
    ("sprites/negative/nervous.png", "looking nervously to the side, hands fidgeting, uncertain expression"),
    ("sprites/negative/scared.png", "stepping back with wide eyes, hands up, startled and scared"),
    ("sprites/negative/embarrassed.png", "one hand to her cheek, looking away with an embarrassed flush"),
    ("sprites/negative/disgusted.png", "leaning away with a disgusted face, hand up in a stop gesture"),
    ("sprites/thinking/confused.png", "head tilted, confused expression, one eyebrow raised"),
    ("sprites/thinking/thinking.png", "looking upward thoughtfully, finger to chin, pondering"),
    ("sprites/thinking/curious.png", "leaning forward with curiosity, eyes bright, interested expression"),
    ("sprites/thinking/determined.png", "intense focused eyes, determined expression, leaning forward"),
    ("sprites/thinking/mischievous.png", "a mischievous smirk, fingers steepled, plotting look"),
    ("sprites/thinking/shocked.png", "mouth open in shock, eyes wide, absolutely stunned"),
    ("sprites/thinking/idea.png", "one index finger raised, bright idea moment, eyes lit up"),
    ("sprites/reactions/mind_blown.png", "hands at the sides of her head, amazed mind-blown expression"),
    ("sprites/reactions/sassy.png", "one hand on hip, head tilted, sassy confident attitude"),
    ("sprites/reactions/cringe.png", "cringing, one eye shut, teeth gritted, looking away"),
    ("sprites/reactions/impressed.png", "nodding approvingly, arms crossed, eyebrow raised in genuine respect"),
    ("sprites/sleep/sleepy.png", "mid-yawn, one hand covering her mouth, half-closed sleepy eyes"),
    ("sprites/neutral/idle.png", "standing relaxed in a casual confident stance, neutral expression"),
    ("sprites/memorial/moment_of_silence.png", "head bowed, one hand over her heart, solemn respectful pose"),
    ("sprites/toast/raising_glass.png", "raising a glass high, confident smile, toasting"),
    ("sprites/party/celebrate.png", "raising both arms in celebration, big grin"),
    ("sprites/birthday/birthday.png", "holding a birthday cake with lit candles, warm smile"),
    ("sprites/speech/talking.png", "gesturing with one hand while speaking, animated expression"),
    ("sprites/speech/talking_excited.png", "gesturing enthusiastically with both hands, excited while talking"),
    ("sprites/speech/listening.png", "head slightly tilted, attentive listening pose"),
    ("sprites/greeting/wave.png", "waving hello with a warm smile, welcoming gesture"),
    ("sprites/sleep/sleeping.png", "curled up asleep, peaceful expression, eyes closed"),
    ("sprites/movement/dancing.png", "mid dance move, energetic and graceful"),
    ("sprites/movement/entering.png", "walking in confidently, a dramatic entrance"),
    ("sprites/greeting/farewell.png", "waving goodbye, glancing back with a smile"),
]

HEADER = (
    "# Sprite prompts for stelle (mcp_chatgpt batch [NN] format) - GPT/ChatGPT, clean portrait.\n"
    "# NO gold warp ribbon / fire / energy splash; plain white bg, single character.\n"
    "# Run: mcp_chatgpt/batch_sprites.py --character stelle --regen --accounts work,default,acct3,acct4,acct5\n"
)

lines = [HEADER]
for i, (rel, pose) in enumerate(POSES, 1):
    lines.append(f"[{i:02d}] {rel}\n" + "-" * 70 + "\n" + f"{DESC} {pose}{TAIL}\n")
OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"wrote {OUT} with {len(POSES)} blocks")
