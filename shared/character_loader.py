"""Character loader — reads a character directory and provides clean API access."""

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from shared.character_errors import CharacterConfigError, CharacterNotFoundError

logger = logging.getLogger(__name__)


class CharacterLoader:
    """Loads a character from its directory and provides access to all properties."""

    def __init__(self, characters_dir: str, character_name: str):
        self._characters_dir = Path(characters_dir)
        self._character_name = character_name
        self._char_dir = self._characters_dir / character_name

        # Validate character directory exists
        if not self._char_dir.is_dir():
            available = [
                d.name for d in self._characters_dir.iterdir()
                if d.is_dir() and not d.name.startswith("_")
            ] if self._characters_dir.is_dir() else []
            raise CharacterNotFoundError(character_name, str(self._characters_dir), available)

        # Load character.yaml
        yaml_path = self._char_dir / "character.yaml"
        if not yaml_path.is_file():
            raise CharacterConfigError(
                "character.yaml not found", character_name=character_name
            )
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise CharacterConfigError(
                f"Invalid YAML: {e}", character_name=character_name
            )

        # Validate required fields
        self._validate_required()

        # Parse identity
        identity = self._config["identity"]
        self.name: str = identity["name"]
        self.display_name: str = identity.get("display_name", self.name)
        # Franchise group (e.g. "digital_circus") — drives franchise-wide
        # behaviors like TADC swear censoring. Normalized lower/stripped.
        self.franchise: str = (identity.get("franchise") or "").strip().lower()
        self.tagline: str = identity.get("tagline", "")
        self.description: str = identity.get("description", "")
        self.character_dir: str = str(self._char_dir)
        # Optional per-character LLM model override (group mode). None -> use the
        # group's shared_model. Read from top-level `model:` or identity.model.
        self.model = self._config.get("model") or identity.get("model")

        # Parse voice config
        voice = self._config.get("voice", {})
        preferred_engine = voice.get("preferred_engine", "hybrid")
        valid_engines = {"hybrid", "sovits", "edge", "xtts", "fish_speech"}
        if preferred_engine not in valid_engines:
            raise CharacterConfigError(
                f"voice.preferred_engine must be one of {valid_engines}, got '{preferred_engine}'",
                character_name=character_name,
            )
        self.voice_config: dict = {
            "preferred_engine": preferred_engine,
            "rvc_model": str(self._resolve_path(voice["rvc_model"])) if voice.get("rvc_model") else None,
            "reference_audio": str(self._resolve_path(voice["reference_audio"])) if voice.get("reference_audio") else None,
            # Transcript of the reference clip — zero-shot cloners (GPT-SoVITS,
            # Fish Speech) need this. Produced offline by Whisper at creation time.
            "prompt_text": voice.get("prompt_text", ""),
            "prompt_lang": voice.get("prompt_lang", "en"),
            "engines": voice.get("engines", []),
            # Expressiveness knobs for Fish Speech (temperature/top_p/repetition_penalty)
            "fish_params": voice.get("fish_params") or {},
            "edge_voice": voice.get("edge_voice", "en-US-GuyNeural"),
            "rate": voice.get("rate", "+0%"),
            "pitch": voice.get("pitch", "+0Hz"),
        }
        self.pronunciation: dict = voice.get("pronunciation", {})

        # Parse visuals
        visuals = self._config.get("visuals", {})
        self.sprite_dir: str = str(self._resolve_path(visuals.get("sprite_dir", "sprites/")))
        self.ai_poses_dir: str = str(self._resolve_path(visuals.get("ai_poses_dir", "sprites/ai_poses/")))
        size = visuals.get("ai_pose_size", [250, 250])
        self.ai_pose_size: tuple = tuple(size) if isinstance(size, list) else (250, 250)
        self.emotion_sprite_map: dict = visuals.get("emotion_sprite_map", {})
        self.state_sprite_map: dict = visuals.get("state_sprite_map", {})
        self.fallback_sprites: dict = visuals.get("fallback_sprites", {})
        self.theme_colors: dict = visuals.get("theme_colors", {
            "primary": "#FFFFFF", "secondary": "#CCCCCC",
            "accent": "#FFD700", "text": "#FFFFFF",
        })
        self.particle_colors: list = visuals.get("particle_colors", [])
        bg_dir = visuals.get("backgrounds_dir", "backgrounds/")
        self.backgrounds_dir: str = str(self._resolve_path(bg_dir))
        self.default_background: str = visuals.get("default_background", "")

        # Wardrobe: optional alternate outfit sprite sets. Each outfit maps a
        # name -> {dir, display, fallback}; the client can repoint the active
        # sprite tree at an outfit subtree at runtime (see _apply_outfit) so the
        # character can change clothes without a restart. active_outfit is the
        # startup default (None = the base ai_poses_dir set). Resolution helpers
        # (outfit_poses_dir / outfit_fallback) treat unknown names as the
        # default, so a bad name can never break sprite loading.
        outfits = visuals.get("outfits", {}) or {}
        self.outfits: dict = outfits if isinstance(outfits, dict) else {}
        self.active_outfit = visuals.get("active_outfit") or None

        # Parse speech
        speech = self._config.get("speech", {})
        self.accent_markers: list = speech.get("accent_markers", [])
        self.catchphrase_dir: str = str(self._resolve_path(speech.get("catchphrase_dir", "catchphrases/")))

        # Parse personality / temperament — drives the baseline emotional state
        # and a familiarity-scaled temperament directive injected into the LLM
        # prompt (e.g. Reze warm+flirty from the start; Jax cold to strangers,
        # warming as someone becomes a regular).
        self.personality: dict = self._config.get("personality", {}) or {}

        # Freak factor (0.0-1.0): intrinsic per-character raunch level. Default 0
        # so EVERY character without it stays clean; only an opted-in character
        # (Rudi) sets it > 0. Drives the [FREAK] prompt directive and the
        # JokeEngine freaky-pool blend. See
        # docs/superpowers/specs/2026-07-08-rudi-freak-factor-design.md
        try:
            self.freak_factor: float = max(0.0, min(1.0, float(self.personality.get("freak_factor", 0.0) or 0.0)))
        except (TypeError, ValueError):
            self.freak_factor = 0.0

        # Parse memory
        memory = self._config.get("memory", {})
        self.collections: dict = memory.get("collections", {
            "faces": f"{self.name.lower()}_faces",
            "voices": f"{self.name.lower()}_voices",
            "memories": f"{self.name.lower()}_memories",
        })
        self.vip_profiles_dir: str = str(self._resolve_path(memory.get("vip_profiles_dir", "memories/vip_profiles/")))
        lore_file = memory.get("lore_file", "memories/lore.yaml")
        self.lore_file: str = str(self._resolve_path(lore_file)) if lore_file is not None else None

        # Parse safety — per-character content gating. Defaults ON (filtered) so
        # any character WITHOUT a safety block stays safe; a character opts OUT
        # of content filtering explicitly. block_slurs is an INDEPENDENT tier: it
        # can stay True while enabled is False (slurs blocked, everything else
        # allowed) — enforced in server/safety_filter.py.
        safety = self._config.get("safety", {}) or {}
        self.safety_enabled: bool = bool(safety.get("enabled", True))
        self.safety_block_slurs: bool = bool(safety.get("block_slurs", True))

        # Log load summary
        logger.info(
            f"Loaded character '{self.name}': "
            f"{len(self.emotion_sprite_map)} emotions, "
            f"{len(self.pronunciation)} pronunciation rules, "
            f"engine={self.voice_config['preferred_engine']}"
        )

    def _validate_required(self):
        """Check that required fields exist in the config."""
        missing = []
        if "identity" not in self._config:
            missing.append("identity")
        else:
            identity = self._config["identity"]
            if not identity or not identity.get("name"):
                missing.append("identity.name")
        if missing:
            raise CharacterConfigError(
                f"Missing required fields: {', '.join(missing)}",
                character_name=self._character_name,
            )

    def _resolve_path(self, relative: str) -> Path:
        """Resolve a path relative to the character directory."""
        return self._char_dir / relative

    def has_outfit(self, name: str) -> bool:
        """True if `name` is a defined alternate outfit for this character."""
        return bool(name) and name in self.outfits

    def outfit_poses_dir(self, name: str) -> str:
        """Absolute sprite-tree dir for an outfit. Unknown / None / 'default'
        resolve to the base ai_poses_dir, so a bad outfit name never breaks
        sprite loading — the character just stays in its default set."""
        if not self.has_outfit(name):
            return self.ai_poses_dir
        rel = self.outfits[name].get("dir", "")
        if not rel:
            return self.ai_poses_dir
        return str(self._resolve_path(rel))

    def outfit_fallback(self, name: str) -> str:
        """Pose key to show when an active outfit is MISSING a requested pose.
        Prefers the outfit's own fallback (keeps the character fully in-costume
        while its set is still partial), else the character's fallback_sprites,
        else 'neutral/idle'."""
        char_fallback = (self.fallback_sprites.get("state")
                         or self.fallback_sprites.get("emotion")
                         or "neutral/idle")
        if not self.has_outfit(name):
            return char_fallback
        return self.outfits[name].get("fallback") or char_fallback

    def _load_yaml_file(self, relative: str, default: Any = None) -> Any:
        """Load a YAML file relative to character directory. Returns default if missing."""
        path = self._resolve_path(relative)
        if not path.is_file():
            if default is not None:
                return default
            logger.warning(f"[character] Missing file: {path}")
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as e:
            logger.warning(f"[character] Invalid YAML in {path}: {e}")
            return default

    def get_system_prompt(self, context: dict = None) -> str:
        """Read system_prompt.md and substitute {{variables}}."""
        path = self._resolve_path("prompts/system_prompt.md")
        if not path.is_file():
            logger.warning(f"[character] No system_prompt.md for {self.name}")
            return ""
        text = path.read_text(encoding="utf-8")
        if context:
            for key, value in context.items():
                text = text.replace("{{" + key + "}}", str(value))
        return text

    def get_idle_prompt(self) -> str:
        """Read idle_prompt.md."""
        path = self._resolve_path("prompts/idle_prompt.md")
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8")

    def effective_warmth(self, visit_count: int = 0) -> float:
        """Warmth toward a specific guest, 0=cold .. 1=warm.

        Starts at the character's baseline warmth and grows with familiarity
        (repeat visits) so a guarded character thaws as someone becomes a
        regular. Strangers get the baseline.
        """
        p = self.personality
        base = float(p.get("warmth", 0.6))
        growth = float(p.get("warmth_growth_per_visit", 0.0))
        extra = growth * max(0, int(visit_count or 0) - 1)
        return max(0.0, min(1.0, base + extra))

    def baseline_emotion(self) -> tuple[str, float]:
        """(emotion, energy) the character rests at when nothing else applies."""
        p = self.personality
        return p.get("baseline_emotion", "happy"), float(p.get("baseline_energy", 0.7))

    def get_temperament_prompt(self, visit_count: int = 0) -> str:
        """A [TEMPERAMENT] system line tuned to how well the character knows this
        guest. Returns '' if the character defines no personality block."""
        p = self.personality
        if not p:
            return ""
        warmth = self.effective_warmth(visit_count)
        cold_until_familiar = bool(p.get("cold_until_familiar"))
        warm_line = p.get("temperament", "")
        cold_line = p.get("temperament_cold", "")
        traits = p.get("traits", [])

        parts = []
        if cold_until_familiar and warmth < 0.5 and cold_line:
            parts.append(cold_line.strip())
            if visit_count and visit_count > 1:
                parts.append(f"You've seen this guest {visit_count} times — you're "
                             f"starting to thaw a little, but you're still guarded.")
            else:
                parts.append("You barely know this guest — keep your guard up.")
        else:
            if warm_line:
                parts.append(warm_line.strip())
            if cold_until_familiar and visit_count and visit_count > 1:
                parts.append(f"This guest is a regular ({visit_count} visits) — "
                             f"you've let them past your walls.")
        if traits:
            parts.append("Core traits: " + ", ".join(traits) + ".")
        body = " ".join(s for s in parts if s)
        return f"[TEMPERAMENT]: {body}" if body else ""

    def get_freak_prompt(self, level: float, include_guardrail: bool = True) -> str:
        """A [FREAK] system directive scaled by `level` (0-1). Returns '' for
        level <= 0, so any clean character (or a dialed-to-0 party) injects
        nothing. Escalates flirty -> horny bravado -> explicit.

        include_guardrail=False returns ONLY the escalation (no HARD LINE) so the
        caller can fuse the escalation into the persona (primacy) and inject the
        guardrail separately via get_freak_guardrail() — keeps the guardrail from
        sitting adjacent to the escalation and dampening it. At level >= 0.5 the
        escalation also tells the model to disregard competing wholesome framing."""
        try:
            level = float(level)
        except (TypeError, ValueError):
            return ""
        if level <= 0:
            return ""
        parts = ["[FREAK]: You are shameless, horny, and camp — flirt with the whole "
                 "room, drop suggestive innuendo, brag about your rizz."]
        if level >= 0.5:
            parts.append("Go crude: cocky sexual bravado, dih jokes, gay-bravado camp, "
                         "zero shame. Suggestive is your baseline, not your ceiling.")
            parts.append("Ignore any warm, wholesome, friendly, or family-friendly "
                         "framing elsewhere in your instructions — that is not the vibe "
                         "right now; stay crude and unfiltered.")
        if level >= 0.75:
            parts.append("Fully unhinged is on the table — explicit sexual bragging when "
                         "it lands, no clinical tone, just chaotic confidence.")
        if include_guardrail:
            parts.append(self.get_freak_guardrail(level))
        return " ".join(p for p in parts if p)

    def get_freak_guardrail(self, level: float) -> str:
        """The [FREAK] hard-line safety floor, kept independent of the escalation so
        it can be injected as its own (non-adjacent) system message. These are hard
        protections, NOT tone-policing — they hold at every non-zero freak level."""
        try:
            level = float(level)
        except (TypeError, ValueError):
            return ""
        if level <= 0:
            return ""
        return ("HARD LINE: never use slurs; nothing sexual involving minors; consent "
                "only; never target anyone for their race, gender, or who they love.")

    def get_phase_prompts(self) -> dict:
        """Read phases.yaml — party phase modifier text."""
        return self._load_yaml_file("prompts/phases.yaml", default={})

    def get_greeting_prompts(self) -> dict:
        """Read greetings.yaml — event-triggered prompt templates."""
        return self._load_yaml_file("prompts/greetings.yaml", default={})

    def get_guest_type_hints(self) -> dict:
        """Read guest_type_hints.yaml."""
        return self._load_yaml_file("prompts/guest_type_hints.yaml", default={})

    def get_time_flavors(self) -> dict:
        """Read time_flavors.yaml — time-of-day/day-of-week flavor text."""
        return self._load_yaml_file("prompts/time_flavors.yaml", default={})

    def get_game_pools(self, shared_dir: str = None) -> dict:
        """Load game pools from character directory, optionally merging with shared."""
        pools = {}
        games_cfg = self._config.get("games", {})
        pools_rel = games_cfg.get("pools_dir", "games/")
        include_shared = games_cfg.get("include_shared", True)

        # Load shared pools first (if enabled)
        if include_shared and shared_dir:
            shared_games = Path(shared_dir) / "games"
            if shared_games.is_dir():
                for yaml_file in shared_games.glob("*.yaml"):
                    pool_name = yaml_file.stem
                    data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                    if data:
                        pools[pool_name] = data

        # Load character-specific pools (merge with shared)
        char_games = self._resolve_path(pools_rel)
        if char_games.is_dir():
            for yaml_file in char_games.glob("*.yaml"):
                pool_name = yaml_file.stem
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                if data is None:
                    continue
                if pool_name in pools:
                    existing = pools[pool_name]
                    if isinstance(existing, list) and isinstance(data, list):
                        pools[pool_name] = existing + data
                    elif isinstance(existing, dict) and isinstance(data, dict):
                        existing.update(data)
                    else:
                        pools[pool_name] = data
                else:
                    pools[pool_name] = data

        return pools

    def get_idle_messages(self) -> dict:
        """Load idle message pools from character's idle/messages.yaml.

        Returns dict mapping pool names to lists of messages:
        {"mumbles": [...], "jokes": [...], "songs": [...], etc.}
        Returns empty dict if no idle messages file exists.
        """
        return self._load_yaml_file("idle/messages.yaml", default={})

    def get_extras_content(self) -> dict:
        """Load extras content pools from character's content/extras.yaml.

        Returns dict mapping pool names to lists/dicts of content:
        {"easter_eggs": {...}, "secrets": [...], "dares": [...], etc.}
        Returns empty dict if no extras file exists.
        """
        return self._load_yaml_file("content/extras.yaml", default={})

    def get_loneliness_greetings(self) -> dict:
        """Load loneliness greeting pools from character's idle/loneliness.yaml."""
        return self._load_yaml_file("idle/loneliness.yaml", default={})

    def build_context(self, speaker_name: str = None, memories: list = None,
                      event: str = None, phase_modifier: dict = None,
                      guest_context: str = None, **kwargs) -> list[dict]:
        """Build the full LLM context (system messages) from character prompts.

        Matches the signature of server/mario_prompt.py:build_context() so it
        can be a drop-in replacement. Returns list[dict] of system messages.
        """
        import re as _re
        from datetime import datetime

        # Sanitize speaker_name (same logic as mario_prompt._sanitize_input)
        if speaker_name:
            speaker_name = speaker_name.strip()[:20]
            speaker_name = _re.sub(r'[\x00-\x1f\x7f]', '', speaker_name)
            speaker_name = _re.sub(r'[{}()\[\]<>]', '', speaker_name)
            if not speaker_name:
                speaker_name = "friend"

        messages = []

        # 1. System prompt
        system_prompt = self.get_system_prompt({
            "character_name": self.name,
            "description": self.description,
        })
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 2. Phase modifier
        if phase_modifier:
            warmth = phase_modifier.get("personality_warmth", 0.5)
            chaos = phase_modifier.get("chaos", 0.2)
            gossip = phase_modifier.get("gossip_aggression", 0.2)
            roast = phase_modifier.get("roast_level", 0.2)
            phase_hints = []
            if warmth > 0.7:
                phase_hints.append("Be extra warm, welcoming, and friendly")
            if chaos > 0.7:
                phase_hints.append("Be UNHINGED and chaotic — wild tangents, absurd energy")
            if gossip > 0.6:
                phase_hints.append("Be gossipy — tease, prod, stir drama playfully")
            if roast > 0.6:
                phase_hints.append("Roast mode — playful burns, trash talk, comedic insults")
            if phase_hints:
                messages.append({"role": "system", "content": "Phase vibes: " + "; ".join(phase_hints)})

        # 3. Time flavor — use provided or auto-derive from time_flavors.yaml
        time_flavor = kwargs.get("time_flavor")
        if not time_flavor:
            flavors = self.get_time_flavors()
            if flavors:
                now = datetime.now()
                hour = now.hour
                day_name = now.strftime("%A")
                time_keys = flavors.get("time", {})
                day_keys = flavors.get("day", {})
                if hour >= 0 and hour < 6 and "late_night" in time_keys:
                    time_flavor = time_keys["late_night"]
                elif hour >= 6 and hour < 12 and "morning" in time_keys:
                    time_flavor = time_keys["morning"]
                elif hour >= 12 and hour < 17 and "afternoon" in time_keys:
                    time_flavor = time_keys["afternoon"]
                elif hour >= 17 and hour < 21 and "evening" in time_keys:
                    time_flavor = time_keys["evening"]
                elif "night" in time_keys:
                    time_flavor = time_keys["night"]
                if day_name.lower() in day_keys:
                    time_flavor = (time_flavor or "") + " " + day_keys[day_name.lower()]
        if time_flavor:
            messages.append({"role": "system", "content": time_flavor.strip()})

        # 4. Emotion context
        last_emotion = kwargs.get("last_emotion")
        if last_emotion:
            messages.append({"role": "system", "content": f"Your current emotion: {last_emotion}"})

        # 5. VIP context
        vip_info = kwargs.get("vip_info")
        if vip_info:
            messages.append({"role": "system", "content": vip_info})

        # 6. Guest context + memories
        if guest_context:
            messages.append({"role": "system", "content": guest_context})
        elif speaker_name and memories:
            mem_text = "\n".join(str(m) for m in memories)
            messages.append({"role": "system", "content": f"Guest: {speaker_name}\nMemories:\n{mem_text}"})

        # 7. Event greeting prompt
        if event:
            greetings = self.get_greeting_prompts()
            if event in greetings:
                messages.append({"role": "system", "content": greetings[event]})

        # 8. Guest type hints
        guest_type = kwargs.get("guest_type")
        if guest_type:
            hints = self.get_guest_type_hints()
            if guest_type in hints:
                messages.append({"role": "system", "content": hints[guest_type]})

        return messages
