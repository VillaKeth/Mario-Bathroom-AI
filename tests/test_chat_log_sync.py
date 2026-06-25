"""Structural tests for bidirectional chat-log sync (server/main.py).

server/main.py is not importable in the unit env (see test_edge_cases.py:1347),
so these parse its AST/source to assert the design invariants. Behavior is
verified live (see the plan's Task 4).
"""
import ast
import os

_MAIN = os.path.join(os.path.dirname(__file__), "..", "server", "main.py")


def _main_src():
    with open(_MAIN, encoding="utf-8") as f:
        return f.read()


def _main_ast(src=None):
    return ast.parse(src if src is not None else _main_src())


def _func(tree, name):
    """Return the (Async)FunctionDef node named `name`, or None."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _calls(node, fname):
    """True if `node`'s body contains a call to a function/method named `fname`."""
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name) and f.id == fname:
                return True
            if isinstance(f, ast.Attribute) and f.attr == fname:
                return True
    return False


def _src_of(src, node):
    return ast.get_source_segment(src, node) or ""


# ── Task 1: helpers exist ────────────────────────────────────────────────

def test_log_guest_turn_helper_defined():
    tree = _main_ast()
    node = _func(tree, "_log_guest_turn")
    assert node is not None, "_log_guest_turn must be defined in server/main.py"
    assert isinstance(node, ast.AsyncFunctionDef), "_log_guest_turn must be async"


def test_resolve_guest_name_helper_defined():
    assert _func(_main_ast(), "_resolve_guest_name") is not None, \
        "_resolve_guest_name must be defined in server/main.py"


def test_log_guest_turn_echoes_and_transcribes():
    src = _main_src()
    node = _func(_main_ast(src), "_log_guest_turn")
    body = _src_of(src, node)
    assert "user_message" in body, "_log_guest_turn must echo a user_message"
    assert "add_transcript" in body, "_log_guest_turn must add to the mirror transcript"


# ── Task 2: guest logged at entry; pipeline echo + tunnel add removed ─────

def test_dispatch_user_text_logs_guest():
    node = _func(_main_ast(), "_dispatch_user_text")
    assert _calls(node, "_log_guest_turn"), "_dispatch_user_text must log the guest turn"


def test_dispatch_user_text_takes_guest_name():
    node = _func(_main_ast(), "_dispatch_user_text")
    args = [a.arg for a in node.args.args]
    assert "guest_name" in args, "_dispatch_user_text must accept guest_name"


def test_handle_event_logs_typed_guest():
    node = _func(_main_ast(), "handle_event")
    assert _calls(node, "_log_guest_turn"), "the text_input handler must log the guest turn"


def test_process_audio_logs_voice_guest():
    # The voice transcript -> response happens in _process_audio (handle_audio
    # only buffers/dispatches audio chunks).
    node = _func(_main_ast(), "_process_audio")
    assert _calls(node, "_log_guest_turn"), "_process_audio must log the spoken guest turn"


def test_pipeline_no_longer_echoes_user_message():
    src = _main_src()
    body = _src_of(src, _func(_main_ast(src), "_generate_and_send_response"))
    assert "user_message" not in body, \
        "_generate_and_send_response must not echo user_message (now done at entry)"


def test_friend_say_no_longer_adds_transcript():
    node = _func(_main_ast(), "friend_say")
    assert not _calls(node, "add_transcript"), \
        "/friend/say must not call add_transcript directly (now via _dispatch_user_text)"
    assert _calls(node, "_dispatch_user_text"), "/friend/say must still dispatch the text"
