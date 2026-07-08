import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
import gen_guard


def test_default_is_not_generating():
    gen_guard.set_user_generating(False)
    assert gen_guard.is_user_generating() is False


def test_flag_round_trips():
    gen_guard.set_user_generating(True)
    assert gen_guard.is_user_generating() is True
    gen_guard.set_user_generating(False)
    assert gen_guard.is_user_generating() is False


def test_worker_thread_sees_flag_set_on_main_thread():
    # The idle joke path runs on a worker thread (asyncio.run), while the user
    # request handler sets the flag on the main loop thread. A worker MUST see
    # the flag the handler set — otherwise an idle joke fires and starves the
    # in-flight user response. This is the whole reason the guard is a
    # thread-safe flag and not an asyncio primitive.
    gen_guard.set_user_generating(True)
    seen = {}

    def worker():
        seen["v"] = gen_guard.is_user_generating()

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    gen_guard.set_user_generating(False)
    assert seen["v"] is True
