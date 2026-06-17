"""Per-provider browser config — the ONLY place site DOM/markers differ.

Adding a provider = one Site entry. Everything else (session, rotation, batch,
cap handling) is provider-agnostic and reads from SITES[provider]. Verified live
against each provider's DOM (chatgpt: 2026-06-15)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Site:
    url: str
    composer: str
    send_button: str
    assistant_turn: str
    generated_image_markers: tuple
    login_url_fragment: str
    challenge_text_markers: tuple
    usage_limit_markers: tuple
    stop_button: str = ""
    refusal_markers: tuple = ()
    response_picker_markers: tuple = ()
    response_picker_buttons: tuple = ()


SITES = {
    "chatgpt": Site(
        url="https://chatgpt.com/",
        composer="#prompt-textarea",
        send_button="[data-testid='send-button']",
        stop_button="[data-testid='stop-button']",
        assistant_turn="[data-message-author-role='assistant']",
        generated_image_markers=("/backend-api/", "oaiusercontent.com"),
        login_url_fragment="/auth/login",
        challenge_text_markers=("Verify you are human", "Just a moment",
                                "Checking your browser"),
        usage_limit_markers=(
            "You've reached", "you've hit", "usage limit", "limit reached",
            "free plan limit", "limit resets", "plan limit for image",
            "too many requests", "try again later", "rate limit", "come back later",
        ),
        refusal_markers=("may violate our guardrails", "violate our content policy",
                         "can't help with that", "unable to generate"),
        response_picker_markers=("which response do you prefer", "prefer this response",
                                 "compare these responses"),
        response_picker_buttons=(
            "button:has-text('I prefer this response')",
            "button:has-text('prefer this response')",
            "button:has-text('Keep this response')",
            "[data-testid='paragen-prefer-button']",
        ),
    ),
}


def get_site(provider: str) -> Site:
    """Return the Site for a provider, or raise KeyError with the known list."""
    try:
        return SITES[provider]
    except KeyError:
        raise KeyError(f"unknown provider {provider!r}; known: {sorted(SITES)}")
