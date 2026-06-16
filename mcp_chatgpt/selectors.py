"""All ChatGPT DOM selectors live here — single repair point when OpenAI reships UI.

Verified against live DOM on: 2026-06-15
"""

URL = "https://chatgpt.com/"

# Composer + send/stop controls
COMPOSER = "#prompt-textarea"
SEND_BUTTON = "[data-testid='send-button']"
STOP_BUTTON = "[data-testid='stop-button']"

# Assistant output
ASSISTANT_TURN = "[data-message-author-role='assistant']"

# Generated images render OUTSIDE the assistant-turn element, so they are found
# page-level and identified by their src host/path (avatars are gravatar.com and
# never match these). Verified against live DOM on 2026-06-15.
GENERATED_IMAGE_MARKERS = ("/backend-api/", "oaiusercontent.com")

# State detection
# Login: when logged out, ChatGPT redirects to a URL containing this path.
LOGIN_URL_FRAGMENT = "/auth/login"
# Cloudflare / challenge interstitials commonly show this in body text.
CHALLENGE_TEXT_MARKERS = ("Verify you are human", "Just a moment", "Checking your browser")
# Usage-limit / throttle text markers — generation waits for the reset on these.
# "free plan limit" / "limit resets" are the verified live wording for the image
# cap: "You've hit the free plan limit for image generations requests. You can
# create more images when the limit resets in 5 hours and 51 minutes."
USAGE_LIMIT_MARKERS = (
    "You've reached", "you've hit", "usage limit", "limit reached",
    "free plan limit", "limit resets", "plan limit for image",
    "too many requests", "try again later", "rate limit",
    "come back later",
)
