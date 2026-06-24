from server.group_state import GroupSession


def test_transcript_appends_and_formats():
    s = GroupSession(member_ids=["pomni", "jax"], maxlen=10)
    s.add_line("Pomni", "Welcome to the circus!")
    s.add_line("Guest", "who are you?")
    assert s.transcript_text() == "Pomni: Welcome to the circus!\nGuest: who are you?"


def test_transcript_is_bounded():
    s = GroupSession(member_ids=["a"], maxlen=2)
    for i in range(5):
        s.add_line("A", f"line{i}")
    assert s.transcript_text() == "A: line3\nA: line4"


def test_least_recent_speaker_for_fallback():
    s = GroupSession(member_ids=["pomni", "jax"], maxlen=10)
    s.add_line("Pomni", "hi")
    # jax has not spoken -> least recent
    assert s.least_recent_speaker() == "jax"
    s.add_line("Jax", "sup")
    # now pomni spoke longest ago
    assert s.least_recent_speaker() == "pomni"
