from mcp_chatgpt.parsing import parse_thread_id, classify_page_state


def test_parse_thread_id_basic():
    assert parse_thread_id("https://chatgpt.com/c/abc-123") == "abc-123"


def test_parse_thread_id_with_trailing_and_query():
    assert parse_thread_id("https://chatgpt.com/c/abc-123/?model=gpt-4") == "abc-123"


def test_parse_thread_id_none_when_no_conversation():
    assert parse_thread_id("https://chatgpt.com/") is None


def test_classify_ok():
    assert classify_page_state("https://chatgpt.com/c/x", "normal page body") == "ok"


def test_classify_login_by_url():
    assert classify_page_state("https://auth.openai.com/auth/login", "") == "login"


def test_classify_challenge_by_body():
    assert classify_page_state("https://chatgpt.com/", "Just a moment...") == "challenge"
