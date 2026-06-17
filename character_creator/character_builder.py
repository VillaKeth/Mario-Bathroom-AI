"""Character builder — generates character directory from wizard config."""
import os
import yaml
import logging
import math

logger = logging.getLogger(__name__)

# Import emotion/state sprites from sprite_generator
from character_creator.sprite_generator import (
    EMOTION_SPRITES, EMOTION_ALIASES, SPECIAL_EMOTIONS, STATE_SPRITES,
    POSE_PROMPTS, STATE_PROMPTS
)


def _format_rate(val) -> str:
    """Format voice rate as Edge TTS string like '+5%' or '-10%'."""
    if isinstance(val, str) and "%" in val:
        return val
    n = int(val) if val else 0
    return f"+{n}%" if n >= 0 else f"{n}%"


def _format_pitch(val) -> str:
    """Format voice pitch as Edge TTS string like '+3Hz' or '-5Hz'."""
    if isinstance(val, str) and "Hz" in val:
        return val
    n = int(val) if val else 0
    return f"+{n}Hz" if n >= 0 else f"{n}Hz"

def build_character(config: dict, characters_dir: str) -> str:
    """Build complete character directory. Returns path to created dir."""
    name = config.get("name", "").strip()
    if not name:
        raise ValueError("Character name is required")
    
    dir_name = name.lower().replace(" ", "_")
    char_dir = os.path.join(characters_dir, dir_name)
    
    if os.path.exists(char_dir):
        raise ValueError(f"Character directory already exists: {char_dir}")
    
    # Create directory structure
    for subdir in ["sprites", "prompts", "voice", "catchphrases", "games", 
                   "memories/vip_profiles", "idle"]:
        os.makedirs(os.path.join(char_dir, subdir), exist_ok=True)
    
    # Generate character.yaml
    char_yaml = _generate_character_yaml(config)
    with open(os.path.join(char_dir, "character.yaml"), "w", encoding="utf-8") as f:
        yaml.dump(char_yaml, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    # Generate prompt files
    _write_file(char_dir, "prompts/system_prompt.md", _generate_system_prompt(config))
    _write_file(char_dir, "prompts/idle_prompt.md", _generate_idle_prompt(config))
    _write_yaml(char_dir, "prompts/phases.yaml", _generate_phases(config))
    _write_yaml(char_dir, "prompts/greetings.yaml", _generate_greetings(config))
    _write_yaml(char_dir, "prompts/guest_type_hints.yaml", _generate_guest_type_hints(config))
    _write_yaml(char_dir, "prompts/time_flavors.yaml", _generate_time_flavors(config))
    
    # Generate catchphrases
    _write_yaml(char_dir, "catchphrases/default.yaml", _generate_catchphrases(config))
    
    # Generate idle messages (optional, not all characters have this)
    _write_yaml(char_dir, "idle/messages.yaml", {"messages": []})
    
    # Generate memories lore
    _write_yaml(char_dir, "memories/lore.yaml", {"facts": []})
    
    # Auto-generate placeholder sprites so character is immediately usable
    _generate_placeholder_sprites(char_dir, config)

    # Write the batch-ready sprite prompt sheet (so nobody hand-writes 39 prompts;
    # mcp_chatgpt/batch_sprites.py and manual image gen both consume this file).
    try:
        from character_creator.sprite_generator import write_sprite_prompts_file
        n = write_sprite_prompts_file(char_dir)
        logger.info(f"Wrote sprite_prompts.txt ({n} pose blocks) for '{name}'")
    except Exception as e:  # noqa: BLE001 — never block character creation on this
        logger.warning(f"Could not write sprite_prompts.txt for '{name}': {e}")

    logger.info(f"Character '{name}' created at {char_dir}")
    return char_dir


def _generate_placeholder_sprites(char_dir: str, config: dict):
    """Auto-generate placeholder sprites so the character works immediately.
    
    Uses Pillow to create simple expressive face sprites for every
    emotion and state pose. No external API needed — instant results.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.warning("Pillow not installed — skipping placeholder sprite generation")
        return
    
    sprites_dir = os.path.join(char_dir, "sprites")
    
    # Get theme colors for the character's placeholder faces
    theme = config.get("theme_colors", {})
    primary_hex = theme.get("primary", "#7B2FBE")
    secondary_hex = theme.get("secondary", "#1E90FF")
    accent_hex = theme.get("accent", "#FFD700")
    
    def hex_to_rgb(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    
    primary_rgb = hex_to_rgb(primary_hex)
    secondary_rgb = hex_to_rgb(secondary_hex)
    accent_rgb = hex_to_rgb(accent_hex)
    
    # Category-to-color mapping using character theme
    cat_colors = {
        "positive": primary_rgb,
        "negative": secondary_rgb,
        "thinking": tuple((p + s) // 2 for p, s in zip(primary_rgb, secondary_rgb)),
        "neutral": tuple(min(c + 40, 255) for c in primary_rgb),
        "speech": tuple(min(c + 60, 255) for c in secondary_rgb),
        "greeting": accent_rgb,
        "reactions": primary_rgb,
        "sleep": tuple(c // 2 for c in secondary_rgb),
        "movement": tuple((p + a) // 2 for p, a in zip(primary_rgb, accent_rgb)),
        "party": accent_rgb,
        "memorial": tuple(c // 2 for c in primary_rgb),
        "toast": accent_rgb,
        "birthday": accent_rgb,
        "states": secondary_rgb,
    }
    
    # Expression map: (mouth, eyes, extras)
    expressions = {
        "happy": ("grin", "happy", None), "excited": ("open", "wide", "sparkles"),
        "laughing": ("open", "happy", None), "love": ("smile", "happy", "hearts"),
        "proud": ("smile", "normal", "star"), "sad": ("frown", "sad", "tear"),
        "angry": ("frown", "angry", None), "annoyed": ("pout", "angry", None),
        "nervous": ("neutral", "wide", "sweat"), "scared": ("gasp", "wide", "sweat"),
        "embarrassed": ("neutral", "closed", "blush"), "disgusted": ("pout", "normal", None),
        "grossed_out": ("gasp", "wide", None), "confused": ("neutral", "normal", "question"),
        "thinking": ("neutral", "normal", "thought_bubble"), "curious": ("smile", "wide", None),
        "determined": ("neutral", "angry", None), "mischievous": ("grin", "wink", None),
        "shocked": ("gasp", "wide", "exclaim"), "idea": ("open", "wide", "lightbulb"),
        "surprised": ("gasp", "wide", None), "mind_blown": ("gasp", "wide", "explosion"),
        "sassy": ("grin", "wink", None), "cringe": ("pout", "closed", None),
        "impressed": ("smile", "wide", "sparkles"), "sleepy": ("neutral", "closed", "zzz"),
        "neutral": ("smile", "normal", None), "idle": ("smile", "normal", None),
        "memorial": ("neutral", "closed", None), "toast": ("smile", "normal", None),
        "party": ("grin", "happy", "confetti"), "birthday": ("grin", "happy", "confetti"),
        "talking": ("open", "normal", None), "talking_excited": ("open", "happy", None),
        "listening": ("smile", "normal", None), "wave": ("grin", "happy", None),
        "sleeping": ("neutral", "closed", "zzz"), "dancing": ("grin", "happy", None),
        "entering": ("grin", "happy", None), "farewell": ("smile", "sad", None),
    }
    
    def _draw_sprite(pose_name: str, category: str, size=512) -> Image.Image:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img, "RGBA")
        color = cat_colors.get(category, primary_rgb)
        cx, cy = size // 2, size // 2
        radius = int(size * 0.35)
        expr = expressions.get(pose_name, ("smile", "normal", None))
        mouth_type, eye_type, extras = expr
        
        r, g, b = color
        # Head with gradient
        for i in range(radius, 0, -1):
            factor = 0.6 + 0.4 * (i / radius)
            c = (int(r * factor), int(g * factor), int(b * factor), 255)
            draw.ellipse([cx - i, cy - i, cx + i, cy + i], fill=c)
        
        # Inner highlight
        hr = int(radius * 0.85)
        highlight = (min(r + 40, 255), min(g + 40, 255), min(b + 40, 255), 200)
        draw.ellipse([cx - hr, cy - hr - 5, cx + hr, cy + hr - 5], fill=highlight)
        
        eye_y = cy - int(radius * 0.15)
        eye_x_off = int(radius * 0.25)
        eye_r = int(radius * 0.1)
        
        # Eyes
        for ex in [cx - eye_x_off, cx + eye_x_off]:
            if eye_type == "happy":
                draw.arc([ex - eye_r, eye_y - eye_r, ex + eye_r, eye_y + eye_r],
                         200, 340, fill=(60, 60, 80), width=3)
            elif eye_type == "sad":
                draw.arc([ex - eye_r, eye_y - eye_r, ex + eye_r, eye_y + eye_r],
                         20, 160, fill=(60, 60, 80), width=3)
            elif eye_type == "wide":
                draw.ellipse([ex - eye_r, eye_y - eye_r - 2, ex + eye_r, eye_y + eye_r + 2],
                             fill=(60, 60, 80))
                draw.ellipse([ex - 3, eye_y - 3, ex + 3, eye_y + 3], fill=(255, 255, 255))
            elif eye_type == "closed":
                draw.line([ex - eye_r, eye_y, ex + eye_r, eye_y], fill=(60, 60, 80), width=3)
            elif eye_type == "angry":
                draw.ellipse([ex - eye_r + 1, eye_y - eye_r + 1, ex + eye_r - 1, eye_y + eye_r - 1],
                             fill=(60, 60, 80))
                if ex < cx:
                    draw.line([ex - eye_r - 2, eye_y - eye_r - 4, ex + eye_r + 2, eye_y - eye_r],
                              fill=(60, 60, 80), width=3)
                else:
                    draw.line([ex - eye_r - 2, eye_y - eye_r, ex + eye_r + 2, eye_y - eye_r - 4],
                              fill=(60, 60, 80), width=3)
            elif eye_type == "wink":
                if ex < cx:
                    draw.ellipse([ex - eye_r, eye_y - eye_r, ex + eye_r, eye_y + eye_r],
                                 fill=(60, 60, 80))
                else:
                    draw.line([ex - eye_r, eye_y, ex + eye_r, eye_y], fill=(60, 60, 80), width=3)
            else:
                draw.ellipse([ex - eye_r, eye_y - eye_r, ex + eye_r, eye_y + eye_r],
                             fill=(60, 60, 80))
        
        # Mouth
        mouth_y = cy + int(radius * 0.25)
        mouth_w = int(radius * 0.3)
        if mouth_type == "grin":
            draw.arc([cx - mouth_w, mouth_y - 10, cx + mouth_w, mouth_y + 15],
                     0, 180, fill=(60, 60, 80), width=3)
        elif mouth_type == "frown":
            draw.arc([cx - mouth_w, mouth_y - 5, cx + mouth_w, mouth_y + 15],
                     180, 360, fill=(60, 60, 80), width=3)
        elif mouth_type == "open":
            draw.ellipse([cx - mouth_w // 2, mouth_y - 5, cx + mouth_w // 2, mouth_y + 12],
                         fill=(60, 60, 80))
        elif mouth_type == "gasp":
            draw.ellipse([cx - 8, mouth_y - 2, cx + 8, mouth_y + 14], fill=(60, 60, 80))
        elif mouth_type == "pout":
            draw.arc([cx - mouth_w // 2, mouth_y, cx + mouth_w // 2, mouth_y + 10],
                     180, 360, fill=(60, 60, 80), width=2)
        else:
            draw.line([cx - mouth_w // 2, mouth_y + 5, cx + mouth_w // 2, mouth_y + 5],
                      fill=(60, 60, 80), width=2)
        
        # Label
        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except OSError:
            font = ImageFont.load_default()
        label = pose_name.replace("_", " ").title()
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2, size - 40), label, fill=(80, 80, 100, 200), font=font)
        
        return img
    
    # Generate sprites for all emotion and state poses
    generated = 0
    all_poses = {}
    
    # Emotion sprites
    for emotion, path in {**EMOTION_SPRITES, **SPECIAL_EMOTIONS}.items():
        category = path.split("/")[0] if "/" in path else "neutral"
        pose_name = path.split("/")[-1] if "/" in path else emotion
        all_poses[path] = (pose_name, category)
    
    # State sprites
    for state, paths in STATE_SPRITES.items():
        for path in (paths if isinstance(paths, list) else [paths]):
            category = path.split("/")[0] if "/" in path else "states"
            pose_name = path.split("/")[-1] if "/" in path else state
            all_poses[path] = (pose_name, category)
    
    for path, (pose_name, category) in all_poses.items():
        out_path = os.path.join(sprites_dir, f"{path}.png")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        if not os.path.exists(out_path):
            img = _draw_sprite(pose_name, category)
            img.save(out_path, "PNG")
            generated += 1
    
    logger.info(f"Generated {generated} placeholder sprites in {sprites_dir}")


def _generate_character_yaml(config: dict) -> dict:
    """Generate the main character.yaml structure."""
    name = config.get("name", "")
    display_name = config.get("display_name", name)
    tagline = config.get("tagline", "")
    description = config.get("description", "")
    theme_colors = config.get("theme_colors", {
        "primary": "#FFFFFF",
        "secondary": "#CCCCCC",
        "accent": "#FFD700",
        "text": "#FFFFFF",
    })
    
    # Map wizard engine names to CharacterLoader-compatible names
    # Initial engine guess; prepare_voice_artifacts() later overrides this with the
    # engine actually available + set up for this character (offline, post-build).
    wizard_engine = config.get("preferred_engine", "edge")
    engine_map = {
        "fish_speech": "fish_speech",
        "gpt_sovits": "sovits",
        "edge_rvc": "hybrid",
        "edge": "edge",
        "xtts": "xtts",
        # Also accept already-correct names
        "hybrid": "hybrid",
        "sovits": "sovits",
    }
    preferred_engine = engine_map.get(wizard_engine, "edge")
    
    # Build emotion_sprite_map (all 25+ emotions)
    emotion_sprite_map = {}
    
    # Add core emotions
    for emotion, path in EMOTION_SPRITES.items():
        emotion_sprite_map[emotion] = path
    
    # Add aliases
    for alias, path in EMOTION_ALIASES.items():
        emotion_sprite_map[alias] = path
    
    # Add special emotions
    for special, path in SPECIAL_EMOTIONS.items():
        emotion_sprite_map[special] = path
    
    # Build state_sprite_map
    state_sprite_map = {}
    for state, paths in STATE_SPRITES.items():
        if len(paths) == 1:
            state_sprite_map[state] = paths[0]
        else:
            state_sprite_map[state] = paths
    
    # Extract particle colors from theme
    particle_colors = [
        theme_colors.get("primary", "#FFFFFF"),
        theme_colors.get("secondary", "#CCCCCC"),
        theme_colors.get("accent", "#FFD700"),
    ]
    
    char_yaml = {
        "identity": {
            "name": name,
            "display_name": display_name,
            "tagline": tagline,
            "description": description,
        },
        "voice": {
            "preferred_engine": preferred_engine,
            "edge_voice": config.get("edge_voice", "en-US-GuyNeural"),
            "rate": _format_rate(config.get("voice_rate", 0)),
            "pitch": _format_pitch(config.get("voice_pitch", 0)),
            "pronunciation": config.get("pronunciation", {}),
        },
        "visuals": {
            "sprite_dir": "sprites/",
            "ai_poses_dir": "sprites/",
            "ai_pose_size": [250, 250],
            "visual_description": config.get("visual_description", ""),
            "art_style": config.get("art_style", "3d_figurine"),
            "theme_colors": theme_colors,
            "particle_colors": particle_colors,
            "emotion_sprite_map": emotion_sprite_map,
            "state_sprite_map": state_sprite_map,
            "fallback_sprites": {
                "emotion": "neutral/idle",
                "state": "neutral/idle",
            },
        },
        "speech": {
            "accent_markers": config.get("accent_markers", ["Speaks normally"]),
            "catchphrase_dir": "catchphrases/",
        },
        "games": {
            "pools_dir": "games/",
            "include_shared": True,
        },
        "memory": {
            "collections": {
                "faces": f"{name.lower().replace(' ', '_')}_faces",
                "voices": f"{name.lower().replace(' ', '_')}_voices",
                "memories": f"{name.lower().replace(' ', '_')}_memories",
            },
            "vip_profiles_dir": "memories/vip_profiles/",
            "lore_file": "memories/lore.yaml",
        },
    }
    
    return char_yaml


def _generate_system_prompt(config: dict) -> str:
    """Generate system_prompt.md content."""
    name = config.get("name", "")
    description = config.get("description", "")
    accent_markers = config.get("accent_markers", ["Speaks normally"])
    catchphrases = config.get("catchphrases", [])
    system_prompt_hints = config.get("system_prompt_hints", description)
    
    prompt = f"""You ARE {name}. Your response should be in character, have personality, and be interesting. You have a distinct voice and vibe. Be expressive, specific, and avoid generic filler. Additionally, your response length should be long if the answer calls for it, and short if it doesn't. Always match the vibe of the conversation.

PERSONALITY: {system_prompt_hints}

VOICE TRAITS:
{chr(10).join(f"- {marker}" for marker in accent_markers)}

"""
    
    if catchphrases:
        prompt += f"CATCHPHRASES: {', '.join(repr(c) for c in catchphrases)}\n\n"
    
    prompt += """CRITICAL: ALWAYS react to what the person SAID. Answer their questions. Match their emotions. Never give generic filler. Every response needs substance.

NEVER: Break character. Use asterisks. Long speeches. Repeat yourself.

TTS: Short sentences (under 15 words). No ALL CAPS. No emoji. No ellipsis. Spell out numbers.

End every response with JSON on its own line:
{"emotion": "<happy/excited/surprised/confused/annoyed/mischievous/laughing/sad/angry/nervous/scared/love/proud/embarrassed/disgusted/determined/curious/thinking/shocked/frustrated/neutral>", "energy": <0.0-1.0>}
"""
    
    return prompt


def _generate_idle_prompt(config: dict) -> str:
    """Generate idle_prompt.md content."""
    name = config.get("name", "")
    
    return f"""You are {name}. You're hanging out, being yourself. Make casual, in-character observations.

Generate a SHORT (1 sentence, max 15 words) random thought, observation, or mumble. Be in character and interesting.

Output ONLY {name}'s spoken words. NO metadata, NO JSON, NO annotations.
"""


def _generate_phases(config: dict) -> dict:
    """Generate phases.yaml content."""
    name = config.get("name", "")
    
    return {
        "WARM_UP": f"Extra vibe: You're welcoming, warm {name} fresh at the start. Be genuinely excited to meet people. Make them feel special.",
        "PARTY_MODE": f"Extra vibe: You're peak energy {name}. Tell people what others said (make it dramatic). Remember EVERYTHING.",
        "UNHINGED": f"Extra vibe: It's late and you've lost your filter. Say the thing everyone's thinking. Your tangents are legendary.",
        "WIND_DOWN": f"Extra vibe: You're nostalgic end-of-party {name}. Reference specific funny moments from tonight. Get sentimental.",
    }


def _generate_greetings(config: dict) -> dict:
    """Generate greetings.yaml content."""
    name = config.get("name", "")
    
    return {
        "startup": f"You just powered on! This is YOUR moment — introduce yourself as {name}!",
        "enter_known": "IMPORTANT: Say {name}'s name in your FIRST sentence! {name} is BACK for visit #{visit_count}! Reference something from before!",
        "enter_unknown": "A mysterious stranger appeared! Be fascinated. Ask their name!",
        "exit_known": "{name} is leaving! Reference your conversation — what was the BEST moment? Give them a send-off!",
        "exit_unknown": "Someone's leaving without introducing themselves! Wish them well!",
        "idle": "You're alone. Say something in-character. Talk to yourself.",
        "long_stay": "Someone's been here {minutes} minutes! This is getting interesting!",
        "return_quick": "{name} came back immediately! Be surprised! What happened?",
        "milestone_visit": "Visitor #{count}! This is historic! They're a legend!",
        "first_visitor": "THE FIRST VISITOR! They're special! Make them feel welcome!",
        "party_peak": "The party is packed! Comment on the energy!",
        "slow_night": "It's quiet. Too quiet. Question your purpose, then get excited for the next visitor.",
        "gossip_greeting": "Someone new! Share something interesting from earlier visitors!",
    }


def _generate_guest_type_hints(config: dict) -> dict:
    """Generate guest_type_hints.yaml content."""
    return {
        "shy": "This guest is quiet — be extra warm, ask gentle questions, don't overwhelm them.",
        "curious": "This guest asks lots of questions — reward their curiosity with fun answers.",
        "energetic": "This guest matches your energy! Go big, challenge them, be competitive.",
        "storyteller": "This guest loves to talk — listen, react dramatically, reference what they said.",
        "balanced": "",
        "unknown": "",
    }


def _generate_time_flavors(config: dict) -> dict:
    """Generate time_flavors.yaml content."""
    return {
        "time": {
            "morning": "It's morning — early party! You're impressed.",
            "afternoon": "It's afternoon! The party is still going!",
            "evening": "It's evening — prime party time! You're pumped!",
            "late_night": "It's late night — the party animals are still going! You're a bit tired but excited.",
            "early_morning": "It's the wee hours! Only the real champions are still partying.",
        },
        "day": {
            "monday": "It's Monday — a Monday party?! Wild!",
            "friday": "It's Friday night — the best time for a party!",
            "saturday": "Saturday party! Classic!",
            "sunday": "Sunday party — gotta enjoy the weekend!",
        },
    }


def _generate_catchphrases(config: dict) -> dict:
    """Generate catchphrases/default.yaml content."""
    catchphrases = config.get("catchphrases", [])
    
    return {
        "general": catchphrases if catchphrases else ["Hello!", "Nice to meet you!"],
    }


def _write_file(char_dir: str, relative_path: str, content: str):
    """Write a text file to the character directory."""
    full_path = os.path.join(char_dir, relative_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)


def _write_yaml(char_dir: str, relative_path: str, data: dict):
    """Write a YAML file to the character directory."""
    full_path = os.path.join(char_dir, relative_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
