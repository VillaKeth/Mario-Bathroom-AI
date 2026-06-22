"""Group session state: roster + bounded shared transcript. Pure."""
from collections import deque


class GroupSession:
    def __init__(self, member_ids, maxlen=40):
        self.member_ids = list(member_ids)
        self._lines = deque(maxlen=maxlen)   # (speaker_name, text)
        self._spoke_order = []               # member_id, most-recent last

    def add_line(self, speaker_name, text):
        self._lines.append((speaker_name, text))
        mid = speaker_name.lower()
        if mid in [m.lower() for m in self.member_ids]:
            self._spoke_order = [m for m in self._spoke_order if m != mid] + [mid]

    def transcript_text(self):
        return "\n".join(f"{name}: {text}" for name, text in self._lines)

    def least_recent_speaker(self):
        """Member who spoke longest ago (or never) — used as a director fallback."""
        never = [m for m in self.member_ids if m.lower() not in self._spoke_order]
        if never:
            return never[0]
        return self._spoke_order[0]
