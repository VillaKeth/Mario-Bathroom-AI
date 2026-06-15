"""All ChatGPT DOM selectors live here — single repair point when OpenAI reships UI.

Verified against live DOM on: <DATE — fill in during Task 8>
"""

URL = "https://chatgpt.com/"

# Composer + send/stop controls
COMPOSER = "#prompt-textarea"
SEND_BUTTON = "[data-testid='send-button']"
STOP_BUTTON = "[data-testid='stop-button']"

# Assistant output
ASSISTANT_TURN = "[data-message-author-role='assistant']"
ASSISTANT_IMAGE = "img"  # queried *within* the last assistant turn

# State detection
# Login: when logged out, ChatGPT redirects to a URL containing this path.
LOGIN_URL_FRAGMENT = "/auth/login"
# Cloudflare / challenge interstitials commonly show this in body text.
CHALLENGE_TEXT_MARKERS = ("Verify you are human", "Just a moment", "Checking your browser")
# Usage-limit banner text marker.
USAGE_LIMIT_MARKERS = ("You've reached", "usage limit", "limit reached")
