import pytest
from mcp_chatgpt.sites import SITES, Site, get_site

REQUIRED = ("url", "composer", "assistant_turn",
            "generated_image_markers", "login_url_fragment",
            "challenge_text_markers", "usage_limit_markers")

def test_chatgpt_site_present_and_complete():
    s = get_site("chatgpt")
    assert isinstance(s, Site)
    for field in REQUIRED:
        assert getattr(s, field), f"chatgpt site missing {field}"

def test_chatgpt_values_match_legacy_selectors():
    s = get_site("chatgpt")
    assert s.url == "https://chatgpt.com/"
    assert s.composer == "#prompt-textarea"
    assert s.send_button == "[data-testid='send-button']"
    assert s.assistant_turn == "[data-message-author-role='assistant']"
    assert "oaiusercontent.com" in s.generated_image_markers
    assert s.login_url_fragment == "/auth/login"

def test_unknown_provider_raises():
    with pytest.raises(KeyError):
        get_site("nope")

def test_image_markers_and_limit_markers_are_tuples():
    s = get_site("chatgpt")
    assert isinstance(s.generated_image_markers, tuple)
    assert isinstance(s.usage_limit_markers, tuple)


def test_grok_site_present_and_complete():
    s = get_site("grok")
    for f in ("url", "composer", "assistant_turn",
              "generated_image_markers", "login_url_fragment", "usage_limit_markers"):
        assert getattr(s, f), f"grok site missing {f}"
    assert s.url.startswith("https://grok.com")


def test_gemini_site_present_and_complete():
    s = get_site("gemini")
    for f in ("url", "composer", "assistant_turn",
              "generated_image_markers", "login_url_fragment", "usage_limit_markers"):
        assert getattr(s, f), f"gemini site missing {f}"
    assert "gemini.google.com" in s.url
