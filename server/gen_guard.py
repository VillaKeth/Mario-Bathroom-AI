"""User-priority generation guard.

Idle / background LLM calls must yield while a user request is being answered,
so they don't compete for the (CPU-bound) model and starve the real response.
On a slow box two concurrent generations crawl; the guest's story loses.

Thread-safe by design: the idle joke path runs on a worker thread (via
asyncio.run) while the request handler runs on the main event-loop thread, so
the shared state is a plain flag behind a threading.Lock — never an asyncio
primitive (those are loop-bound and can't coordinate across the two contexts,
and must never be held across an await).

Usage:
    gen_guard.set_user_generating(True)   # request handler, before LLM call
    try:
        ...generate the user's response...
    finally:
        gen_guard.set_user_generating(False)

    if gen_guard.is_user_generating():    # idle/background LLM paths
        return None                       # yield — don't compete
"""
import threading

_lock = threading.Lock()
_user_generating = False


def set_user_generating(active: bool) -> None:
    """Mark whether a user request is currently generating an LLM response."""
    global _user_generating
    with _lock:
        _user_generating = bool(active)


def is_user_generating() -> bool:
    """True while a user request is mid-generation; idle LLM calls should skip."""
    with _lock:
        return _user_generating
