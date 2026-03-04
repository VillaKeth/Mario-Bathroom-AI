"""Generate high-quality Mario pixel art sprites with outlines and shading.

Run this once to create sprite assets in client/assets/mario/.
The sprites are original pixel art inspired by the classic 8-bit style,
with auto-generated outlines and drop shadows for a polished look.
"""

import os
from PIL import Image

ASSET_DIR = os.path.join(os.path.dirname(__file__), "assets", "mario")

# Enhanced NES-inspired color palette with shading variants
PALETTE = {
    '.': None,                        # Transparent
    'r': (228, 0, 0, 255),           # Red (cap, shirt)
    'd': (176, 0, 0, 255),           # Dark red (cap shadow)
    'b': (160, 88, 0, 255),          # Brown (hair, shoes)
    'g': (104, 56, 0, 255),          # Dark brown (shoe soles)
    's': (252, 180, 108, 255),       # Skin
    'n': (228, 148, 84, 255),        # Dark skin (nose, shading)
    'u': (0, 88, 248, 255),          # Blue (overalls)
    'i': (0, 56, 200, 255),          # Dark blue (overall shadow)
    'y': (252, 216, 0, 255),         # Yellow (buttons)
    'w': (255, 255, 255, 255),       # White (eyes, gloves)
    'e': (220, 220, 220, 255),       # Light gray (glove cuff)
    'k': (0, 0, 0, 255),            # Black (pupils)
}

SCALE = 10  # Each pixel becomes 10x10 (up from 8)
OUTLINE_COLOR = (16, 16, 16, 255)   # Near-black outline
SHADOW_COLOR = (0, 0, 0, 50)        # Subtle drop shadow

# ==========================================
# SPRITE DEFINITIONS (16 wide, varying height)
# Fixed: friendly eyes, clear mustache, correct arm anatomy
# ==========================================

# Eyes: ww top (whites), kk bottom (pupils) = relaxed, friendly look
# Mustache: thick brown band with nose shadow (n) above for definition
# Arms: extend from body at chest level, never float from head

SPRITE_IDLE = [
    "....rrrrr.......",
    "...rrrrrrrrr....",
    "...drrrrrrrrr...",
    "..drrrrrrrrrrd..",
    "..bbbsssbbs.....",
    ".bssbsssssbbs...",
    ".bssswwswwsss...",
    ".bssskkskkssn...",
    "..ssssnssnsss...",
    "..ssbbbbbbbss...",
    "...ssssssssss...",
    "....rrrrrrrr....",
    "..rrrruuuurrrr..",
    ".wrrrrruuurrrrrw",
    ".errrrruuuurrrrw",
    "..rrrruuyuurrrr.",
    "...uuuuuuuuuu...",
    "..uuuuuuuuuuuu..",
    "..iiuuu..uuuii..",
    "..uuuu....uuuu..",
    "..bbbb....bbbb..",
    ".bbbbb....bbbbb.",
    ".ggggg....ggggg.",
]

SPRITE_TALK = [
    "....rrrrr.......",
    "...rrrrrrrrr....",
    "...drrrrrrrrr...",
    "..drrrrrrrrrrd..",
    "..bbbsssbbs.....",
    ".bssbsssssbbs...",
    ".bssswwswwsss...",
    ".bssskkskkssn...",
    "..ssssnssnsss...",
    "..ssbbbbbbbss...",
    "...ssnrrrnsss...",
    "....rrrrrrrr....",
    "..rrrruuuurrrr..",
    ".wrrrrruuurrrrrw",
    ".errrrruuuurrrrw",
    "..rrrruuyuurrrr.",
    "...uuuuuuuuuu...",
    "..uuuuuuuuuuuu..",
    "..iiuuu..uuuii..",
    "..uuuu....uuuu..",
    "..bbbb....bbbb..",
    ".bbbbb....bbbbb.",
    ".ggggg....ggggg.",
]

SPRITE_WALK1 = [
    "....rrrrr.......",
    "...rrrrrrrrr....",
    "...drrrrrrrrr...",
    "..drrrrrrrrrrd..",
    "..bbbsssbbs.....",
    ".bssbsssssbbs...",
    ".bssswwswwsss...",
    ".bssskkskkssn...",
    "..ssssnssnsss...",
    "..ssbbbbbbbss...",
    "...ssssssssss...",
    "....rrrrrrrr....",
    "..rrrruuuurrrr..",
    ".wrrrrruuurrrrrw",
    ".errrrruuuurrrrw",
    "..rrrruuyuurrrr.",
    "...uuuuuuuuuu...",
    "...uuuuuuuuuuu..",
    "....iuuu..uuui..",
    ".....uuu...bbbb.",
    "....bbbb...ggg..",
    "...ggggg........",
]

SPRITE_WALK2 = [
    "....rrrrr.......",
    "...rrrrrrrrr....",
    "...drrrrrrrrr...",
    "..drrrrrrrrrrd..",
    "..bbbsssbbs.....",
    ".bssbsssssbbs...",
    ".bssswwswwsss...",
    ".bssskkskkssn...",
    "..ssssnssnsss...",
    "..ssbbbbbbbss...",
    "...ssssssssss...",
    "....rrrrrrrr....",
    "..rrrruuuurrrr..",
    ".wrrrrruuurrrrrw",
    ".errrrruuuurrrrw",
    "..rrrruuyuurrrr.",
    "...uuuuuuuuuu...",
    "..uuuuuuuuuuu...",
    "..iuuu..uuuui...",
    ".bbbb...uuu.....",
    "..ggg...bbbb....",
    "........ggggg...",
]

# Wave: right arm extends from shirt at chest level
SPRITE_WAVE = [
    "....rrrrr.......",
    "...rrrrrrrrr....",
    "...drrrrrrrrr...",
    "..drrrrrrrrrrd..",
    "..bbbsssbbs.....",
    ".bssbsssssbbs...",
    ".bssswwswwsss...",
    ".bssskkskkssn...",
    "..ssssnssnsss...",
    "..ssbbbbbbbss...",
    "...ssssssssss...",
    "....rrrrrrrr....",
    "..rrrruuuurrrrew",
    ".wrrrrruuurrrrr.",
    ".errrrruuuurrrrr",
    "..rrrruuyuurrrr.",
    "...uuuuuuuuuu...",
    "..uuuuuuuuuuuu..",
    "..iiuuu..uuuii..",
    "..uuuu....uuuu..",
    "..bbbb....bbbb..",
    ".bbbbb....bbbbb.",
    ".ggggg....ggggg.",
]

# Jump: arms spread wide from body, legs tucked up
SPRITE_JUMP = [
    "....rrrrr.......",
    "...rrrrrrrrr....",
    "...drrrrrrrrr...",
    "..drrrrrrrrrrd..",
    "..bbbsssbbs.....",
    ".bssbsssssbbs...",
    ".bssswwswwsss...",
    ".bssskkskkssn...",
    "..ssssnssnsss...",
    "..ssbbbbbbbss...",
    "...ssssssssss...",
    "....rrrrrrrr....",
    "..rrrruuuurrrr..",
    "wrrrrruuuurrrrrw",
    ".errrrruuuurrre.",
    "..rrrruuyuurrrr.",
    "...uuuuuuuuuu...",
    "..uuuuuuuuuuuu..",
    "..uuuuu..uuuuu..",
    ".bbbbb....bbbbb.",
    ".ggggg....ggggg.",
]

# Think: half-closed contemplative eyes (squinting, not staring)
SPRITE_THINK = [
    "....rrrrr.......",
    "...rrrrrrrrr....",
    "...drrrrrrrrr...",
    "..drrrrrrrrrrd..",
    "..bbbsssbbs.....",
    ".bssbsssssbbs...",
    ".bsssnnsnnssn...",
    ".bsssswsswssn...",
    "..ssssnssnsss...",
    "..ssbbbbbbbss...",
    "...ssssssssss...",
    "....rrrrrrrr....",
    "..rrrruuuurrrr..",
    ".wrrrrruuurrrrrw",
    ".errrrruuuurrrrw",
    "..rrrruuyuurrrr.",
    "...uuuuuuuuuu...",
    "..uuuuuuuuuuuu..",
    "..iiuuu..uuuii..",
    "..uuuu....uuuu..",
    "..bbbb....bbbb..",
    ".bbbbb....bbbbb.",
    ".ggggg....ggggg.",
]

# Laughing: eyes squeezed shut, big open mouth below mustache
SPRITE_LAUGH = [
    "....rrrrr.......",
    "...rrrrrrrrr....",
    "...drrrrrrrrr...",
    "..drrrrrrrrrrd..",
    "..bbbsssbbs.....",
    ".bssbsssssbbs...",
    ".bsssnnsnnssn...",
    ".bsssssssssss...",
    "..ssssnssnsss...",
    "..ssbbbsbbbss...",
    "...snrrrrrnsn...",
    "....rrrrrrrr....",
    "..rrrruuuurrrr..",
    ".wrrrrruuurrrrrw",
    ".errrrruuuurrrrw",
    "..rrrruuyuurrrr.",
    "...uuuuuuuuuu...",
    "..uuuuuuuuuuuu..",
    "..iiuuu..uuuii..",
    "..uuuu....uuuu..",
    "..bbbb....bbbb..",
    ".bbbbb....bbbbb.",
    ".ggggg....ggggg.",
]

# Surprised: extra-wide eyes, small O mouth
SPRITE_SURPRISE = [
    "....rrrrr.......",
    "...rrrrrrrrr....",
    "...drrrrrrrrr...",
    "..drrrrrrrrrrd..",
    "..bbbsssbbs.....",
    ".bssbsssssbbs...",
    ".bswwwsswwwss...",
    ".bswkwsswkwss...",
    "..ssssnssnsss...",
    "..ssbbbbbbbss...",
    "...sssnrnsssn...",
    "....rrrrrrrr....",
    "..rrrruuuurrrr..",
    ".wrrrrruuurrrrrw",
    ".errrrruuuurrrrw",
    "..rrrruuyuurrrr.",
    "...uuuuuuuuuu...",
    "..uuuuuuuuuuuu..",
    "..iiuuu..uuuii..",
    "..uuuu....uuuu..",
    "..bbbb....bbbb..",
    ".bbbbb....bbbbb.",
    ".ggggg....ggggg.",
]

# Sleeping: closed eyes, Z's floating above head
SPRITE_SLEEP = [
    "............k.k.",
    "...........k....",
    "..........k.k...",
    "....rrrrr.......",
    "...rrrrrrrrr....",
    "...drrrrrrrrr...",
    "..drrrrrrrrrrd..",
    "..bbbsssbbs.....",
    ".bssbsssssbbs...",
    ".bsssnnsnnssn...",
    ".bsssssssssss...",
    "..ssssnssnsss...",
    "..ssbbbbbbbss...",
    "...ssssssssss...",
    "....rrrrrrrr....",
    "..rrrruuuurrrr..",
    ".wrrrrruuurrrrrw",
    ".errrrruuuurrrrw",
    "..rrrruuyuurrrr.",
    "...uuuuuuuuuu...",
    "..uuuuuuuuuuuu..",
    "..iiuuu..uuuii..",
    "..uuuu....uuuu..",
    "..bbbb....bbbb..",
    ".bbbbb....bbbbb.",
    ".ggggg....ggggg.",
]

# Dancing: arms wide, right leg kicked out
SPRITE_DANCE = [
    "....rrrrr.......",
    "...rrrrrrrrr....",
    "...drrrrrrrrr...",
    "..drrrrrrrrrrd..",
    "..bbbsssbbs.....",
    ".bssbsssssbbs...",
    ".bssswwswwsss...",
    ".bssskkskkssn...",
    "..ssssnssnsss...",
    "..ssbbbbbbbss...",
    "...ssssssssss...",
    "....rrrrrrrr....",
    "..rrrruuuurrrr..",
    "wrrrrruuuurrrrrw",
    ".errrrruuuurrre.",
    "..rrrruuyuurrrr.",
    "...uuuuuuuuuu...",
    "..uuuuuuuuuuuu..",
    "..iiuuu....uuuu.",
    "..uuuu......uuu.",
    "..bbbb.....bbbb.",
    ".bbbbb.....ggggg",
    ".ggggg..........",
]

ALL_SPRITES = {
    "idle":     SPRITE_IDLE,
    "talk":     SPRITE_TALK,
    "walk1":    SPRITE_WALK1,
    "walk2":    SPRITE_WALK2,
    "wave":     SPRITE_WAVE,
    "jump":     SPRITE_JUMP,
    "think":    SPRITE_THINK,
    "laugh":    SPRITE_LAUGH,
    "surprise": SPRITE_SURPRISE,
    "sleep":    SPRITE_SLEEP,
    "dance":    SPRITE_DANCE,
}


# ==========================================
# IMAGE PROCESSING
# ==========================================

def sprite_to_raw(sprite_data: list[str]) -> Image.Image:
    """Convert a sprite string array to a raw pixel image (no scaling)."""
    height = len(sprite_data)
    width = max(len(row) for row in sprite_data)

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pixels = img.load()

    for y, row in enumerate(sprite_data):
        for x, char in enumerate(row):
            color = PALETTE.get(char)
            if color:
                pixels[x, y] = color

    return img


def add_outline(img: Image.Image, color: tuple = OUTLINE_COLOR) -> Image.Image:
    """Add 1px pixel-art outline around all non-transparent pixels.
    
    Checks all 8 directions for a polished, rounded outline look.
    Returns a new image padded by 1px on each side.
    """
    w, h = img.size
    result = Image.new("RGBA", (w + 2, h + 2), (0, 0, 0, 0))
    src = img.load()
    dst = result.load()

    dirs = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

    # Pass 1: mark outline pixels around non-transparent areas
    for y in range(h):
        for x in range(w):
            if src[x, y][3] > 0:
                for dx, dy in dirs:
                    nx, ny = x + dx + 1, y + dy + 1
                    if 0 <= nx < w + 2 and 0 <= ny < h + 2:
                        if dst[nx, ny][3] == 0:
                            dst[nx, ny] = color

    # Pass 2: copy original pixels on top of outline
    for y in range(h):
        for x in range(w):
            if src[x, y][3] > 0:
                dst[x + 1, y + 1] = src[x, y]

    return result


def add_drop_shadow(img: Image.Image, offset: tuple = (2, 2),
                    color: tuple = SHADOW_COLOR) -> Image.Image:
    """Add a subtle drop shadow behind the sprite for depth."""
    w, h = img.size
    ox, oy = offset
    nw, nh = w + abs(ox), h + abs(oy)
    result = Image.new("RGBA", (nw, nh), (0, 0, 0, 0))
    src = img.load()
    dst = result.load()

    # Draw shadow offset
    for y in range(h):
        for x in range(w):
            if src[x, y][3] > 0:
                sx, sy = x + max(ox, 0), y + max(oy, 0)
                if 0 <= sx < nw and 0 <= sy < nh and dst[sx, sy][3] == 0:
                    dst[sx, sy] = color

    # Draw original on top
    for y in range(h):
        for x in range(w):
            if src[x, y][3] > 0:
                dst[x + max(-ox, 0), y + max(-oy, 0)] = src[x, y]

    return result


def generate_sprite(sprite_data: list[str]) -> Image.Image:
    """Full pipeline: raw pixels → outline → shadow → scale up."""
    raw = sprite_to_raw(sprite_data)
    outlined = add_outline(raw)
    shadowed = add_drop_shadow(outlined)
    final = shadowed.resize(
        (shadowed.width * SCALE, shadowed.height * SCALE),
        Image.NEAREST,
    )
    return final


def generate_all():
    """Generate all Mario sprite PNGs."""
    os.makedirs(ASSET_DIR, exist_ok=True)

    # Validate all sprites before generating
    for name, data in ALL_SPRITES.items():
        for i, row in enumerate(data):
            if len(row) != 16:
                raise ValueError(f"Sprite '{name}' row {i}: expected 16 chars, got {len(row)}")

    for name, data in ALL_SPRITES.items():
        img = generate_sprite(data)
        path = os.path.join(ASSET_DIR, f"mario_{name}.png")
        img.save(path)
        print(f"  Created {path} ({img.width}x{img.height})")

    # Create "talk2" frame with wider mouth for talk animation
    talk2 = SPRITE_TALK.copy()
    talk2[10] = "...snrrrrrnsss.."
    img = generate_sprite(talk2)
    path = os.path.join(ASSET_DIR, "mario_talk2.png")
    img.save(path)
    print(f"  Created {path} ({img.width}x{img.height})")

    print(f"\nAll {len(ALL_SPRITES) + 1} sprites saved to {ASSET_DIR}")


if __name__ == "__main__":
    generate_all()
