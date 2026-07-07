import os
import yaml

def load_curated_jokes(char_dir: str, fallback=None):
    """Return the curated joke list from <char_dir>/jokes/curated.yaml, or fallback."""
    fallback = fallback or []
    path = os.path.join(char_dir, "jokes", "curated.yaml")
    if not os.path.isfile(path):
        return fallback
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        jokes = data.get("jokes") or []
        return jokes if jokes else fallback
    except Exception:
        return fallback
