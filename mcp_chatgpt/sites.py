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
    file_input: str = ""        # hidden <input type=file> for image-to-image upload (chatgpt)
    refusal_markers: tuple = ()
    response_picker_markers: tuple = ()
    response_picker_buttons: tuple = ()
    # Assistant-text substrings that mean "still generating" (lowercased match).
    # For providers with no Stop button (gemini shows "Creating your image..."
    # while the image renders) this keeps the wait loop from finishing early.
    generating_text_markers: tuple = ()
    # Ordered onboarding buttons clicked (each if present) BEFORE the composer
    # exists — e.g. fresh gemini accounts show "Use Gemini" then a "No thanks"
    # data-sharing dialog. Clicked in order, only when the composer isn't there.
    intro_buttons: tuple = ()


SITES = {
    "chatgpt": Site(
        url="https://chatgpt.com/",
        composer="#prompt-textarea",
        send_button="[data-testid='send-button']",
        stop_button="[data-testid='stop-button']",
        file_input="input[type='file']",
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
    # SCAFFOLD — selectors are best-effort guesses; verify live against the
    # logged-in site and fix before trusting (composer, send, assistant turn,
    # the real generated-image src host, login/cap wording).
    "grok": Site(
        url="https://grok.com/",
        composer="[contenteditable='true']",
        send_button="",                       # no Send button; submit via Enter
        stop_button="button[aria-label*='Stop' i]",
        assistant_turn="[data-testid*='message'], .message-bubble",
        generated_image_markers=("assets.grok.com", "imggen", "grok-attachments"),
        login_url_fragment="/sign-in",
        challenge_text_markers=("Verify you are human", "Just a moment"),
        usage_limit_markers=("rate limit", "try again later", "out of",
                             "limit reached", "upgrade to"),
        refusal_markers=("can't help with that", "i can't create"),
    ),
    # SCAFFOLD — verify live (Gemini uses a Quill div.ql-editor composer +
    # <model-response> turns; confirm the real image host).
    "gemini": Site(
        url="https://gemini.google.com/app",
        composer="div.ql-editor",
        send_button="",                       # no Send button; submit via Enter
        stop_button="",                       # no reliable Stop selector; rely on stability
        assistant_turn="model-response",
        # Gemini renders a generated image as a blob: URL (avatars are lh3.*, so
        # markers must NOT match those). Verified live 2026-06-17.
        generated_image_markers=("blob:",),
        login_url_fragment="accounts.google.com",
        challenge_text_markers=("Verify it's you", "unusual traffic"),
        usage_limit_markers=("you've reached your limit", "try again later",
                             "limit for", "upgrade", "can't create more images",
                             "can't generate more images", "more images for you today",
                             "come back tomorrow"),
        refusal_markers=("i can't create", "i'm not able to generate",
                         "can't help with that"),
        generating_text_markers=("creating your image", "creating image",
                                 "generating", "working on", "let me create"),
        # Fresh-account onboarding: "Use Gemini" landing CTA, then a "No thanks"
        # data-sharing dialog — click both (decline data) so the composer loads.
        intro_buttons=(
            "button:has-text('Use Gemini')",
            "button:has-text('Chat with Gemini')",
            "a:has-text('Use Gemini')",
            "button:has-text('No thanks')",
            "button:has-text('No, thanks')",
            "button:has-text('Don')",
            "button:has-text('Dismiss')",       # "Gemini is more relevant with location" nag
        ),
    ),
}


def get_site(provider: str) -> Site:
    """Return the Site for a provider, or raise KeyError with the known list."""
    try:
        return SITES[provider]
    except KeyError:
        raise KeyError(f"unknown provider {provider!r}; known: {sorted(SITES)}")
