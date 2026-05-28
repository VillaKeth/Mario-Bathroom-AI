"""Config.json manager — reads/writes model selections without overwriting other fields."""
import json
import os
import logging

logger = logging.getLogger(__name__)

def read_model_config(config_path: str) -> dict:
    if not os.path.exists(config_path):
        return {"quality_model": "", "fast_model": "", "character": ""}
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    server = cfg.get("server", {})
    return {
        "quality_model": server.get("llm_quality_model", ""),
        "fast_model": server.get("llm_fast_model", ""),
        "character": cfg.get("character", ""),
    }

def write_model_config(config_path: str, quality_model: str | None = None,
                        fast_model: str | None = None, character: str | None = None) -> None:
    if not os.path.exists(config_path):
        cfg = {"server": {}, "client": {}}
    else:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    if quality_model is not None:
        cfg.setdefault("server", {})["llm_quality_model"] = quality_model
    if fast_model is not None:
        cfg.setdefault("server", {})["llm_fast_model"] = fast_model
    if character is not None:
        cfg["character"] = character
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)
    logger.info(f"Updated config.json: quality={quality_model}, fast={fast_model}, character={character}")
