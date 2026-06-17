import os
from mcp_chatgpt.browser import profile_dir, PROFILE_DIR


def test_profile_dir_chatgpt_uses_legacy_paths():
    # chatgpt keeps the legacy locations so existing logins survive
    assert profile_dir("chatgpt", "default") == PROFILE_DIR
    assert profile_dir("chatgpt", "work") == os.path.join(PROFILE_DIR, "_accounts", "work")


def test_profile_dir_other_providers_namespaced():
    assert profile_dir("grok", "default") == os.path.join(PROFILE_DIR, "grok")
    assert profile_dir("grok", "work") == os.path.join(PROFILE_DIR, "grok", "_accounts", "work")


def test_profile_dir_defaults_to_chatgpt():
    # called with no args / just defaults still resolves to the legacy chatgpt path
    assert profile_dir() == PROFILE_DIR
