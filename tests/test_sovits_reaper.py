"""The stale-SoVITS reaper must not kill a DIFFERENT server's subprocess.

`_kill_stale_sovits_processes` scanned every process on the machine and killed
anything whose command line mentioned gpt_sovits_server.py, excluding only its own
PID. That reaps orphans from a crashed run — its actual purpose — but it also kills
the subprocess belonging to a live server running alongside it.

Observed 2026-09-11: a pytest run (which boots TTS on import of a standalone
script) reaped the running party server's SoVITS mid-conversation. The server
logged `subprocess exited (code=15)`, hit its 30s restart cooldown, and dropped to
Edge — so the character's voice changed mid-reply.

Ownership rule: kill our own children, and kill true orphans (parent gone). Never
kill a subprocess whose parent is alive and isn't us.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

SOVITS_CMD = ["python.exe", "-s", "server/gpt_sovits_server.py"]
OTHER_CMD = ["python.exe", "-m", "pytest"]


@pytest.fixture(scope="module")
def tts():
    import tts
    return tts


def test_never_reaps_our_own_process(tts):
    assert tts._should_reap_sovits(
        pid=100, cmdline=SOVITS_CMD, ppid=1, my_pid=100,
        my_child_pids=set(), parent_alive=True) is False


def test_ignores_processes_that_are_not_sovits(tts):
    assert tts._should_reap_sovits(
        pid=200, cmdline=OTHER_CMD, ppid=1, my_pid=100,
        my_child_pids=set(), parent_alive=True) is False


def test_reaps_our_own_leftover_child(tts):
    """A subprocess we spawned earlier in this process is ours to clean up."""
    assert tts._should_reap_sovits(
        pid=200, cmdline=SOVITS_CMD, ppid=100, my_pid=100,
        my_child_pids={200}, parent_alive=True) is True


def test_reaps_a_true_orphan(tts):
    """Parent died (crashed server) — nobody owns this, reap it."""
    assert tts._should_reap_sovits(
        pid=200, cmdline=SOVITS_CMD, ppid=999, my_pid=100,
        my_child_pids=set(), parent_alive=False) is True


def test_spares_another_live_servers_subprocess(tts):
    """THE BUG: a second server is running and this subprocess belongs to it."""
    assert tts._should_reap_sovits(
        pid=200, cmdline=SOVITS_CMD, ppid=555, my_pid=100,
        my_child_pids=set(), parent_alive=True) is False


def test_cmdline_none_is_not_reaped(tts):
    """psutil hands back None for processes it cannot inspect."""
    assert tts._should_reap_sovits(
        pid=200, cmdline=None, ppid=1, my_pid=100,
        my_child_pids=set(), parent_alive=False) is False
