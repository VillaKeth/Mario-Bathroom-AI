"""Executes a group turn: director picks speakers; each generates with its model
+ persona + the shared transcript, is filtered, and recorded. Pure — TTS/send live
in main.py. Members expose: id, display_name, model, voice_config, build_prompt()."""
import logging

logger = logging.getLogger(__name__)


class GroupOrchestrator:
    def __init__(self, members, session, generate_fn, filter_fn, director_fn):
        self._members = members            # {id: member}
        self._session = session            # GroupSession
        self._generate_fn = generate_fn    # (messages, model) -> {"text","emotion"}
        self._filter_fn = filter_fn        # (text) -> text
        self._director_fn = director_fn    # (guest_text, transcript, roster) -> TurnPlan

    def handle(self, guest_text):
        roster = {mid: m.display_name for mid, m in self._members.items()}
        self._session.add_line("Guest", guest_text)
        transcript = self._session.transcript_text()
        plan = self._director_fn(guest_text, transcript, roster)

        spoken = []
        for mid in plan.speakers:
            member = self._members.get(mid)
            if member is None:
                continue
            try:
                messages = [
                    {"role": "system", "content": member.build_prompt()},
                    {"role": "system", "content":
                        "You are in a group chat with the others. Stay in character; "
                        "react to what was just said. One short reply.\n\n" + self._session.transcript_text()},
                    {"role": "user", "content": guest_text},
                ]
                result = self._generate_fn(messages, member.model)
                text = self._filter_fn((result or {}).get("text", "") or "")
                if not text.strip():
                    continue
                self._session.add_line(member.display_name, text)
                spoken.append({
                    "id": mid, "display_name": member.display_name, "text": text,
                    "model": member.model, "voice_config": member.voice_config,
                    "emotion": (result or {}).get("emotion", "happy"),
                })
            except Exception as e:
                logger.warning(f"[group] speaker {mid} failed, skipping: {e}")
                continue
        return spoken
