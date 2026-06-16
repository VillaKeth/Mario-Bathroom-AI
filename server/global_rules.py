"""Global rules + pronunciation applied to EVERY character, layered on top of
each character's own config. Loaded once at startup from
characters/_shared/global_rules.yaml. Absent/empty file = no-op (fully
backward-compatible). Intended to be edited as config — no code change needed
to add a rule or a global pronunciation.
"""
import os


def load_global_rules(shared_dir: str) -> dict:
    """Read characters/_shared/global_rules.yaml. Always returns a dict with
    'prompt_rules' (list[str]) and 'pronunciation' (dict[str,str])."""
    out = {"prompt_rules": [], "pronunciation": {}}
    path = os.path.join(shared_dir or "", "global_rules.yaml")
    if not os.path.exists(path):
        return out
    try:
        import yaml
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except Exception:
        return out
    if isinstance(data, dict):
        rules = data.get("prompt_rules") or []
        if isinstance(rules, list):
            out["prompt_rules"] = [str(r).strip() for r in rules if str(r).strip()]
        pron = data.get("pronunciation") or {}
        if isinstance(pron, dict):
            out["pronunciation"] = {str(k): str(v) for k, v in pron.items()
                                    if str(k).strip() and str(v).strip()}
    return out


def merge_pronunciation(global_pron: dict, char_pron: dict) -> dict:
    """Global pronunciation is the base; a character's own rule wins on conflict."""
    return {**(global_pron or {}), **(char_pron or {})}
