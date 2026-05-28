"""Party Report Card — end-of-party stats and shareable HTML report."""

import logging
import time
from collections import Counter

logger = logging.getLogger("party_report")

DEBUG_REPORT = True

_CHARACTER_NAME = "Mario"
_CHARACTER_DISPLAY_NAME = "Mario"


def set_character(name: str, display_name: str):
    global _CHARACTER_NAME, _CHARACTER_DISPLAY_NAME
    if name:
        _CHARACTER_NAME = name
    if display_name:
        _CHARACTER_DISPLAY_NAME = display_name


class PartyReport:
    """Compiles end-of-party statistics from all running modules."""

    def __init__(
        self,
        *,
        server_start_time: float = None,
        party_gossip=None,
        catchphrase_mirror=None,
        birthday_vip=None,
        tts_router=None,
        night_progression=None,
        llm_router=None,
        party_stats=None,
        state_current: dict = None,
        error_count: int = 0,
    ):
        self._start_time = server_start_time or time.time()
        self._gossip = party_gossip
        self._mirror = catchphrase_mirror
        self._vip = birthday_vip
        self._tts = tts_router
        self._progression = night_progression
        self._llm = llm_router
        self._party_stats = party_stats
        self._state = state_current or {}
        self._error_count = error_count

    # ------------------------------------------------------------------
    # Core report generation
    # ------------------------------------------------------------------

    def generate(self) -> dict:
        """Compile end-of-party stats from all available modules."""
        if DEBUG_REPORT:
            logger.debug("[DEBUG_REPORT] generate: START")

        now = time.time()
        duration_hours = round((now - self._start_time) / 3600, 2)

        report = {
            "party_duration_hours": duration_hours,
            "error_count": self._error_count,
            "total_guests": self._count_guests(),
            "total_interactions": self._count_interactions(),
            "total_audio_minutes": self._estimate_audio_minutes(),
            "avg_response_time": self._avg_response_time(),
            "most_popular_game": self._most_popular_game(),
            "funniest_moment": self._funniest_moment(),
            "top_gossip_topics": self._top_gossip_topics(),
            "top_catchphrases": self._top_catchphrases(),
            "phase_timeline": self._phase_timeline(duration_hours),
            "birthday_person_interactions": self._birthday_interactions(),
            "tts_stats": self._tts_stats(),
            "llm_stats": self._llm_stats(),
        }

        if DEBUG_REPORT:
            logger.debug("[DEBUG_REPORT] generate: END duration=%.2fh guests=%d",
                         duration_hours, report["total_guests"])
        return report

    # ------------------------------------------------------------------
    # Stat helpers
    # ------------------------------------------------------------------

    def _count_guests(self) -> int:
        if self._gossip and hasattr(self._gossip, "_guest_names"):
            return len(self._gossip._guest_names)
        return 0

    def _count_interactions(self) -> int:
        history = self._state.get("conversation_history", [])
        return len([m for m in history if m.get("role") == "user"])

    def _estimate_audio_minutes(self) -> float:
        interactions = self._count_interactions()
        return round(interactions * 0.25, 1)

    def _avg_response_time(self) -> float:
        times = self._state.get("_response_times")
        if times and len(times) > 0:
            return round(sum(times) / len(times), 3)
        return 0.0

    def _most_popular_game(self) -> str:
        game_state = self._state.get("_game_state", {})
        if game_state and game_state.get("game_name"):
            return game_state["game_name"]
        return "None played"

    def _funniest_moment(self) -> str:
        if self._gossip and hasattr(self._gossip, "_gossip_log"):
            funny = [g for g in self._gossip._gossip_log if g.get("type") == "funny"]
            if funny:
                longest = max(funny, key=lambda g: len(g.get("text", "")))
                speaker = longest.get("speaker_name", "Someone")
                return f'{speaker}: "{longest.get("text", "")}"'
        return "No funny moments captured"

    def _top_gossip_topics(self) -> list:
        if self._gossip and hasattr(self._gossip, "_gossip_log"):
            keywords = [g.get("keyword", "") for g in self._gossip._gossip_log if g.get("keyword")]
            counter = Counter(keywords)
            return [{"topic": k, "count": v} for k, v in counter.most_common(5)]
        return []

    def _top_catchphrases(self) -> dict:
        if self._mirror and hasattr(self._mirror, "get_party_catchphrases"):
            try:
                raw = self._mirror.get_party_catchphrases()
                result = {}
                for name, phrases in raw.items():
                    result[name] = [{"phrase": p, "count": c} for p, c in phrases[:3]]
                return result
            except Exception:
                pass
        return {}

    def _phase_timeline(self, duration_hours: float) -> list:
        from night_progression import Phase
        boundaries = [
            (0.0, Phase.WARM_UP),
            (2.0, Phase.PARTY_MODE),
            (5.0, Phase.UNHINGED),
            (7.0, Phase.WIND_DOWN),
        ]
        timeline = []
        for boundary_hr, phase in boundaries:
            if boundary_hr <= duration_hours:
                timeline.append({
                    "phase": phase.name,
                    "started_at_hour": boundary_hr,
                })
        return timeline

    def _birthday_interactions(self) -> dict:
        if self._vip and self._vip.is_configured():
            return {
                "name": self._vip.name,
                "interaction_count": self._vip.interaction_count,
            }
        return {}

    def _tts_stats(self) -> dict:
        if self._tts and hasattr(self._tts, "get_engine_stats"):
            try:
                return self._tts.get_engine_stats()
            except Exception:
                pass
        return {}

    def _llm_stats(self) -> dict:
        if self._llm and hasattr(self._llm, "stats"):
            return dict(self._llm.stats)
        return {}

    # ------------------------------------------------------------------
    # HTML rendering
    # ------------------------------------------------------------------

    def to_html(self) -> str:
        """Render a shareable HTML report card."""
        data = self.generate()
        awards = self._build_awards(data)
        awards_html = "\n".join(
            f'<div class="award"><span class="award-icon">{a["icon"]}</span>'
            f'<div class="award-title">{a["title"]}</div>'
            f'<div class="award-detail">{a["detail"]}</div></div>'
            for a in awards
        )

        gossip_html = ""
        if data["top_gossip_topics"]:
            items = "".join(
                f'<li>{t["topic"]} ({t["count"]}x)</li>'
                for t in data["top_gossip_topics"]
            )
            gossip_html = f'<div class="section"><h2>🗣️ Hot Topics</h2><ul>{items}</ul></div>'

        catchphrase_html = ""
        if data["top_catchphrases"]:
            rows = ""
            for name, phrases in data["top_catchphrases"].items():
                plist = ", ".join(f'"{p["phrase"]}" ({p["count"]}x)' for p in phrases)
                rows += f"<tr><td>{name}</td><td>{plist}</td></tr>"
            catchphrase_html = (
                '<div class="section"><h2>🔁 Catchphrases</h2>'
                f'<table><tr><th>Guest</th><th>Phrases</th></tr>{rows}</table></div>'
            )

        timeline_html = ""
        if data["phase_timeline"]:
            phases = " → ".join(
                f'{p["phase"]} (hr {p["started_at_hour"]})'
                for p in data["phase_timeline"]
            )
            timeline_html = f'<div class="section"><h2>🌙 Night Timeline</h2><p>{phases}</p></div>'

        vip_html = ""
        if data["birthday_person_interactions"]:
            vip = data["birthday_person_interactions"]
            vip_html = (
                f'<div class="section vip"><h2>🎂 Birthday Star: {vip["name"]}</h2>'
                f'<p>{_CHARACTER_NAME} chatted with them <b>{vip["interaction_count"]}</b> times!</p></div>'
            )

        tts_html = ""
        if data["tts_stats"]:
            rows = ""
            for eng, st in data["tts_stats"].items():
                if isinstance(st, dict):
                    rate = st.get("success_rate", st.get("successes", "?"))
                    rows += f"<tr><td>{eng}</td><td>{rate}</td></tr>"
            if rows:
                tts_html = (
                    '<div class="section"><h2>🔊 TTS Engines</h2>'
                    f'<table><tr><th>Engine</th><th>Success Rate</th></tr>{rows}</table></div>'
                )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_CHARACTER_DISPLAY_NAME} — Party Report Card</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',Roboto,sans-serif;background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);color:#eee;min-height:100vh;padding:20px}}
.container{{max-width:700px;margin:0 auto}}
h1{{text-align:center;font-size:2em;margin-bottom:4px;background:linear-gradient(90deg,#e94560,#ffd700);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.subtitle{{text-align:center;color:#888;font-size:.9em;margin-bottom:24px}}
.stats-bar{{display:flex;flex-wrap:wrap;justify-content:center;gap:16px;margin-bottom:24px}}
.stat{{background:#16213e;border:1px solid #0f3460;border-radius:12px;padding:12px 20px;text-align:center;min-width:120px}}
.stat .num{{font-size:1.8em;font-weight:bold;color:#ffd700}}
.stat .lbl{{font-size:.7em;color:#888;text-transform:uppercase;letter-spacing:1px}}
.awards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:24px}}
.award{{background:linear-gradient(135deg,#16213e,#1a1a3e);border:1px solid #e94560;border-radius:14px;padding:16px;text-align:center}}
.award-icon{{font-size:2.2em;display:block;margin-bottom:6px}}
.award-title{{font-size:.85em;color:#e94560;font-weight:bold;text-transform:uppercase;letter-spacing:.5px}}
.award-detail{{font-size:.9em;color:#ddd;margin-top:4px}}
.section{{background:#16213e;border:1px solid #0f3460;border-radius:12px;padding:16px;margin-bottom:16px}}
.section h2{{font-size:1.1em;color:#e94560;margin-bottom:10px}}
.section ul{{list-style:none;padding:0}}
.section li{{padding:4px 0;border-bottom:1px solid #0f3460}}
.section li:last-child{{border:none}}
.section table{{width:100%;border-collapse:collapse}}
.section th,.section td{{text-align:left;padding:6px 10px;border-bottom:1px solid #0f3460}}
.section th{{color:#ffd700;font-size:.8em;text-transform:uppercase}}
.vip{{border-color:#ffd700;background:linear-gradient(135deg,#2a1a00,#16213e)}}
.footer{{text-align:center;color:#555;font-size:.75em;margin-top:30px}}
</style>
</head>
<body>
<div class="container">
<h1>🍄 {_CHARACTER_DISPLAY_NAME} Party Report 🍄</h1>
<p class="subtitle">Party Duration: {data["party_duration_hours"]} hours</p>

<div class="stats-bar">
<div class="stat"><div class="num">{data["total_guests"]}</div><div class="lbl">Guests</div></div>
<div class="stat"><div class="num">{data["total_interactions"]}</div><div class="lbl">Interactions</div></div>
<div class="stat"><div class="num">{data["total_audio_minutes"]}</div><div class="lbl">Audio Min</div></div>
<div class="stat"><div class="num">{data["avg_response_time"]}s</div><div class="lbl">Avg Response</div></div>
<div class="stat"><div class="num">{data["error_count"]}</div><div class="lbl">Errors</div></div>
</div>

<div class="awards">
{awards_html}
</div>

{gossip_html}
{catchphrase_html}
{timeline_html}
{vip_html}
{tts_html}

<div class="footer">Generated by {_CHARACTER_DISPLAY_NAME} Party Bot 🎮</div>
</div>
</body>
</html>"""

    def _build_awards(self, data: dict) -> list:
        awards = [
            {
                "icon": "🏆",
                "title": "Party Duration",
                "detail": f"{data['party_duration_hours']} hours of fun!",
            },
            {
                "icon": "👥",
                "title": "Total Guests",
                "detail": f"{data['total_guests']} guests joined the party",
            },
            {
                "icon": "💬",
                "title": "Total Interactions",
                "detail": f"{data['total_interactions']} conversations",
            },
            {
                "icon": "🎮",
                "title": "Most Popular Game",
                "detail": data["most_popular_game"],
            },
            {
                "icon": "😂",
                "title": "Funniest Moment",
                "detail": data["funniest_moment"][:80],
            },
        ]

        if data.get("top_gossip_topics"):
            top = data["top_gossip_topics"][0]
            awards.append({
                "icon": "🗣️",
                "title": "Hottest Topic",
                "detail": f'"{top["topic"]}" mentioned {top["count"]}x',
            })

        if data.get("birthday_person_interactions"):
            vip = data["birthday_person_interactions"]
            awards.append({
                "icon": "🎂",
                "title": "Birthday Star",
                "detail": f'{vip["name"]} — {vip["interaction_count"]} interactions',
            })

        llm = data.get("llm_stats", {})
        if llm:
            total_llm = llm.get("fast", 0) + llm.get("quality", 0) + llm.get("fallback", 0)
            if total_llm > 0:
                awards.append({
                    "icon": "🧠",
                    "title": "Brain Power",
                    "detail": f"{total_llm} LLM calls ({llm.get('quality', 0)} quality)",
                })

        return awards
