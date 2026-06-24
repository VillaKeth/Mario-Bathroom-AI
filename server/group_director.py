"""Hybrid turn director: address fast-path + injected-LLM pick + rule fallback.

Pure: the LLM is passed in as `llm_fn(messages, model) -> {"text": str}` so this
unit-tests without Ollama.
"""
import json
import re


class TurnPlan:
    def __init__(self, speakers, addressed=None, banter=False):
        self.speakers = speakers
        self.addressed = addressed
        self.banter = banter


def _extract_json(text):
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def plan_turn(guest_text, transcript, roster, director_model, llm_fn, least_recent=None):
    """roster: {member_id: display_name}. Returns a TurnPlan (speakers are ids)."""
    ids = list(roster.keys())
    low = (guest_text or "").lower()

    # 1) Address fast-path: an explicitly named member answers, no LLM.
    for mid, name in roster.items():
        if re.search(rf"\b{re.escape(name.lower())}\b", low) or re.search(rf"\b{re.escape(mid)}\b", low):
            return TurnPlan(speakers=[mid], addressed=mid)

    # 2) Fast-model pick.
    sys = ("You are the ringmaster director of a group chat. Members: "
           + ", ".join(f"{n} (id={i})" for i, n in roster.items())
           + ". Given the guest message and recent transcript, choose 1 (or 2 for "
           'banter) member IDs to respond. Reply ONLY JSON: {"speakers":["id"],"banter":false}.')
    user = f"Transcript:\n{transcript}\n\nGuest: {guest_text}"
    raw = llm_fn([{"role": "system", "content": sys}, {"role": "user", "content": user}], director_model)
    data = _extract_json(raw.get("text", "")) if isinstance(raw, dict) else None

    speakers = []
    if data and isinstance(data.get("speakers"), list):
        seen = set()
        for s in data["speakers"]:
            s = str(s).lower()
            if s in ids and s not in seen:
                seen.add(s)
                speakers.append(s)
    banter = bool(data.get("banter")) if data else False

    # 3) Fallback: least-recent speaker (or first member).
    if not speakers:
        speakers = [least_recent or ids[0]]

    return TurnPlan(speakers=speakers[:2], addressed=None, banter=banter)
