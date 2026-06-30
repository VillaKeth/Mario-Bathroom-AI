import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
import main as srv

def test_single_message_unchanged():
    assert srv._batch_join(["how do I win?"]) == "how do I win?"

def test_multiple_messages_folded():
    out = srv._batch_join(["wait", "actually", "how do I beat the boss?"])
    assert "how do I beat the boss?" in out
    assert "wait" in out and "actually" in out
    # folded into a single string, not a list
    assert isinstance(out, str)

def test_empty_list_returns_empty():
    assert srv._batch_join([]) == ""

def test_blank_messages_filtered():
    assert srv._batch_join(["", "  ", "hello"]) == "hello"

def test_all_blank_returns_empty():
    assert srv._batch_join(["", "  "]) == ""
