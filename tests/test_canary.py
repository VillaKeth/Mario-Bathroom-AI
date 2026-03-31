"""Tests for Canary pre-party self-test."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from canary import Canary


def test_canary_returns_results():
    canary = Canary(server_url="http://localhost:8765")
    result = canary._format_result("voice_test", True, "Generated in 0.5s")
    assert result["test"] == "voice_test"
    assert result["passed"] == True
    assert result["message"] == "Generated in 0.5s"


def test_confidence_calculation():
    canary = Canary(server_url="http://localhost:8765")
    results = [
        {"passed": True},
        {"passed": True},
        {"passed": True},
        {"passed": False},
        {"passed": True},
    ]
    assert canary._calculate_confidence(results) == 80


def test_confidence_all_pass():
    canary = Canary(server_url="http://localhost:8765")
    results = [{"passed": True}, {"passed": True}, {"passed": True}]
    assert canary._calculate_confidence(results) == 100


def test_confidence_empty():
    canary = Canary(server_url="http://localhost:8765")
    assert canary._calculate_confidence([]) == 0
