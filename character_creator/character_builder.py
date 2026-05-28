"""Character builder — generates character directory from wizard config."""
import os
import yaml
import logging

logger = logging.getLogger(__name__)

# Import emotion/state sprites from sprite_generator
from character_creator.sprite_generator import (
    EMOTION_SPRITES, EMOTION_ALIASES, SPECIAL_EMOTIONS, STATE_SPRITES
)

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
    
    logger.info(f"Character '{name}' created at {char_dir}")
    return char_dir


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
    wizard_engine = config.get("preferred_engine", "edge")
    engine_map = {
        "fish_speech": "hybrid",
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
            "rate": config.get("voice_rate", "+0%"),
            "pitch": config.get("voice_pitch", "+0Hz"),
            "pronunciation": config.get("pronunciation", {}),
        },
        "visuals": {
            "sprite_dir": "sprites/",
            "ai_poses_dir": "sprites/ai_poses/",
            "ai_pose_size": [250, 250],
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
    
    prompt = f"""You ARE {name}. 2-3 sentences max.

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
