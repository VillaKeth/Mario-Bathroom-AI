from mcp_chatgpt.parsing import parse_thread_id, classify_page_state, parse_reset_seconds


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


def test_reset_seconds_minutes():
    assert parse_reset_seconds("You've hit the limit. Try again in 12 minutes.") == 720


def test_reset_seconds_seconds():
    assert parse_reset_seconds("Please try again in 30 seconds") == 30


def test_reset_seconds_hours():
    assert parse_reset_seconds("Image limit reached. Come back in 2 hours.") == 7200


def test_reset_seconds_countdown_mmss():
    assert parse_reset_seconds("Try again in 04:59") == 299


def test_reset_seconds_countdown_hms():
    assert parse_reset_seconds("available in 1:02:03") == 3723


def test_reset_seconds_compound_hours_and_minutes():
    assert parse_reset_seconds("the limit resets in 5 hours and 51 minutes") == 5 * 3600 + 51 * 60


def test_reset_seconds_real_free_plan_message():
    msg = ("You've hit the free plan limit for image generations requests. "
           "You can create more images when the limit resets in 5 hours and 51 minutes.")
    assert parse_reset_seconds(msg) == 21060


def test_reset_seconds_none_when_absent():
    assert parse_reset_seconds("You've reached your limit, come back later") is None
