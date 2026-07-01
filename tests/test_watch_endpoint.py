import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
import mario_prompt


def test_build_watch_context_includes_description():
    ctx = mario_prompt.build_watch_context("Fortnite, 12 HP, being chased", guest="Jacob")
    assert isinstance(ctx, list) and ctx
    joined = " ".join(m["content"] for m in ctx)
    assert "Fortnite, 12 HP, being chased" in joined
    assert "Jacob" in joined
    assert ctx[-1]["role"] == "user"
