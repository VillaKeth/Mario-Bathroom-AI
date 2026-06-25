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
