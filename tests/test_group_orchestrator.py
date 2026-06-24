from server.group_orchestrator import GroupOrchestrator
from server.group_state import GroupSession
from server.group_director import TurnPlan


class FakeMember:
    def __init__(self, mid, name, model, vc):
        self.id = mid
        self.display_name = name
        self.model = model
        self.voice_config = vc

    def build_prompt(self):
        return f"You are {self.display_name}."


def _orch(plan_speakers):
    members = {
        "pomni": FakeMember("pomni", "Pomni", "shared", {"v": "p"}),
        "jax": FakeMember("jax", "Jax", "jax-model", {"v": "j"}),
    }
    gen_calls = []

    def generate_fn(messages, model):
        gen_calls.append(model)
        who = messages[0]["content"]
        return {"text": f"line from {who}", "emotion": "happy"}

    def filter_fn(t):
        return t.upper()

    def director_fn(text, transcript, roster):
        return TurnPlan(speakers=plan_speakers)

    sess = GroupSession(member_ids=list(members), maxlen=20)
    orch = GroupOrchestrator(members, sess, generate_fn, filter_fn, director_fn)
    return orch, sess, gen_calls


def test_two_speaker_turn_uses_each_model_and_voice():
    orch, sess, gen_calls = _orch(["pomni", "jax"])
    lines = orch.handle("hello circus")
    assert [l["id"] for l in lines] == ["pomni", "jax"]
    assert gen_calls == ["shared", "jax-model"]           # resolved per member
    assert lines[1]["voice_config"] == {"v": "j"}
    assert lines[0]["text"] == "LINE FROM YOU ARE POMNI."  # filter applied
    assert "Guest: hello circus" in sess.transcript_text()
    assert "Pomni: LINE FROM YOU ARE POMNI." in sess.transcript_text()


def test_failing_speaker_is_skipped_not_fatal():
    orch, sess, _ = _orch(["pomni", "jax"])

    def boom(messages, model):
        if model == "jax-model":
            raise RuntimeError("ollama down")
        return {"text": "ok", "emotion": "happy"}

    orch._generate_fn = boom
    lines = orch.handle("hi")
    assert [l["id"] for l in lines] == ["pomni"]   # jax skipped, turn survived
