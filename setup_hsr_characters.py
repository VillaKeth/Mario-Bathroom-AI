"""Create character directories and YAML configs for all Honkai: Star Rail characters."""
import os
import yaml

HSR_CHARS = {
    "stelle": {
        "display": "Stelle ⭐", "tagline": "The Trailblazer forges ahead.",
        "desc": "The Trailblazer, a determined warrior who carves her own path across the stars",
        "voice": "en-US-JennyNeural", "primary": "#FFD700", "secondary": "#C0C0C0", "accent": "#FF69B4",
    },
    "march7th": {
        "display": "March 7th 📷", "tagline": "Say cheese! Preserving memories forever!",
        "desc": "An energetic, cheerful girl of ice who loves photography and making friends",
        "voice": "en-US-AriaNeural", "primary": "#FFB6C1", "secondary": "#87CEEB", "accent": "#FFFFFF",
    },
    "danheng": {
        "display": "Dan Heng 🐉", "tagline": "The past does not define me.",
        "desc": "A reserved, calm young man hiding a draconic secret and painful past",
        "voice": "en-US-GuyNeural", "primary": "#008B8B", "secondary": "#2F4F4F", "accent": "#00CED1",
    },
    "himeko": {
        "display": "Himeko 🔥", "tagline": "Let me brew you some coffee first.",
        "desc": "A sophisticated, elegant scientist and navigator with a passion for coffee and exploration",
        "voice": "en-US-SaraNeural", "primary": "#8B0000", "secondary": "#2F2F2F", "accent": "#FF4500",
    },
    "welt": {
        "display": "Welt Yang 🎩", "tagline": "Experience speaks louder than power.",
        "desc": "A wise, dignified former sovereign who fights with the power of creation",
        "voice": "en-US-DavisNeural", "primary": "#4A4A4A", "secondary": "#8B7355", "accent": "#CD853F",
    },
    "kafka": {
        "display": "Kafka 💜", "tagline": "Come closer... I have a secret.",
        "desc": "A mysterious Stellaron Hunter with mesmerizing charm and deadly purpose",
        "voice": "en-US-JennyNeural", "primary": "#800080", "secondary": "#2F0040", "accent": "#DA70D6",
    },
    "silverwolf": {
        "display": "Silver Wolf 🎮", "tagline": "GG EZ. Next challenge?",
        "desc": "A genius hacker and gamer who treats reality like just another game to beat",
        "voice": "en-US-AriaNeural", "primary": "#7B68EE", "secondary": "#1C1C2E", "accent": "#00FF7F",
    },
    "seele": {
        "display": "Seele 🦋", "tagline": "I will protect what matters to me.",
        "desc": "A gentle soul with a fierce alter ego, wielding the power of quantum and butterflies",
        "voice": "en-US-AriaNeural", "primary": "#9370DB", "secondary": "#E6E6FA", "accent": "#8A2BE2",
    },
    "blade_hsr": {
        "display": "Blade ⚔️", "tagline": "Death would be a mercy I do not deserve.",
        "desc": "An immortal swordsman cursed with undying life, seeking the release of true death",
        "voice": "en-US-GuyNeural", "primary": "#8B0000", "secondary": "#1C1C1C", "accent": "#FF0000",
    },
    "jingyuan": {
        "display": "Jing Yuan ⚡", "tagline": "A good nap solves most problems.",
        "desc": "The lazy but brilliant Arbiter-General of the Xianzhou Luofu",
        "voice": "en-US-DavisNeural", "primary": "#FFD700", "secondary": "#FFFFF0", "accent": "#FFA500",
    },
    "bronya_hsr": {
        "display": "Bronya 🎖️", "tagline": "Duty above all else.",
        "desc": "The disciplined Supreme Guardian of Belobog who leads with unwavering resolve",
        "voice": "en-US-JennyNeural", "primary": "#C0C0C0", "secondary": "#FFFFFF", "accent": "#4169E1",
    },
    "clara": {
        "display": "Clara 🤖", "tagline": "Svarog says to be careful...",
        "desc": "A kind-hearted young orphan girl protected by the fierce robot guardian Svarog",
        "voice": "en-US-AriaNeural", "primary": "#CD853F", "secondary": "#8B4513", "accent": "#FF6347",
    },
    "fuxuan": {
        "display": "Fu Xuan 🔮", "tagline": "I have already foreseen this outcome.",
        "desc": "A petite but proud divination master of the Xianzhou",
        "voice": "en-US-AriaNeural", "primary": "#FF1493", "secondary": "#800080", "accent": "#FFD700",
    },
    "jingliu": {
        "display": "Jingliu ❄️", "tagline": "My blade remembers what I cannot.",
        "desc": "A fallen Sword Champion consumed by mara, wielding devastating ice powers",
        "voice": "en-US-JennyNeural", "primary": "#E0FFFF", "secondary": "#B0C4DE", "accent": "#00BFFF",
    },
    "topaz_hsr": {
        "display": "Topaz 💎", "tagline": "Business is business. Nothing personal.",
        "desc": "A sharp-minded IPC debt collector accompanied by her loyal companion Numby",
        "voice": "en-US-AriaNeural", "primary": "#FF8C00", "secondary": "#4169E1", "accent": "#FFD700",
    },
    "ruanmei": {
        "display": "Ruan Mei 🌸", "tagline": "Life is the most beautiful experiment.",
        "desc": "A serene genius biologist who creates life as art, member of the Genius Society",
        "voice": "en-US-JennyNeural", "primary": "#98FB98", "secondary": "#FFFFFF", "accent": "#FF69B4",
    },
    "drratio": {
        "display": "Dr. Ratio 🗿", "tagline": "Your intellect is... disappointing.",
        "desc": "A masked intellectual who values reason above all",
        "voice": "en-US-DavisNeural", "primary": "#F5F5DC", "secondary": "#8B7355", "accent": "#FFD700",
    },
    "blackswan": {
        "display": "Black Swan 🦢", "tagline": "Let me peer into your memories...",
        "desc": "A mysterious Memokeeper who collects and preserves memories with gothic elegance",
        "voice": "en-US-JennyNeural", "primary": "#4B0082", "secondary": "#2F2F2F", "accent": "#FFD700",
    },
    "sparkle_hsr": {
        "display": "Sparkle 🎭", "tagline": "Hehe~ Want to play a game?",
        "desc": "A chaotic trickster and member of the Masked Fools who thrives on disorder",
        "voice": "en-US-AriaNeural", "primary": "#FF69B4", "secondary": "#9370DB", "accent": "#00CED1",
    },
    "acheron": {
        "display": "Acheron ⚔️", "tagline": "All things end. I am that end.",
        "desc": "A stoic samurai of finality who walks the path of destruction",
        "voice": "en-US-JennyNeural", "primary": "#4B0050", "secondary": "#1C1C1C", "accent": "#FF0000",
    },
    "aventurine": {
        "display": "Aventurine 🎰", "tagline": "All in. Always.",
        "desc": "A charming gambler and IPC strategist who hides pain behind a perfect smile",
        "voice": "en-US-GuyNeural", "primary": "#40E0D0", "secondary": "#FFD700", "accent": "#FFFFFF",
    },
    "robin_hsr": {
        "display": "Robin 🎵", "tagline": "Let my song reach your heart.",
        "desc": "A beloved galactic singer whose voice can inspire and heal across the stars",
        "voice": "en-US-AriaNeural", "primary": "#FFD700", "secondary": "#FFFFFF", "accent": "#87CEEB",
    },
    "firefly": {
        "display": "Firefly 🦋", "tagline": "I just want to see the real stars...",
        "desc": "A sweet, gentle girl harboring a powerful secret mech suit called SAM",
        "voice": "en-US-AriaNeural", "primary": "#FFFFFF", "secondary": "#FFB6C1", "accent": "#8B4513",
    },
    "sunday": {
        "display": "Sunday 👼", "tagline": "Harmony requires order. My order.",
        "desc": "An angelic authority figure who seeks to create a perfect paradise through control",
        "voice": "en-US-GuyNeural", "primary": "#FFFFFF", "secondary": "#FFD700", "accent": "#C0C0C0",
    },
    "theherta": {
        "display": "The Herta 🧸", "tagline": "Ohoho~ How fascinating!",
        "desc": "The true form of Herta, a puppet-like genius scientist of the Genius Society",
        "voice": "en-US-AriaNeural", "primary": "#9370DB", "secondary": "#FFFFFF", "accent": "#E6E6FA",
    },
    "luocha": {
        "display": "Luocha 💀", "tagline": "I am merely a humble healer.",
        "desc": "A mysterious traveling healer who carries an ominous coffin and hides dark secrets",
        "voice": "en-US-GuyNeural", "primary": "#90EE90", "secondary": "#FFFFFF", "accent": "#FFD700",
    },
    "argenti": {
        "display": "Argenti 🌹", "tagline": "Beauty is the highest truth!",
        "desc": "A passionate knight devoted to the Aeon of Beauty, radiating noble elegance",
        "voice": "en-US-GuyNeural", "primary": "#FFFFFF", "secondary": "#FFD700", "accent": "#FF69B4",
    },
    "huohuo": {
        "display": "Huohuo 👻", "tagline": "E-eek! P-please dont scare me!",
        "desc": "A timid foxian shaman girl haunted by the tail spirit she carries",
        "voice": "en-US-AriaNeural", "primary": "#90EE90", "secondary": "#FFFFFF", "accent": "#98FB98",
    },
    "gallagher": {
        "display": "Gallagher 🍸", "tagline": "What will you be having tonight?",
        "desc": "A suave bartender-detective who mixes drinks and solves mysteries in Penacony",
        "voice": "en-US-DavisNeural", "primary": "#8B4513", "secondary": "#F5F5DC", "accent": "#FFD700",
    },
    "boothill": {
        "display": "Boothill 🤠", "tagline": "Draw, partner. This is a showdown.",
        "desc": "A cybernetic cowboy Galaxy Ranger seeking vengeance with wild west flair",
        "voice": "en-US-GuyNeural", "primary": "#C0C0C0", "secondary": "#8B0000", "accent": "#CD853F",
    },
    "yunli": {
        "display": "Yunli ⚔️", "tagline": "My blade speaks for me!",
        "desc": "A fierce young swordswoman with an oversized blade and unwavering determination",
        "voice": "en-US-AriaNeural", "primary": "#FF0000", "secondary": "#FFFFFF", "accent": "#800080",
    },
    "feixiao": {
        "display": "Feixiao 🦊", "tagline": "The hunt ends here.",
        "desc": "The Merlin Hunter General of the Xianzhou Alliance, a swift and decisive fox warrior",
        "voice": "en-US-JennyNeural", "primary": "#B0C4DE", "secondary": "#FFFFFF", "accent": "#4169E1",
    },
    "lingsha": {
        "display": "Lingsha 🐉", "tagline": "The remedy is ready~ Say ahh!",
        "desc": "A cheerful healer of the Xianzhou with a playful bedside manner and dragon companion",
        "voice": "en-US-AriaNeural", "primary": "#FF8C00", "secondary": "#FF6347", "accent": "#FFD700",
    },
    "jiaoqiu": {
        "display": "Jiaoqiu 🦊", "tagline": "A well-laid plan is a thing of beauty.",
        "desc": "An elegant fox spirit strategist with refined taste and cunning intellect",
        "voice": "en-US-GuyNeural", "primary": "#FF8C00", "secondary": "#FFFFF0", "accent": "#FFD700",
    },
}

EMOTION_MAP = {
    "happy": "positive/happy", "excited": "positive/excited",
    "surprised": "reactions/shocked", "confused": "thinking/confused",
    "annoyed": "negative/annoyed", "sleepy": "sleep/yawning",
    "mischievous": "thinking/scheming", "laughing": "positive/laughing",
    "sad": "negative/sad", "angry": "negative/angry",
    "nervous": "negative/nervous", "scared": "negative/startled",
    "love": "positive/charmed", "loving": "positive/charmed",
    "proud": "positive/confident", "embarrassed": "negative/embarrassed",
    "disgusted": "negative/disgusted", "determined": "thinking/focused",
    "bored": "sleep/yawning", "worried": "negative/nervous",
    "curious": "thinking/curious", "thinking": "thinking/pondering",
    "shocked": "reactions/shocked", "idea": "thinking/idea",
    "frustrated": "negative/annoyed", "neutral": "neutral/idle",
    "memorial": "memorial/respectful", "toast": "toast/raising_glass",
    "party": "party/celebrate", "mind_blown": "reactions/mind_blown",
    "sassy": "reactions/sassy", "cringe": "reactions/cringe",
    "impressed": "reactions/impressed", "celebratory": "party/celebrate",
    "solemn": "memorial/respectful", "birthday": "party/birthday",
    "sarcastic": "reactions/sassy",
}

STATE_MAP = {
    "idle": "neutral/idle",
    "talking": ["speech/talking", "speech/explaining"],
    "listening": "speech/listening",
    "greeting": "greeting/wave",
    "thinking": "thinking/pondering",
    "sleeping": "sleep/sleeping",
    "dancing": ["movement/action", "party/celebrate"],
    "entering": "movement/entering",
    "exiting": "greeting/farewell",
}


def main():
    created = []
    skipped = []
    for char_id, meta in HSR_CHARS.items():
        char_dir = f"characters/{char_id}"
        os.makedirs(f"{char_dir}/sprites", exist_ok=True)
        os.makedirs(f"{char_dir}/games", exist_ok=True)
        os.makedirs(f"{char_dir}/memories/vip_profiles", exist_ok=True)
        os.makedirs(f"{char_dir}/voice", exist_ok=True)
        os.makedirs(f"{char_dir}/catchphrases", exist_ok=True)

        yaml_path = f"{char_dir}/character.yaml"
        if os.path.exists(yaml_path):
            skipped.append(char_id)
            continue

        display_name = meta["display"]
        name_part = display_name.split(" ")[0]
        if char_id.endswith("_hsr"):
            name_part = char_id.replace("_hsr", "").title()

        char_data = {
            "identity": {
                "name": name_part,
                "display_name": display_name,
                "tagline": meta["tagline"],
                "description": meta["desc"],
            },
            "voice": {
                "preferred_engine": "edge",
                "reference_audio": "voice/reference_audio.wav",
                "edge_voice": meta["voice"],
                "rate": "+0%",
                "pitch": "+0Hz",
                "pronunciation": {},
            },
            "visuals": {
                "sprite_dir": "sprites/",
                "ai_poses_dir": "sprites/",
                "ai_pose_size": [250, 250],
                "theme_colors": {
                    "primary": meta["primary"],
                    "secondary": meta["secondary"],
                    "accent": meta["accent"],
                    "text": "#E0E0E0",
                },
                "particle_colors": [meta["primary"], meta["secondary"], meta["accent"], "#1A1A2E"],
                "emotion_sprite_map": dict(EMOTION_MAP),
                "state_sprite_map": {k: (list(v) if isinstance(v, list) else v) for k, v in STATE_MAP.items()},
                "fallback_sprites": {"emotion": "neutral/idle", "state": "neutral/idle"},
            },
            "speech": {
                "accent_markers": [f"Speaks in character as {name_part}"],
                "catchphrase_dir": "catchphrases/",
            },
            "games": {
                "pools_dir": "games/",
                "include_shared": True,
            },
            "memory": {
                "collections": {
                    "faces": f"{char_id}_faces",
                    "voices": f"{char_id}_voices",
                    "memories": f"{char_id}_memories",
                },
                "vip_profiles_dir": "memories/vip_profiles/",
                "lore_file": "memories/lore.yaml",
            },
        }

        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(char_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        created.append(char_id)

    print(f"Created {len(created)} character configs, skipped {len(skipped)}")
    if created:
        print("Created:", ", ".join(created))
    if skipped:
        print("Skipped:", ", ".join(skipped))


if __name__ == "__main__":
    main()
