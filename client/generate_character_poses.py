"""
Universal Character Pose Generator
Generates sprite poses for any character using SubNP free API or DALL-E.
Automatically removes backgrounds with rembg.

Usage:
    python generate_character_poses.py --character rudi
    python generate_character_poses.py --character sonic --category party
    python generate_character_poses.py --character rudi --dalle
    python generate_character_poses.py --character sonic --list
"""
import requests
import json
import time
import os
import sys
import argparse
from io import BytesIO

DEBUG_GEN = True

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))

API_URL = "https://subnp.com/api/free/generate"
MODEL = "magic"

# Character-specific style suffixes
CHARACTER_STYLES = {
    "rudi": (
        "A cute 3D animated orange red panda character named Rudi with big blue eyes, "
        "small rounded ears with white inner ear markings, a tuft of orange hair on top, "
        "brown facial markings, a small smile showing one tooth, wearing a pink/red hoodie "
        "and dark navy shorts, short stubby orange paws with no shoes, chubby adorable proportions"
    ),
    "sonic": (
        "Sonic the Hedgehog, 3D rendered modern design, blue anthropomorphic hedgehog "
        "with large swept-back blue quills, green eyes, tan/peach muzzle and belly, "
        "small black nose, brown inner ears, wearing white gloves with sock cuffs, "
        "and iconic red shoes with white straps and gold buckles"
    ),
    "ani": (
        "A warm, elegant humanoid AI character named Ani with flowing pastel pink "
        "and lavender hair, soft golden glowing accents, kind expressive eyes, "
        "modern ethereal aesthetic, gentle features with genuine warmth"
    ),
    "pomni": (
        "Pomni from The Amazing Digital Circus, 3D animated style, short female jester character "
        "with a tall red and blue two-pointed jester hat with yellow bells, large expressive eyes "
        "with different colored irises (one red, one blue), pale white skin, small round head, "
        "wearing a red and blue checkered jester outfit with yellow buttons down the center, "
        "white collar, simple stick-like limbs, cartoonish proportions, anxious nervous expression"
    ),
    # ── Honkai: Star Rail Characters ──
    "stelle": (
        "Stelle from Honkai Star Rail, 3D anime style, young woman with short messy silver-white hair "
        "with pink gradient tips, bright amber-orange eyes, small frame, wearing a cropped dark vest "
        "with star emblem over white shirt, dark pleated skirt, tall dark boots, carrying a baseball bat"
    ),
    "march7th": (
        "March 7th from Honkai Star Rail, 3D anime style, cheerful young woman with long flowing pink hair "
        "with ice crystal hair ornaments, bright blue eyes, wearing a white and ice-blue outfit with ribbons "
        "and bow details, energetic bubbly appearance, carries an ice bow and a camera"
    ),
    "danheng": (
        "Dan Heng from Honkai Star Rail, 3D anime style, calm young man with long black hair tied in "
        "a low ponytail with teal streaks, teal eyes, reserved expression, wearing a dark teal and black "
        "form-fitting outfit with dragon motifs, carries a jade spear"
    ),
    "himeko": (
        "Himeko from Honkai Star Rail, 3D anime style, elegant mature woman with long wavy crimson red hair, "
        "red eyes, wearing a long dark professional coat with red accents over a white blouse, sophisticated "
        "appearance, carries a flaming sword"
    ),
    "welt": (
        "Welt Yang from Honkai Star Rail, 3D anime style, mature gentleman with dark brown hair slicked back, "
        "wearing glasses, brown eyes, wearing a long dark trenchcoat over formal clothes, carries a cane, "
        "dignified intellectual appearance"
    ),
    "kafka": (
        "Kafka from Honkai Star Rail, 3D anime style, mysterious woman with purple-lilac hair covering one eye, "
        "one visible purple eye, wearing a dark purple-black bodysuit with revealing cut, silver earrings, "
        "seductive confident appearance, carries a pistol"
    ),
    "silverwolf": (
        "Silver Wolf from Honkai Star Rail, 3D anime style, young woman with short messy blue-purple hair "
        "with long side bangs, green eyes, wearing a dark hoodie with digital circuit patterns and headphones, "
        "tech gamer aesthetic, carries a handheld gaming device"
    ),
    "seele": (
        "Seele from Honkai Star Rail, 3D anime style, young woman with long purple-blue hair, purple eyes, "
        "wearing a dark purple and white dress with butterfly wing motifs, delicate but fierce appearance, "
        "carries a large scythe"
    ),
    "blade_hsr": (
        "Blade from Honkai Star Rail, 3D anime style, brooding man with long flowing dark black hair, "
        "red eyes, visible scars on skin, wearing a dark tattered robe, intense dangerous appearance, "
        "carries a broken cursed sword"
    ),
    "jingyuan": (
        "Jing Yuan from Honkai Star Rail, 3D anime style, regal man with long flowing white-blonde hair, "
        "golden eyes, wearing ornate golden and white general's robes with fur trim, commanding majestic "
        "presence, accompanied by a small lightning lion"
    ),
    "bronya_hsr": (
        "Bronya Rand from Honkai Star Rail, 3D anime style, young woman with silver-white hair in twin "
        "drill tails, blue eyes, wearing a white military commander's uniform with cape and medals, "
        "serious authoritative appearance"
    ),
    "clara": (
        "Clara from Honkai Star Rail, 3D anime style, young girl with short brown hair in pigtails, "
        "brown eyes, wearing simple modest work clothes, accompanied by a large red-eyed mechanical "
        "guardian robot named Svarog standing behind her"
    ),
    "fuxuan": (
        "Fu Xuan from Honkai Star Rail, 3D anime style, petite short woman with pink-magenta hair in "
        "elaborate updo with ornamental hairpins, golden eyes, wearing elaborate traditional purple and "
        "gold Chinese-style divination robes with celestial patterns"
    ),
    "jingliu": (
        "Jingliu from Honkai Star Rail, 3D anime style, ethereal woman with long flowing white hair, "
        "ice-blue eyes with a blindfold partially covering them, wearing elegant white and ice-blue "
        "traditional Chinese robes, cold ethereal beauty, carries a katana"
    ),
    "topaz_hsr": (
        "Topaz from Honkai Star Rail, 3D anime style, young professional woman with orange-red hair in "
        "a neat ponytail, amber eyes, wearing a sharp blue and gold IPC business suit, confident corporate "
        "appearance, accompanied by small floating creature companion Numby"
    ),
    "ruanmei": (
        "Ruan Mei from Honkai Star Rail, 3D anime style, refined woman with long green hair adorned with "
        "flowers, green eyes, wearing an elegant white and green cheongsam with lab coat elements, "
        "scientific beauty, holds a plum blossom branch"
    ),
    "drratio": (
        "Dr. Ratio from Honkai Star Rail, 3D anime style, muscular athletic man with a distinctive "
        "white marble-textured mask covering his face, wearing a dark scholarly toga and robes with "
        "golden philosophical trim, intellectual warrior appearance"
    ),
    "blackswan": (
        "Black Swan from Honkai Star Rail, 3D anime style, elegant woman with long flowing dark "
        "purple-black hair, golden eyes, wearing an elegant dark purple and black dress with veil "
        "and ornate mask elements, mysterious gothic fortune teller aesthetic"
    ),
    "sparkle_hsr": (
        "Sparkle from Honkai Star Rail, 3D anime style, woman with multi-colored gradient hair from "
        "pink to purple to blue, heterochromatic eyes, wearing a theatrical colorful jester and "
        "harlequin outfit with masks, playful chaotic trickster appearance"
    ),
    "acheron": (
        "Acheron from Honkai Star Rail, 3D anime style, stoic woman with long straight dark purple-black "
        "hair, cold purple eyes, wearing a dark samurai-style outfit with red accents and flowing kimono "
        "elements, carries a katana, warrior of finality appearance"
    ),
    "aventurine": (
        "Aventurine from Honkai Star Rail, 3D anime style, charming man with styled blonde hair, "
        "turquoise-green eyes, wearing a stylish white and gold suit with jeweled accessories and "
        "gemstone cufflinks, confident suave gambler appearance"
    ),
    "robin_hsr": (
        "Robin from Honkai Star Rail, 3D anime style, beautiful woman with long wavy golden-blonde hair, "
        "warm blue eyes, wearing an elegant white dress with angelic wing motifs and golden halo accessory, "
        "celestial singer and idol aesthetic, gentle ethereal beauty"
    ),
    "firefly": (
        "Firefly from Honkai Star Rail, 3D anime style, sweet young woman with short brown hair with bangs, "
        "warm brown eyes, innocent youthful face, wearing a casual white and pink outfit with butterfly "
        "hair clips, gentle sincere appearance"
    ),
    "sunday": (
        "Sunday from Honkai Star Rail, 3D anime style, elegant man with white-platinum hair swept back, "
        "golden eyes, wearing a pristine white suit with angelic golden wing accessories extending from "
        "his back, authoritative beautiful androgynous appearance"
    ),
    "theherta": (
        "The Herta from Honkai Star Rail, 3D anime style, small doll-like young woman with purple twin "
        "tails, purple eyes, wearing a small purple and white Victorian-style dress with gear motifs, "
        "puppet-like proportions, genius scientist aesthetic"
    ),
    "luocha": (
        "Luocha from Honkai Star Rail, 3D anime style, handsome man with long blonde hair, green eyes, "
        "wearing a white and green clerical healer outfit with cross motifs, carries a large ornate "
        "coffin on his back, mysterious elegant healer"
    ),
    "argenti": (
        "Argenti from Honkai Star Rail, 3D anime style, beautiful man with long flowing silver-white hair, "
        "golden eyes, wearing ornate white and gold knight's armor with rose motifs and a flowing cape, "
        "radiant handsome paladin of beauty"
    ),
    "huohuo": (
        "Huohuo from Honkai Star Rail, 3D anime style, small young foxian girl with short green hair "
        "and fluffy fox ears, green eyes, wearing a traditional green and white foxian shaman outfit, "
        "carries a large fluffy tail spirit, perpetually nervous scared expression"
    ),
    "gallagher": (
        "Gallagher from Honkai Star Rail, 3D anime style, middle-aged man with brown hair slicked to the "
        "side, amber eyes, wearing a bartender outfit with vest rolled sleeves and bowtie, carries a "
        "cocktail glass, detective bartender aesthetic"
    ),
    "boothill": (
        "Boothill from Honkai Star Rail, 3D anime style, cybernetic cowboy with silver mechanical body "
        "parts mixed with organic skin, wearing a cowboy hat and red bandana around neck, wild grin, "
        "carries dual revolvers, wild west gunslinger with robot enhancements"
    ),
    "yunli": (
        "Yunli from Honkai Star Rail, 3D anime style, fierce young girl with long dark hair in a high "
        "ponytail, purple eyes, wearing a traditional red and white Chinese martial arts outfit with "
        "arm wraps, carries an oversized greatsword, determined warrior"
    ),
    "feixiao": (
        "Feixiao from Honkai Star Rail, 3D anime style, confident woman with short gray-white hair and "
        "fox ears, blue eyes, wearing a white and blue military general's outfit with epaulettes, "
        "carries dual curved swords, warrior leader appearance"
    ),
    "lingsha": (
        "Lingsha from Honkai Star Rail, 3D anime style, cheerful woman with long orange-red hair in an "
        "updo, amber eyes, wearing a colorful traditional Chinese outfit with medical motifs and ribbons, "
        "accompanied by a small dragon companion, healer"
    ),
    "jiaoqiu": (
        "Jiaoqiu from Honkai Star Rail, 3D anime style, elegant fox spirit man with long orange hair "
        "with fluffy fox ears and multiple flowing fox tails, golden eyes, wearing traditional ornate "
        "robes with floral patterns, refined strategist appearance"
    ),
}

RENDER_SUFFIX = (
    ", 3D rendered figurine style, clean gray studio background, "
    "full body shot, highly detailed, high quality, soft studio lighting"
)

# Pose definitions per character
CHARACTER_POSES = {
    "rudi": {
        "neutral": [
            ("idle", "{char} standing relaxed with arms crossed, slight smirk, casual confident stance"),
            ("thinking", "{char} with hand on chin, one eyebrow raised, thoughtful expression"),
        ],
        "positive": [
            ("smirk", "{char} with a knowing smirk, arms crossed, head slightly tilted, confident"),
            ("hyped", "{char} pumping fist in the air, excited grin, energetic pose"),
            ("cracking_up", "{char} laughing hard, head thrown back, genuine amusement"),
            ("charmed", "{char} with a warm genuine smile, hand over heart, pleasantly surprised"),
            ("confident", "{char} standing tall, hands on hips, chin up, supremely confident"),
        ],
        "negative": [
            ("unimpressed", "{char} with arms crossed, one eyebrow raised, clearly unimpressed look"),
            ("disappointed", "{char} pinching bridge of nose, eyes closed, disappointed expression"),
            ("facepalm", "{char} doing a full facepalm, other hand on hip, exasperated"),
            ("grossed_out", "{char} leaning away with disgusted face, hand up in stop gesture"),
            ("fired_up", "{char} with intense angry expression, fists clenched, leaning forward"),
            ("uneasy", "{char} looking nervously to the side, hands fidgeting, uncertain expression"),
            ("startled", "{char} jumping back with wide eyes, arms up in surprise, startled"),
            ("flustered", "{char} scratching back of head sheepishly, embarrassed half-smile"),
        ],
        "thinking": [
            ("pondering", "{char} looking upward thoughtfully, finger tapping chin"),
            ("questioning", "{char} with head tilted, confused expression, one eyebrow raised high"),
            ("scheming", "{char} with a mischievous grin, fingers steepled, plotting look"),
            ("focused", "{char} with intense focused eyes, determined expression, leaning forward"),
            ("intrigued", "{char} leaning forward with curiosity, eyes bright, interested expression"),
            ("lightbulb", "{char} with index finger raised, bright idea moment, excited eyes"),
        ],
        "speech": [
            ("talking", "{char} gesturing with one hand while speaking, animated expression"),
            ("explaining", "{char} with both hands open, explaining something passionately"),
            ("listening", "{char} with head slightly tilted, attentive listening pose, slight nod"),
        ],
        "greeting": [
            ("casual_wave", "{char} giving a casual two-finger wave, cool relaxed smile"),
            ("peace_out", "{char} throwing up a peace sign, walking away with a smirk"),
        ],
        "reactions": [
            ("double_take", "{char} doing a dramatic double take, head whipping back, surprised"),
            ("jaw_drop", "{char} with mouth wide open in shock, eyes huge, absolutely stunned"),
            ("mind_blown", "{char} with hands on sides of head, explosion effect, amazed"),
            ("sassy", "{char} with hand on hip, head tilted, finger wagging, sassy attitude"),
            ("cringe", "{char} cringing hard, one eye closed, teeth gritted, looking away"),
            ("impressed", "{char} nodding approvingly, arms crossed, raised eyebrow, genuine respect"),
        ],
        "sleep": [
            ("bored_yawn", "{char} mid-yawn, hand covering mouth, half-closed eyes, bored"),
            ("powered_down", "{char} slumped against wall, eyes closed, hoodie pulled up, sleeping"),
        ],
        "movement": [
            ("vibing", "{char} doing a casual dance move, bobbing head to music, relaxed groove"),
            ("arriving", "{char} walking in confidently, one hand in pocket, cool entrance"),
        ],
        "party": [
            ("celebrate", "{char} raising both arms in celebration, huge grin, confetti around"),
            ("birthday", "{char} holding a birthday cake with candles, warm smile"),
        ],
        "toast": [
            ("raising_glass", "{char} raising a glass high, confident smile, toasting"),
        ],
        "memorial": [
            ("respectful", "{char} with head bowed, one hand over heart, solemn respectful pose"),
        ],
    },
    "sonic": {
        "neutral": [
            ("idle", "{char} standing in classic pose, arms crossed, confident smirk, foot tapping"),
            ("thinking", "{char} with hand on chin, looking to the side, thoughtful"),
        ],
        "positive": [
            ("thumbs_up", "{char} giving a big thumbs up, wide grin, classic heroic pose"),
            ("hyped", "{char} in dynamic running pose, fist pumped, excited grin"),
            ("cracking_up", "{char} laughing, holding his belly, genuine amusement"),
            ("charmed", "{char} with a cocky but warm smile, hand behind head, chill pose"),
            ("confident", "{char} standing heroically, hands on hips, wind blowing quills"),
        ],
        "negative": [
            ("impatient", "{char} tapping foot impatiently, arms crossed, annoyed expression"),
            ("bummed", "{char} looking down sadly, ears drooped, disappointed"),
            ("grossed_out", "{char} holding nose in disgust, leaning away, revolted face"),
            ("fired_up", "{char} in battle stance, intense angry eyes, fists clenched"),
            ("uneasy", "{char} looking nervously to the side, uncertain stance"),
            ("startled", "{char} jumping back with wide eyes, spines raised, surprised"),
            ("flustered", "{char} scratching head sheepishly, embarrassed grin"),
        ],
        "thinking": [
            ("pondering", "{char} looking up thoughtfully, finger on chin"),
            ("head_scratch", "{char} scratching head confused, puzzled expression"),
            ("smirk", "{char} with a mischievous knowing smirk, plan forming"),
            ("focused", "{char} crouched in ready stance, determined eyes"),
            ("intrigued", "{char} leaning forward curiously, eyebrow raised"),
            ("lightbulb", "{char} snapping fingers with bright idea, excited eyes"),
        ],
        "speech": [
            ("talking", "{char} gesturing enthusiastically while talking, animated"),
            ("explaining", "{char} pointing at something while explaining, energetic"),
            ("listening", "{char} standing with arms crossed, listening attentively, slight nod"),
        ],
        "greeting": [
            ("wave", "{char} waving hello energetically, big smile, welcoming pose"),
            ("peace_out", "{char} giving peace sign, running away, looking back with grin"),
        ],
        "reactions": [
            ("double_take", "{char} doing a cartoon double take, body whipping around"),
            ("jaw_drop", "{char} jaw dropped, eyes popping, absolutely stunned"),
            ("mind_blown", "{char} hands on head, amazed shocked expression, spines standing up"),
            ("sassy", "{char} wagging finger confidently, cocky grin, attitude pose"),
            ("cringe", "{char} cringing, one eye closed, looking away uncomfortable"),
            ("impressed", "{char} giving slow nod of approval, arms crossed, respect"),
        ],
        "sleep": [
            ("dozing", "{char} curled up sleeping, peaceful expression, tail wrapped around"),
            ("impatient", "{char} yawning dramatically, checking imaginary watch"),
        ],
        "movement": [
            ("running", "{char} in full speed running pose, motion blur, dynamic"),
            ("speed_entry", "{char} sliding to a stop, dust cloud, dramatic entrance"),
        ],
        "party": [
            ("celebrate", "{char} jumping high with joy, fist pumped, confetti, celebration"),
            ("birthday", "{char} wearing a party hat, holding cake, excited expression"),
        ],
        "toast": [
            ("raising_glass", "{char} raising a glass, grinning, celebratory pose"),
        ],
        "memorial": [
            ("respectful", "{char} standing solemnly, head bowed, respectful, hand over heart"),
        ],
    },
    "ani": {
        "neutral": [
            ("idle", "{char} standing relaxed with hands gently clasped, warm smile, soft inviting stance"),
            ("thinking", "{char} with head tilted slightly, gentle thoughtful expression, hand near chin"),
        ],
        "positive": [
            ("happy", "{char} with a genuine warm smile, eyes bright, hands together, radiating kindness"),
            ("excited", "{char} clasping hands together excitedly, eyes sparkling, delighted expression"),
            ("laughing", "{char} laughing warmly, one hand over heart, genuine amusement"),
            ("love", "{char} with hands over heart, eyes soft and warm, deeply moved expression"),
            ("proud", "{char} standing tall with gentle confidence, warm approving smile, hands at sides"),
        ],
        "negative": [
            ("sad", "{char} with downcast eyes, gentle sad expression, hands clasped in front"),
            ("angry", "{char} with determined upset expression, arms crossed, concerned but firm"),
            ("annoyed", "{char} with slight frown, one eyebrow raised, mildly exasperated"),
            ("nervous", "{char} fidgeting with hands, uncertain expression, looking to the side"),
            ("scared", "{char} stepping back with wide worried eyes, hands up defensively"),
            ("embarrassed", "{char} touching cheek bashfully, looking away with slight blush"),
            ("disgusted", "{char} leaning away with wrinkled nose, hand up in gentle stop gesture"),
            ("grossed_out", "{char} covering mouth with hand, eyes wide, revolted expression"),
        ],
        "thinking": [
            ("confused", "{char} with tilted head, puzzled expression, questioning look"),
            ("thinking", "{char} looking upward thoughtfully, finger gently tapping chin"),
            ("curious", "{char} leaning forward with bright curious eyes, interested expression"),
            ("determined", "{char} with focused gentle eyes, slight nod, resolved expression"),
            ("mischievous", "{char} with a playful knowing smile, eyes twinkling, slight head tilt"),
            ("shocked", "{char} with hands on cheeks, wide surprised eyes, mouth slightly open"),
            ("idea", "{char} with finger raised, bright realization moment, eyes lit up"),
            ("surprised", "{char} with hands near face, pleasantly surprised expression"),
        ],
        "speech": [
            ("talking", "{char} gesturing gently with one hand while speaking, warm animated expression"),
            ("talking_excited", "{char} gesturing expressively with both hands, enthusiastic warm expression"),
            ("listening", "{char} with head slightly tilted, attentive warm listening pose, gentle nod"),
        ],
        "greeting": [
            ("wave", "{char} waving hello warmly, genuine bright smile, welcoming open posture"),
            ("farewell", "{char} waving goodbye gently, bittersweet warm smile, caring expression"),
        ],
        "reactions": [
            ("mind_blown", "{char} with hands on sides of head, amazed delighted expression"),
            ("sassy", "{char} with hand on hip, playful knowing look, gentle sass"),
            ("cringe", "{char} wincing sympathetically, one eye closed, empathetic cringe"),
            ("impressed", "{char} nodding approvingly, warm smile, genuinely impressed expression"),
        ],
        "sleep": [
            ("yawning", "{char} mid-yawn, hand covering mouth, sleepy gentle expression"),
            ("sleepy", "{char} eyes half closed, peaceful drowsy expression, leaning slightly"),
            ("sleeping", "{char} peacefully sleeping, serene expression, floating gently"),
        ],
        "movement": [
            ("dancing", "{char} doing a gentle graceful dance, flowing movement, joyful"),
            ("entering", "{char} stepping forward warmly, open welcoming gesture, bright smile"),
        ],
        "party": [
            ("celebrate", "{char} raising both arms in celebration, radiant joy, sparkles around"),
        ],
        "birthday": [
            ("birthday", "{char} holding a birthday cake with candles, warm caring smile"),
        ],
        "toast": [
            ("raising_glass", "{char} raising a glass with a warm smile, gentle toast"),
        ],
        "memorial": [
            ("moment_of_silence", "{char} with head bowed, hand over heart, solemn respectful pose"),
        ],
    },
}

# ── Shared HSR humanoid pose template ──
_HSR_POSES = {
    "neutral": [
        ("idle", "{char} standing in a relaxed signature pose, calm confident expression"),
        ("thinking", "{char} with hand on chin, looking thoughtfully to the side"),
    ],
    "positive": [
        ("happy", "{char} with a genuine warm smile, eyes bright, cheerful expression"),
        ("excited", "{char} with fists clenched in excitement, big grin, energetic pose"),
        ("laughing", "{char} laughing heartily, head tilted back, genuine amusement"),
        ("charmed", "{char} with a warm gentle smile, hand near heart, pleasantly touched"),
        ("confident", "{char} standing tall with hands on hips, confident proud expression"),
    ],
    "negative": [
        ("annoyed", "{char} with arms crossed, slight frown, one eyebrow raised, unimpressed"),
        ("disappointed", "{char} pinching bridge of nose, eyes closed, disappointed sigh"),
        ("angry", "{char} with intense angry expression, fists clenched, battle stance"),
        ("disgusted", "{char} leaning away with wrinkled nose, hand up in stop gesture"),
        ("sad", "{char} looking down with sorrowful expression, hands at sides, dejected"),
        ("nervous", "{char} looking to the side nervously, fidgeting with hands, uncertain"),
        ("startled", "{char} jumping back with wide eyes, arms up defensively, surprised"),
        ("embarrassed", "{char} looking away with slight blush, hand behind head, sheepish"),
    ],
    "thinking": [
        ("pondering", "{char} looking upward thoughtfully, finger tapping chin"),
        ("confused", "{char} with tilted head, puzzled expression, question mark vibe"),
        ("scheming", "{char} with a sly knowing grin, fingers steepled, plotting"),
        ("focused", "{char} with intense focused eyes, determined expression, ready stance"),
        ("curious", "{char} leaning forward with bright curious eyes, intrigued"),
        ("idea", "{char} with finger raised, bright idea moment, eyes lit up with realization"),
    ],
    "speech": [
        ("talking", "{char} gesturing with one hand while speaking, animated expression"),
        ("explaining", "{char} with both hands open, explaining something passionately"),
        ("listening", "{char} with head slightly tilted, attentive listening pose"),
    ],
    "greeting": [
        ("wave", "{char} waving hello warmly, friendly smile, welcoming pose"),
        ("farewell", "{char} waving goodbye, warm but bittersweet expression"),
    ],
    "reactions": [
        ("shocked", "{char} with hands on cheeks, wide eyes, absolutely stunned"),
        ("mind_blown", "{char} with hands on sides of head, amazed expression"),
        ("impressed", "{char} nodding approvingly, arms crossed, genuine respect"),
        ("sassy", "{char} with hand on hip, head tilted, confident attitude"),
        ("cringe", "{char} cringing with one eye closed, teeth gritted, looking away"),
    ],
    "sleep": [
        ("yawning", "{char} mid-yawn, hand covering mouth, drowsy eyes"),
        ("sleeping", "{char} peacefully sleeping, serene expression, eyes closed"),
    ],
    "movement": [
        ("entering", "{char} making a dramatic entrance, confident stride, cool arrival"),
        ("action", "{char} in dynamic action pose, weapon drawn, battle ready"),
    ],
    "party": [
        ("celebrate", "{char} raising both arms in celebration, huge joyful grin, confetti"),
        ("birthday", "{char} holding a birthday cake with candles, warm smile"),
    ],
    "toast": [
        ("raising_glass", "{char} raising a glass, charming smile, celebratory toast"),
    ],
    "memorial": [
        ("respectful", "{char} with head bowed, hand over heart, solemn respectful pose"),
    ],
}

_HSR_CHARACTERS = [
    "stelle", "march7th", "danheng", "himeko", "welt", "kafka", "silverwolf",
    "seele", "blade_hsr", "jingyuan", "bronya_hsr", "clara", "fuxuan",
    "jingliu", "topaz_hsr", "ruanmei", "drratio", "blackswan", "sparkle_hsr",
    "acheron", "aventurine", "robin_hsr", "firefly", "sunday", "theherta",
    "luocha", "argenti", "huohuo", "gallagher", "boothill", "yunli",
    "feixiao", "lingsha", "jiaoqiu",
]
for _c in _HSR_CHARACTERS:
    CHARACTER_POSES[_c] = _HSR_POSES

# ── Pomni (The Amazing Digital Circus) ──
CHARACTER_POSES["pomni"] = {
    "neutral": [
        ("idle", "{char} standing nervously with hands clasped, wide anxious eyes, jester outfit with red and blue, slight trembling"),
        ("thinking", "{char} with finger to lip, worried thoughtful expression, looking off to the side nervously"),
    ],
    "positive": [
        ("happy", "{char} with a small relieved smile, still nervous but genuinely pleased, hands together"),
        ("excited", "{char} bouncing slightly with surprised joy, wide eyes, rare moment of genuine excitement"),
        ("laughing", "{char} covering mouth while laughing nervously, eyes squinting with genuine amusement"),
        ("love", "{char} with a soft warm expression, hands over heart, rare moment of peace and affection"),
        ("proud", "{char} standing slightly taller, small confident smile, fists gently clenched in triumph"),
    ],
    "negative": [
        ("sad", "{char} looking down with drooping jester hat bells, shoulders slumped, melancholy expression"),
        ("angry", "{char} with fists clenched at sides, frustrated tears in eyes, rare moment of anger"),
        ("annoyed", "{char} with deadpan expression, arms crossed, one eye twitching in irritation"),
        ("nervous", "{char} fidgeting with hands, eyes darting around, classic anxious pose, sweat drops"),
        ("scared", "{char} cowering with hands up defensively, wide terrified eyes, bells jingling"),
        ("embarrassed", "{char} covering face with both hands, visible blush, jester hat drooping"),
        ("disgusted", "{char} recoiling backwards, hands up in disgust, nose wrinkled"),
        ("grossed_out", "{char} turning away gagging slightly, hand over mouth, revolted expression"),
    ],
    "thinking": [
        ("confused", "{char} with head tilted, question marks floating around, genuinely puzzled expression"),
        ("thinking", "{char} tapping chin nervously, eyes looking up, overthinking everything"),
        ("curious", "{char} leaning forward cautiously, one eye squinting, suspicious but interested"),
        ("determined", "{char} with unusually firm expression, fists clenched, rare brave moment"),
        ("mischievous", "{char} with a sly nervous grin, fingers together, plotting something risky"),
        ("shocked", "{char} jaw dropped, hands on cheeks, absolute shock and disbelief"),
        ("idea", "{char} with finger raised, eyes wide with sudden realization, lightbulb moment"),
        ("surprised", "{char} jumping back with hands up, startled wide eyes, bells jingling"),
    ],
    "speech": [
        ("talking", "{char} gesturing nervously while speaking, one hand waving, stammering expression"),
        ("talking_excited", "{char} talking faster than usual, animated hand gestures, rare enthusiastic moment"),
        ("listening", "{char} leaning in attentively, hands clasped, focused listening with nervous energy"),
    ],
    "greeting": [
        ("wave", "{char} giving a small nervous wave, hesitant smile, jester bells tinkling softly"),
        ("farewell", "{char} waving goodbye with worried expression, hoping they will come back"),
    ],
    "reactions": [
        ("mind_blown", "{char} with hands on sides of head, eyes like spirals, completely overwhelmed"),
        ("sassy", "{char} with rare confident hand-on-hip pose, raised eyebrow, brief sass moment"),
        ("cringe", "{char} cringing hard with both eyes squeezed shut, teeth gritted, full body cringe"),
        ("impressed", "{char} with eyebrows raised high, small 'oh' mouth, genuinely impressed nod"),
    ],
    "sleep": [
        ("yawning", "{char} mid-yawn with hand covering mouth, sleepy drooping eyes, hat bells hanging"),
        ("sleepy", "{char} eyes half closed, swaying slightly, fighting to stay awake"),
        ("sleeping", "{char} curled up peacefully sleeping, rare moment of complete calm, gentle expression"),
    ],
    "movement": [
        ("dancing", "{char} doing an awkward but endearing little dance, self-conscious but trying"),
        ("entering", "{char} peeking around a corner cautiously before stepping in, nervous entrance"),
    ],
    "party": [
        ("celebrate", "{char} throwing hands up in rare celebration, genuine joy breaking through anxiety"),
    ],
    "birthday": [
        ("birthday", "{char} holding a birthday cake nervously, worried about dropping it, sweet smile"),
    ],
    "toast": [
        ("raising_glass", "{char} raising a glass with shaking hands, nervous but sincere toast"),
    ],
    "memorial": [
        ("moment_of_silence", "{char} with head bowed solemnly, hands clasped, bells completely still"),
    ],
}

def generate_pollinations(prompt, retries=8):
    """Generate an image using Pollinations.ai free API."""
    import urllib.parse
    import random
    for attempt in range(retries):
        try:
            if DEBUG_GEN:
                print(f"    [DEBUG_GEN] Pollinations attempt {attempt + 1}/{retries}")
            encoded = urllib.parse.quote(prompt)
            seed = random.randint(1, 999999)
            url = f"https://image.pollinations.ai/prompt/{encoded}?width=512&height=512&nologo=true&seed={seed}"
            resp = requests.get(url, timeout=180)
            if resp.status_code == 200 and len(resp.content) > 5000:
                if DEBUG_GEN:
                    print(f"    [DEBUG_GEN] Pollinations OK: {len(resp.content)} bytes")
                return resp.content
            else:
                if DEBUG_GEN:
                    print(f"    [DEBUG_GEN] Pollinations: HTTP {resp.status_code}, {len(resp.content)} bytes")
        except Exception as e:
            if DEBUG_GEN:
                print(f"    [DEBUG_GEN] Pollinations error: {e}")
        if attempt < retries - 1:
            wait = 20 * (attempt + 1)
            if DEBUG_GEN:
                print(f"    [DEBUG_GEN] Retrying in {wait}s...")
            time.sleep(wait)
    return None


def generate_subnp(prompt, retries=5):
    """Generate an image using SubNP free API with retry logic."""
    for attempt in range(retries):
        try:
            if DEBUG_GEN:
                print(f"    [DEBUG_GEN] SubNP attempt {attempt + 1}/{retries}")

            resp = requests.post(
                API_URL,
                json={"prompt": prompt, "model": MODEL},
                timeout=180,
                stream=True,
                headers={"Connection": "keep-alive"},
            )

            if resp.status_code != 200:
                if DEBUG_GEN:
                    print(f"    [DEBUG_GEN] HTTP {resp.status_code}")
                continue

            img_url = None
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                try:
                    data = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                status = data.get("status", "")
                if DEBUG_GEN:
                    print(f"    [DEBUG_GEN] SSE: {status} - {data.get('message', '')}")
                if status == "error":
                    break
                img_url = data.get("image_url") or data.get("url") or data.get("imageUrl")
                if img_url:
                    break

            if img_url:
                img_resp = requests.get(img_url, timeout=60)
                if img_resp.status_code == 200 and len(img_resp.content) > 1000:
                    return img_resp.content
        except requests.exceptions.ConnectionError:
            pass
        except requests.exceptions.Timeout:
            pass
        except Exception as e:
            if DEBUG_GEN:
                print(f"    [DEBUG_GEN] Error: {type(e).__name__}: {e}")

        if attempt < retries - 1:
            wait = 10 * (attempt + 1)
            if DEBUG_GEN:
                print(f"    [DEBUG_GEN] Retrying in {wait}s...")
            time.sleep(wait)
    return None


def generate_dalle(prompt):
    """Generate an image using OpenAI DALL-E API."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable not set")

    try:
        resp = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "dall-e-3", "prompt": prompt, "n": 1, "size": "1024x1024", "quality": "standard"},
            timeout=120,
        )
        if resp.status_code == 200:
            img_url = resp.json()["data"][0]["url"]
            img_resp = requests.get(img_url, timeout=60)
            if img_resp.status_code == 200:
                return img_resp.content
        else:
            print(f"    [ERROR] DALL-E API: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        print(f"    [ERROR] DALL-E error: {e}")
    return None


def remove_background(input_path, output_path):
    """Remove background from image using rembg."""
    try:
        from rembg import remove as rembg_remove
    except ImportError:
        print("    [ERROR] rembg not installed. Run: pip install rembg")
        return False
    try:
        with open(input_path, "rb") as f:
            input_data = f.read()
        output_data = rembg_remove(input_data)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(output_data)
        return True
    except Exception as e:
        print(f"    [ERROR] Background removal failed: {e}")
        return False


def generate_character(character_name, category_filter=None, use_dalle=False, use_pollinations=False, force=False, min_size=1000):
    """Generate all poses for a character."""
    if character_name not in CHARACTER_POSES:
        print(f"Error: Unknown character '{character_name}'. Available: {list(CHARACTER_POSES.keys())}")
        return

    char_style = CHARACTER_STYLES.get(character_name, character_name)
    poses = CHARACTER_POSES[character_name]
    char_dir = os.path.join(PROJECT_ROOT, "characters", character_name, "sprites")
    raw_dir = os.path.join(PROJECT_ROOT, "characters", character_name, "_raw_sprites")

    total_gen = 0
    total_skip = 0
    total_fail = 0

    categories = [category_filter] if category_filter else list(poses.keys())

    for category in categories:
        if category not in poses:
            print(f"Unknown category: {category}")
            continue

        print(f"\n{'='*50}")
        print(f"  {character_name.upper()} — {category.upper()}")
        print(f"{'='*50}")

        cat_poses = poses[category]
        cat_dir = os.path.join(char_dir, category)
        raw_cat_dir = os.path.join(raw_dir, category)
        os.makedirs(cat_dir, exist_ok=True)
        os.makedirs(raw_cat_dir, exist_ok=True)

        for i, (pose_id, prompt_template) in enumerate(cat_poses):
            out_path = os.path.join(cat_dir, f"{pose_id}.png")
            raw_path = os.path.join(raw_cat_dir, f"{pose_id}.png")

            if not force and os.path.exists(out_path) and os.path.getsize(out_path) > min_size:
                print(f"  [{i+1}/{len(cat_poses)}] {category}/{pose_id} — SKIPPED (exists)")
                total_skip += 1
                continue

            if not force and os.path.exists(raw_path) and os.path.getsize(raw_path) > 1000:
                print(f"  [{i+1}/{len(cat_poses)}] {category}/{pose_id} — Removing BG...")
                if remove_background(raw_path, out_path):
                    total_gen += 1
                else:
                    total_fail += 1
                continue

            # Build full prompt
            full_prompt = prompt_template.format(char=char_style) + RENDER_SUFFIX
            print(f"  [{i+1}/{len(cat_poses)}] {category}/{pose_id} — Generating...")
            start = time.time()

            if use_dalle:
                img_data = generate_dalle(full_prompt)
            elif use_pollinations:
                img_data = generate_pollinations(full_prompt)
            else:
                img_data = generate_subnp(full_prompt, retries=2)
                if not img_data:
                    if DEBUG_GEN:
                        print(f"    [DEBUG_GEN] SubNP failed, trying Pollinations.ai...")
                    img_data = generate_pollinations(full_prompt)

            elapsed = time.time() - start

            if img_data:
                with open(raw_path, "wb") as f:
                    f.write(img_data)
                print(f"  [{i+1}/{len(cat_poses)}] {category}/{pose_id} — Downloaded ({len(img_data)/1024:.0f}KB, {elapsed:.1f}s)")
                print(f"  [{i+1}/{len(cat_poses)}] {category}/{pose_id} — Removing BG...")
                if remove_background(raw_path, out_path):
                    print(f"  [{i+1}/{len(cat_poses)}] {category}/{pose_id} — OK ✓")
                    total_gen += 1
                else:
                    total_fail += 1
            else:
                print(f"  [{i+1}/{len(cat_poses)}] {category}/{pose_id} — FAILED ({elapsed:.1f}s)")
                total_fail += 1

            time.sleep(20)

    print(f"\n{'='*50}")
    print(f"  {character_name.upper()} COMPLETE")
    print(f"  Generated: {total_gen}  Skipped: {total_skip}  Failed: {total_fail}")
    print(f"  Sprites saved to: {char_dir}")
    print(f"{'='*50}")


def list_poses(character_name):
    """List all pose categories and counts for a character."""
    if character_name not in CHARACTER_POSES:
        print(f"Unknown character: {character_name}")
        return
    poses = CHARACTER_POSES[character_name]
    total = 0
    for cat, items in poses.items():
        print(f"  {cat}: {len(items)} poses")
        total += len(items)
    print(f"  TOTAL: {total} poses")


def main():
    parser = argparse.ArgumentParser(description="Generate character sprite poses")
    parser.add_argument("--character", "-c", required=True, help="Character name (rudi, sonic, ani)")
    parser.add_argument("--category", help="Generate only this category")
    parser.add_argument("--dalle", action="store_true", help="Use DALL-E instead of SubNP")
    parser.add_argument("--pollinations", action="store_true", help="Use Pollinations.ai directly (skip SubNP)")
    parser.add_argument("--list", action="store_true", help="List pose categories")
    parser.add_argument("--force", action="store_true", help="Regenerate all poses (ignore existing files)")
    parser.add_argument("--min-size", type=int, default=1000, help="Min file size to consider 'existing' (default: 1000, use 15000 to skip placeholders)")
    args = parser.parse_args()

    if args.list:
        list_poses(args.character)
        return

    generate_character(args.character, args.category, args.dalle, args.pollinations, 
                       force=args.force, min_size=args.min_size)


if __name__ == "__main__":
    main()
