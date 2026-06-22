from server.group_director import plan_turn, TurnPlan


ROSTER = {"pomni": "Pomni", "jax": "Jax"}  # id -> display name


def test_addressed_name_fast_path_no_llm():
    called = []
    def llm(_msgs, _model):
        called.append(1)
        return {"text": '{"speakers":["pomni"]}'}
    plan = plan_turn("Hey Jax, what's up?", "", ROSTER, "m", llm)
    assert plan.speakers == ["jax"]
    assert plan.addressed == "jax"
    assert called == []   # fast path skipped the LLM


def test_llm_pick_when_unaddressed():
    def llm(_msgs, _model):
        return {"text": 'sure -> {"speakers":["pomni"],"banter":false}'}
    plan = plan_turn("is this a dream?", "", ROSTER, "m", llm)
    assert plan.speakers == ["pomni"]


def test_garbage_llm_falls_back_to_least_recent():
    def llm(_msgs, _model):
        return {"text": "i have no idea what json is"}
    plan = plan_turn("hello?", "", ROSTER, "m", llm, least_recent="jax")
    assert plan.speakers == ["jax"]


def test_speakers_capped_at_two():
    def llm(_msgs, _model):
        return {"text": '{"speakers":["pomni","jax","pomni"]}'}
    plan = plan_turn("everyone talk", "", ROSTER, "m", llm)
    assert len(plan.speakers) == 2


def test_llm_names_outside_roster_are_dropped():
    def llm(_msgs, _model):
        return {"text": '{"speakers":["caine","pomni"]}'}
    plan = plan_turn("hi", "", ROSTER, "m", llm, least_recent="jax")
    assert plan.speakers == ["pomni"]
