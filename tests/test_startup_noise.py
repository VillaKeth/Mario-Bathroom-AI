"""Startup noise — an expected race must not look like a crash.

The client usually starts before the server has finished loading (SoVITS subprocess,
model loads), so its first health checks and WebSocket connects are refused. That
is routine and already handled: it retries with backoff and degrades cleanly. But
it was REPORTED as catastrophe — ERROR-level stack text per attempt, plus
"Disconnected from server!" when it had never been connected at all.

At a party nobody can tell a working startup from a broken one by looking at that.
These tests pin the distinction: "nothing is listening yet" is a calm, expected
condition; a real failure still reports loudly.
"""
import logging
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "client")):
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture(scope="module")
def wsc():
    import client.ws_client as wsc
    return wsc


# --- classifying the error -------------------------------------------------

def test_windows_connection_refused_is_server_not_up_yet(wsc):
    """WinError 10061 — what this box actually produces while the server loads."""
    err = OSError(None, "No connection could be made because the target machine "
                        "actively refused it", None, 10061)
    assert wsc.is_server_unreachable(err) is True


def test_posix_connection_refused_is_server_not_up_yet(wsc):
    assert wsc.is_server_unreachable(ConnectionRefusedError(111, "Connection refused")) is True


def test_real_protocol_error_is_not_treated_as_server_down(wsc):
    """A genuine fault must stay loud — this guard must not swallow everything."""
    assert wsc.is_server_unreachable(ValueError("invalid frame payload")) is False


def test_unexpected_oserror_is_not_treated_as_server_down(wsc):
    assert wsc.is_server_unreachable(OSError(13, "Permission denied")) is False


# --- how it is reported ----------------------------------------------------

def test_server_not_up_yet_is_not_logged_as_error(wsc, caplog):
    """The routine startup race must not surface at ERROR level."""
    client = wsc.MarioWSClient.__new__(wsc.MarioWSClient)
    client._ever_connected = False
    err = OSError(None, "actively refused it", None, 10061)

    with caplog.at_level(logging.DEBUG, logger="ws_client"):
        client._on_error(None, err)

    assert not [r for r in caplog.records if r.levelno >= logging.ERROR], (
        "expected startup race logged below ERROR, got: "
        f"{[(r.levelname, r.message) for r in caplog.records]}")


def test_genuine_error_is_still_logged_as_error(wsc, caplog):
    client = wsc.MarioWSClient.__new__(wsc.MarioWSClient)
    client._ever_connected = True

    with caplog.at_level(logging.DEBUG, logger="ws_client"):
        client._on_error(None, ValueError("invalid frame payload"))

    assert [r for r in caplog.records if r.levelno >= logging.ERROR], (
        "a real protocol error must still be reported at ERROR")


# --- "disconnected" must mean it was once connected ------------------------

def test_never_connected_is_not_reported_as_a_disconnect(wsc):
    client = wsc.MarioWSClient.__new__(wsc.MarioWSClient)
    client._ever_connected = False
    assert client.was_ever_connected() is False


def test_connected_then_dropped_is_a_real_disconnect(wsc):
    client = wsc.MarioWSClient.__new__(wsc.MarioWSClient)
    client._ever_connected = True
    assert client.was_ever_connected() is True
