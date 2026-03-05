"""Generate fully fresh Mario sprite sets in assets_boutique_fresh.

This generator does not reuse prior sprite grids; every sprite is drawn
procedurally from shape primitives for each state.
"""

import os
from datetime import UTC, datetime
from typing import Any

from PIL import Image, ImageDraw

from generate_sprites import add_drop_shadow, add_outline

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
OUTPUT_DIR = os.path.join(ROOT_DIR, "assets_boutique_fresh")

SPRITE_STATES = [
    "idle",
    "talk",
    "talk2",
    "walk1",
    "walk2",
    "wave",
    "jump",
    "think",
    "laugh",
    "surprise",
    "sleep",
    "dance",
]

POSES: dict[str, dict[str, Any]] = {
    "idle": {"eye": "open", "mouth": "neutral", "arm": "down", "leg": "stand", "lift": 0, "lean": 0},
    "talk": {"eye": "open", "mouth": "talk", "arm": "down", "leg": "stand", "lift": 0, "lean": 0},
    "talk2": {"eye": "open", "mouth": "talk2", "arm": "down", "leg": "stand", "lift": 0, "lean": 0},
    "walk1": {"eye": "open", "mouth": "neutral", "arm": "walk1", "leg": "walk1", "lift": 0, "lean": -1},
    "walk2": {"eye": "open", "mouth": "neutral", "arm": "walk2", "leg": "walk2", "lift": 0, "lean": 1},
    "wave": {"eye": "open", "mouth": "neutral", "arm": "wave", "leg": "stand", "lift": 0, "lean": 0},
    "jump": {"eye": "open", "mouth": "neutral", "arm": "jump", "leg": "jump", "lift": 3, "lean": 0},
    "think": {"eye": "half", "mouth": "neutral", "arm": "think", "leg": "stand", "lift": 0, "lean": 0},
    "laugh": {"eye": "closed", "mouth": "laugh", "arm": "laugh", "leg": "stand", "lift": 0, "lean": 0},
    "surprise": {"eye": "wide", "mouth": "surprise", "arm": "surprise", "leg": "stand", "lift": 0, "lean": 0},
    "sleep": {"eye": "sleep", "mouth": "sleep", "arm": "sleep", "leg": "stand", "lift": 0, "lean": 0},
    "dance": {"eye": "open", "mouth": "laugh", "arm": "dance", "leg": "dance", "lift": 0, "lean": 1},
}

BASE_STYLE: dict[str, Any] = {
    "id": "base",
    "note": "Base style",
    "canvas_w": 28,
    "canvas_h": 38,
    "scale": 8,
    "head_w": 14,
    "head_h": 10,
    "hat_h": 3,
    "brim_h": 2,
    "body_w": 14,
    "body_h": 11,
    "arm_w": 3,
    "arm_h": 6,
    "leg_w": 4,
    "leg_h": 7,
    "boot_h": 2,
    "eye_w": 4,
    "eye_h": 2,
    "eye_gap": 2,
    "iris_w": 3,
    "pupil_w": 1,
    "mustache_w": 10,
    "mustache_h": 2,
    "nose_w": 2,
    "nose_h": 2,
    "colors": {
        "shirt": (228, 0, 0, 255),
        "shirt_shadow": (176, 0, 0, 255),
        "skin": (252, 180, 108, 255),
        "skin_shadow": (228, 148, 84, 255),
        "overall": (0, 88, 248, 255),
        "overall_shadow": (0, 56, 200, 255),
        "mustache": (160, 88, 0, 255),
        "hair": (128, 72, 0, 255),
        "boot": (132, 76, 0, 255),
        "boot_shadow": (88, 48, 0, 255),
        "glove": (240, 240, 240, 255),
        "eye_white": (255, 255, 255, 255),
        "eye_blue": (16, 116, 255, 255),
        "pupil": (0, 0, 0, 255),
        "button": (252, 216, 0, 255),
    },
}


def build_style(style_id: str, note: str, overrides: dict[str, Any]) -> dict[str, Any]:
    style = dict(BASE_STYLE)
    style["colors"] = dict(BASE_STYLE["colors"])
    for key, value in overrides.items():
        if key == "colors":
            for color_key, color_value in value.items():
                style["colors"][color_key] = color_value
        else:
            style[key] = value
    style["id"] = style_id
    style["note"] = note
    return style


STYLES = [
    build_style(
        "01_classic_fresh",
        "Classic balanced pass with large cobalt eyes and medium mustache.",
        {},
    ),
    build_style(
        "02_blocky_champion",
        "Chunkier proportions and wider hat with heavier mustache.",
        {
            "head_w": 15,
            "body_w": 15,
            "eye_w": 5,
            "iris_w": 4,
            "mustache_w": 11,
            "arm_w": 4,
            "colors": {
                "shirt": (236, 24, 8, 255),
                "overall": (20, 104, 255, 255),
                "overall_shadow": (0, 72, 220, 255),
                "mustache": (150, 78, 0, 255),
            },
        },
    ),
    build_style(
        "03_tall_showman",
        "Taller frame with slimmer body and high bright eyes.",
        {
            "canvas_h": 40,
            "head_h": 11,
            "body_h": 12,
            "leg_h": 8,
            "eye_w": 4,
            "eye_gap": 3,
            "mustache_w": 9,
            "colors": {
                "shirt": (220, 0, 0, 255),
                "shirt_shadow": (150, 0, 0, 255),
                "overall": (0, 98, 252, 255),
                "overall_shadow": (0, 62, 206, 255),
                "skin": (250, 176, 106, 255),
            },
        },
    ),
    build_style(
        "04_chibi_fireball",
        "Short chibi silhouette with giant eyes and compact overalls.",
        {
            "canvas_h": 34,
            "head_w": 15,
            "head_h": 11,
            "body_h": 9,
            "leg_h": 5,
            "eye_w": 5,
            "eye_h": 3,
            "iris_w": 4,
            "pupil_w": 2,
            "mustache_w": 9,
            "colors": {
                "shirt": (244, 44, 44, 255),
                "shirt_shadow": (192, 32, 32, 255),
                "overall": (42, 132, 255, 255),
                "overall_shadow": (20, 94, 224, 255),
                "skin": (255, 194, 128, 255),
                "skin_shadow": (234, 156, 92, 255),
            },
        },
    ),
    build_style(
        "05_stout_arcade",
        "Wider lower body with thick boots and arcade blues.",
        {
            "canvas_w": 30,
            "body_w": 16,
            "leg_w": 5,
            "boot_h": 3,
            "mustache_w": 12,
            "eye_w": 4,
            "iris_w": 3,
            "colors": {
                "shirt": (226, 12, 8, 255),
                "overall": (0, 90, 240, 255),
                "overall_shadow": (0, 58, 188, 255),
                "boot": (120, 64, 0, 255),
                "boot_shadow": (76, 40, 0, 255),
            },
        },
    ),
    build_style(
        "06_heroic_neo",
        "Heroic silhouette with pronounced hat brim and vivid irises.",
        {
            "head_w": 16,
            "hat_h": 4,
            "brim_h": 2,
            "eye_w": 5,
            "iris_w": 4,
            "mustache_h": 3,
            "colors": {
                "shirt": (210, 0, 0, 255),
                "shirt_shadow": (136, 0, 0, 255),
                "overall": (0, 104, 255, 255),
                "overall_shadow": (0, 70, 216, 255),
                "eye_blue": (20, 128, 255, 255),
            },
        },
    ),
    build_style(
        "07_comic_bold",
        "Comic-book contrast with darker shading and strong mustache lines.",
        {
            "scale": 9,
            "head_w": 14,
            "body_w": 15,
            "eye_w": 4,
            "iris_w": 3,
            "mustache_w": 11,
            "colors": {
                "shirt": (198, 0, 0, 255),
                "shirt_shadow": (122, 0, 0, 255),
                "skin": (242, 168, 98, 255),
                "skin_shadow": (200, 126, 72, 255),
                "overall": (10, 92, 228, 255),
                "overall_shadow": (0, 52, 170, 255),
                "eye_blue": (8, 112, 244, 255),
            },
        },
    ),
    build_style(
        "08_party_neon",
        "Party palette with neon red/blue accents and bright eyes.",
        {
            "eye_w": 5,
            "eye_h": 3,
            "iris_w": 4,
            "pupil_w": 2,
            "mustache_w": 10,
            "colors": {
                "shirt": (255, 56, 84, 255),
                "shirt_shadow": (208, 26, 54, 255),
                "overall": (0, 164, 255, 255),
                "overall_shadow": (0, 114, 220, 255),
                "eye_blue": (32, 176, 255, 255),
                "button": (255, 238, 82, 255),
            },
        },
    ),
    build_style(
        "09_retro_dark",
        "Retro darker tone with compact eyes and deep costume shading.",
        {
            "head_w": 13,
            "body_w": 13,
            "eye_w": 3,
            "iris_w": 2,
            "mustache_w": 9,
            "colors": {
                "shirt": (186, 0, 0, 255),
                "shirt_shadow": (118, 0, 0, 255),
                "overall": (0, 76, 206, 255),
                "overall_shadow": (0, 44, 152, 255),
                "skin": (230, 158, 92, 255),
                "skin_shadow": (186, 118, 68, 255),
                "boot": (98, 50, 0, 255),
                "boot_shadow": (62, 30, 0, 255),
            },
        },
    ),
    build_style(
        "10_royal_prime",
        "Final polished pass with broad hat, large irises, and clean costume lines.",
        {
            "scale": 9,
            "head_w": 16,
            "body_w": 15,
            "eye_w": 5,
            "eye_h": 3,
            "iris_w": 4,
            "pupil_w": 2,
            "mustache_w": 12,
            "mustache_h": 3,
            "colors": {
                "shirt": (234, 20, 8, 255),
                "shirt_shadow": (168, 8, 8, 255),
                "overall": (12, 112, 255, 255),
                "overall_shadow": (0, 70, 214, 255),
                "eye_blue": (24, 132, 255, 255),
                "skin": (252, 184, 114, 255),
                "skin_shadow": (224, 144, 84, 255),
            },
        },
    ),
]


def validate_style(style: dict[str, Any]) -> None:
    positive_fields = [
        "canvas_w",
        "canvas_h",
        "scale",
        "head_w",
        "head_h",
        "hat_h",
        "brim_h",
        "body_w",
        "body_h",
        "arm_w",
        "arm_h",
        "leg_w",
        "leg_h",
        "boot_h",
        "eye_w",
        "eye_h",
        "eye_gap",
        "iris_w",
        "pupil_w",
        "mustache_w",
        "mustache_h",
        "nose_w",
        "nose_h",
    ]
    for key in positive_fields:
        if style[key] <= 0:
            raise ValueError(f"{style['id']} invalid value for {key}: {style[key]}")

    if style["iris_w"] > style["eye_w"]:
        raise ValueError(f"{style['id']} iris_w must be <= eye_w")
    if style["pupil_w"] > style["iris_w"]:
        raise ValueError(f"{style['id']} pupil_w must be <= iris_w")


def rect(draw: ImageDraw.ImageDraw, x1: int, y1: int, x2: int, y2: int, color: tuple[int, int, int, int]) -> None:
    xa = min(x1, x2)
    xb = max(x1, x2)
    ya = min(y1, y2)
    yb = max(y1, y2)
    draw.rectangle([xa, ya, xb, yb], fill=color)


def draw_eyes(
    draw: ImageDraw.ImageDraw,
    style: dict[str, Any],
    cx: int,
    eye_y: int,
    eye_mode: str,
) -> None:
    colors = style["colors"]
    eye_w = style["eye_w"]
    eye_h = style["eye_h"]
    iris_w = style["iris_w"]
    pupil_w = style["pupil_w"]
    eye_gap = style["eye_gap"]

    if eye_mode == "wide":
        eye_h = eye_h + 1

    left_x = cx - (eye_gap // 2) - eye_w
    right_x = cx + (eye_gap // 2) + 1

    if eye_mode in ("open", "wide"):
        for eye_x in (left_x, right_x):
            rect(draw, eye_x, eye_y, eye_x + eye_w - 1, eye_y + eye_h - 1, colors["eye_white"])
            iris_x = eye_x + (eye_w - iris_w) // 2
            rect(draw, iris_x, eye_y, iris_x + iris_w - 1, eye_y + eye_h - 1, colors["eye_blue"])
            pupil_x = iris_x + (iris_w - pupil_w) // 2
            rect(draw, pupil_x, eye_y, pupil_x + pupil_w - 1, eye_y + eye_h - 1, colors["pupil"])
        return

    if eye_mode == "half":
        for eye_x in (left_x, right_x):
            rect(draw, eye_x, eye_y, eye_x + eye_w - 1, eye_y, colors["skin_shadow"])
            rect(draw, eye_x, eye_y + 1, eye_x + eye_w - 1, eye_y + eye_h - 1, colors["eye_blue"])
            pupil_x = eye_x + (eye_w - pupil_w) // 2
            rect(draw, pupil_x, eye_y + 1, pupil_x + pupil_w - 1, eye_y + eye_h - 1, colors["pupil"])
        return

    for eye_x in (left_x, right_x):
        rect(draw, eye_x, eye_y, eye_x + eye_w - 1, eye_y, colors["skin_shadow"])
        if eye_mode == "sleep":
            rect(draw, eye_x + 1, eye_y + 1, eye_x + eye_w - 2, eye_y + 1, colors["skin"])


def draw_mouth(
    draw: ImageDraw.ImageDraw,
    style: dict[str, Any],
    cx: int,
    y: int,
    mouth_mode: str,
) -> None:
    colors = style["colors"]
    if mouth_mode == "neutral":
        rect(draw, cx - 2, y, cx + 2, y, colors["skin_shadow"])
    elif mouth_mode == "talk":
        rect(draw, cx - 2, y, cx + 2, y + 1, colors["shirt_shadow"])
    elif mouth_mode == "talk2":
        rect(draw, cx - 3, y, cx + 3, y + 1, colors["shirt_shadow"])
    elif mouth_mode == "laugh":
        rect(draw, cx - 3, y, cx + 3, y + 1, colors["shirt_shadow"])
        rect(draw, cx - 2, y, cx + 2, y, colors["skin"])
    elif mouth_mode == "surprise":
        rect(draw, cx - 1, y, cx + 1, y + 1, colors["shirt_shadow"])
    else:
        rect(draw, cx - 1, y, cx + 1, y, colors["skin_shadow"])


def draw_legs(
    draw: ImageDraw.ImageDraw,
    style: dict[str, Any],
    body_left: int,
    body_right: int,
    leg_top: int,
    leg_bottom: int,
    boot_top: int,
    ground_y: int,
    leg_mode: str,
) -> None:
    colors = style["colors"]
    leg_w = style["leg_w"]
    left_leg_x = body_left + 1
    right_leg_x = body_right - leg_w

    if leg_mode == "stand":
        rect(draw, left_leg_x, leg_top, left_leg_x + leg_w - 1, leg_bottom, colors["overall"])
        rect(draw, right_leg_x, leg_top, right_leg_x + leg_w - 1, leg_bottom, colors["overall"])
    elif leg_mode == "walk1":
        rect(draw, left_leg_x, leg_top, left_leg_x + leg_w - 1, leg_bottom, colors["overall"])
        rect(draw, right_leg_x, leg_top + 2, right_leg_x + leg_w - 1, leg_bottom, colors["overall_shadow"])
    elif leg_mode == "walk2":
        rect(draw, left_leg_x, leg_top + 2, left_leg_x + leg_w - 1, leg_bottom, colors["overall_shadow"])
        rect(draw, right_leg_x, leg_top, right_leg_x + leg_w - 1, leg_bottom, colors["overall"])
    elif leg_mode == "jump":
        rect(draw, left_leg_x, leg_top + 1, left_leg_x + leg_w - 1, leg_bottom - 1, colors["overall"])
        rect(draw, right_leg_x, leg_top + 1, right_leg_x + leg_w - 1, leg_bottom - 1, colors["overall"])
    else:
        rect(draw, left_leg_x, leg_top, left_leg_x + leg_w - 1, leg_bottom, colors["overall"])
        rect(draw, right_leg_x + 1, leg_top + 1, right_leg_x + leg_w + 1, leg_bottom, colors["overall"])

    rect(draw, left_leg_x - 1, boot_top, left_leg_x + leg_w, ground_y, colors["boot"])
    rect(draw, right_leg_x - 1, boot_top, right_leg_x + leg_w, ground_y, colors["boot"])
    rect(draw, left_leg_x - 1, ground_y, left_leg_x + leg_w, ground_y, colors["boot_shadow"])
    rect(draw, right_leg_x - 1, ground_y, right_leg_x + leg_w, ground_y, colors["boot_shadow"])


def draw_arms(
    draw: ImageDraw.ImageDraw,
    style: dict[str, Any],
    body_left: int,
    body_right: int,
    shoulder_y: int,
    head_top: int,
    arm_mode: str,
) -> None:
    colors = style["colors"]
    arm_w = style["arm_w"]
    arm_h = style["arm_h"]

    left_x = body_left - arm_w
    right_x = body_right + 1
    down_y2 = shoulder_y + arm_h - 1

    if arm_mode == "down":
        rect(draw, left_x, shoulder_y, left_x + arm_w - 1, down_y2, colors["shirt"])
        rect(draw, right_x, shoulder_y, right_x + arm_w - 1, down_y2, colors["shirt"])
        rect(draw, left_x, down_y2, left_x + arm_w - 1, down_y2 + 1, colors["glove"])
        rect(draw, right_x, down_y2, right_x + arm_w - 1, down_y2 + 1, colors["glove"])
        return

    if arm_mode == "walk1":
        rect(draw, left_x, shoulder_y + 1, left_x + arm_w - 1, down_y2 + 1, colors["shirt"])
        rect(draw, right_x, shoulder_y - 1, right_x + arm_w - 1, down_y2 - 1, colors["shirt"])
        rect(draw, left_x, down_y2 + 1, left_x + arm_w - 1, down_y2 + 2, colors["glove"])
        rect(draw, right_x, down_y2 - 1, right_x + arm_w - 1, down_y2, colors["glove"])
        return

    if arm_mode == "walk2":
        rect(draw, left_x, shoulder_y - 1, left_x + arm_w - 1, down_y2 - 1, colors["shirt"])
        rect(draw, right_x, shoulder_y + 1, right_x + arm_w - 1, down_y2 + 1, colors["shirt"])
        rect(draw, left_x, down_y2 - 1, left_x + arm_w - 1, down_y2, colors["glove"])
        rect(draw, right_x, down_y2 + 1, right_x + arm_w - 1, down_y2 + 2, colors["glove"])
        return

    if arm_mode == "wave":
        rect(draw, left_x, shoulder_y, left_x + arm_w - 1, down_y2, colors["shirt"])
        rect(draw, left_x, down_y2, left_x + arm_w - 1, down_y2 + 1, colors["glove"])
        rect(draw, right_x, head_top - 1, right_x + arm_w - 1, shoulder_y + 2, colors["shirt"])
        rect(draw, right_x, head_top - 2, right_x + arm_w - 1, head_top - 1, colors["glove"])
        return

    if arm_mode == "jump":
        rect(draw, left_x, head_top, left_x + arm_w - 1, shoulder_y + 1, colors["shirt"])
        rect(draw, right_x, head_top, right_x + arm_w - 1, shoulder_y + 1, colors["shirt"])
        rect(draw, left_x, head_top - 1, left_x + arm_w - 1, head_top, colors["glove"])
        rect(draw, right_x, head_top - 1, right_x + arm_w - 1, head_top, colors["glove"])
        return

    if arm_mode == "think":
        rect(draw, left_x, shoulder_y, left_x + arm_w - 1, down_y2, colors["shirt"])
        rect(draw, left_x, down_y2, left_x + arm_w - 1, down_y2 + 1, colors["glove"])
        rect(draw, right_x, shoulder_y + 1, right_x + arm_w - 1, shoulder_y + 3, colors["shirt"])
        rect(draw, right_x, shoulder_y + 3, right_x + arm_w - 1, shoulder_y + 4, colors["glove"])
        return

    if arm_mode == "laugh":
        rect(draw, left_x, shoulder_y - 1, left_x + arm_w - 1, down_y2 - 1, colors["shirt"])
        rect(draw, right_x, shoulder_y - 1, right_x + arm_w - 1, down_y2 - 1, colors["shirt"])
        rect(draw, left_x, down_y2 - 1, left_x + arm_w - 1, down_y2, colors["glove"])
        rect(draw, right_x, down_y2 - 1, right_x + arm_w - 1, down_y2, colors["glove"])
        return

    if arm_mode == "surprise":
        rect(draw, left_x - 1, shoulder_y + 1, left_x + arm_w - 2, down_y2, colors["shirt"])
        rect(draw, right_x + 1, shoulder_y + 1, right_x + arm_w, down_y2, colors["shirt"])
        rect(draw, left_x - 1, down_y2, left_x + arm_w - 2, down_y2 + 1, colors["glove"])
        rect(draw, right_x + 1, down_y2, right_x + arm_w, down_y2 + 1, colors["glove"])
        return

    if arm_mode == "sleep":
        rect(draw, left_x, shoulder_y + 1, left_x + arm_w - 1, down_y2 + 1, colors["shirt_shadow"])
        rect(draw, right_x, shoulder_y + 1, right_x + arm_w - 1, down_y2 + 1, colors["shirt_shadow"])
        rect(draw, left_x, down_y2 + 1, left_x + arm_w - 1, down_y2 + 2, colors["glove"])
        rect(draw, right_x, down_y2 + 1, right_x + arm_w - 1, down_y2 + 2, colors["glove"])
        return

    rect(draw, left_x, head_top, left_x + arm_w - 1, shoulder_y + 2, colors["shirt"])
    rect(draw, left_x, head_top - 1, left_x + arm_w - 1, head_top, colors["glove"])
    rect(draw, right_x + 1, shoulder_y + 1, right_x + arm_w, down_y2, colors["shirt"])
    rect(draw, right_x + 1, down_y2, right_x + arm_w, down_y2 + 1, colors["glove"])


def draw_sprite(style: dict[str, Any], state: str) -> Image.Image:
    pose = POSES[state]
    validate_style(style)

    img = Image.new("RGBA", (style["canvas_w"], style["canvas_h"]), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    colors = style["colors"]

    cx = (style["canvas_w"] // 2) + pose["lean"]
    ground_y = style["canvas_h"] - 2 - pose["lift"]
    boot_top = ground_y - style["boot_h"] + 1
    leg_bottom = boot_top - 1
    leg_top = leg_bottom - style["leg_h"] + 1
    body_bottom = leg_top - 1
    body_top = body_bottom - style["body_h"] + 1
    head_bottom = body_top - 1
    head_top = head_bottom - style["head_h"] + 1

    body_left = cx - (style["body_w"] // 2)
    body_right = body_left + style["body_w"] - 1
    head_left = cx - (style["head_w"] // 2)
    head_right = head_left + style["head_w"] - 1

    draw_legs(draw, style, body_left, body_right, leg_top, leg_bottom, boot_top, ground_y, pose["leg"])

    rect(draw, body_left, body_top, body_right, body_bottom, colors["shirt"])
    rect(draw, body_left, body_bottom - 1, body_right, body_bottom, colors["shirt_shadow"])

    bib_left = cx - (style["body_w"] // 4)
    bib_right = cx + (style["body_w"] // 4)
    rect(draw, bib_left, body_top + 1, bib_right, body_bottom, colors["overall"])
    rect(draw, bib_left, body_bottom - 1, bib_right, body_bottom, colors["overall_shadow"])
    rect(draw, body_left + 1, body_top + 1, body_left + 3, body_bottom - 2, colors["overall"])
    rect(draw, body_right - 3, body_top + 1, body_right - 1, body_bottom - 2, colors["overall"])
    rect(draw, bib_left + 1, body_top + 3, bib_left + 2, body_top + 4, colors["button"])
    rect(draw, bib_right - 2, body_top + 3, bib_right - 1, body_top + 4, colors["button"])

    draw_arms(draw, style, body_left, body_right, body_top + 1, head_top, pose["arm"])

    hat_width = style["head_w"] + 2
    hat_left = cx - (hat_width // 2)
    hat_right = hat_left + hat_width - 1
    brim_left = head_left - 1
    brim_right = head_right + 1

    rect(draw, hat_left, head_top, hat_right, head_top + style["hat_h"] - 1, colors["shirt"])
    rect(draw, hat_left, head_top + style["hat_h"] - 1, hat_right, head_top + style["hat_h"] - 1, colors["shirt_shadow"])
    rect(draw, brim_left, head_top + style["hat_h"], brim_right, head_top + style["hat_h"] + style["brim_h"] - 1, colors["shirt"])
    rect(draw, brim_left, head_top + style["hat_h"] + style["brim_h"] - 1, brim_right, head_top + style["hat_h"] + style["brim_h"] - 1, colors["shirt_shadow"])

    face_top = head_top + style["hat_h"] + style["brim_h"]
    rect(draw, head_left, face_top, head_right, head_bottom, colors["skin"])
    rect(draw, head_left, face_top + 1, head_left + 1, head_bottom - 1, colors["hair"])
    rect(draw, head_right - 1, face_top + 1, head_right, head_bottom - 1, colors["hair"])

    eye_y = face_top + 1
    draw_eyes(draw, style, cx, eye_y, pose["eye"])

    nose_x1 = cx - (style["nose_w"] // 2)
    nose_x2 = nose_x1 + style["nose_w"] - 1
    nose_y1 = eye_y + style["eye_h"] + 1
    nose_y2 = nose_y1 + style["nose_h"] - 1
    rect(draw, nose_x1, nose_y1, nose_x2, nose_y2, colors["skin_shadow"])

    mustache_y1 = nose_y2 + 1
    mustache_y2 = mustache_y1 + style["mustache_h"] - 1
    mustache_x1 = cx - (style["mustache_w"] // 2)
    mustache_x2 = mustache_x1 + style["mustache_w"] - 1
    rect(draw, mustache_x1, mustache_y1, mustache_x2, mustache_y2, colors["mustache"])

    mouth_y = mustache_y2 + 1
    draw_mouth(draw, style, cx, mouth_y, pose["mouth"])

    if state == "sleep":
        rect(draw, head_right + 1, head_top - 2, head_right + 2, head_top - 2, colors["eye_white"])
        rect(draw, head_right + 3, head_top - 4, head_right + 4, head_top - 4, colors["eye_white"])

    return img


def write_notes(folder_path: str, style: dict[str, Any], index_num: int) -> None:
    notes = (
        f"Iteration {index_num:02d} - {style['id']}\n"
        f"{style['note']}\n\n"
        "Fresh build characteristics:\n"
        "- Drawn from shape primitives, not prior sprite grids\n"
        "- Includes hat, overalls, mustache, and large blue eyes\n"
        f"- Canvas: {style['canvas_w']}x{style['canvas_h']}, scale: {style['scale']}x\n"
    )
    with open(os.path.join(folder_path, "style_notes.txt"), "w", encoding="utf-8") as file:
        file.write(notes)


def write_index(records: list[dict[str, str]]) -> None:
    cards = []
    for record in records:
        cards.append(
            f"""
<div class="card">
  <h2>{record['title']}</h2>
  <p>{record['note']}</p>
  <div class="preview">
    <img src="{record['folder']}/mario_idle.png" alt="{record['title']} idle">
    <img src="{record['folder']}/mario_wave.png" alt="{record['title']} wave">
    <img src="{record['folder']}/mario_surprise.png" alt="{record['title']} surprise">
  </div>
</div>
"""
        )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Fresh Mario Boutique Iterations</title>
  <style>
    body {{
      margin: 0;
      padding: 24px;
      background: #11131a;
      color: #e9edf9;
      font-family: Arial, sans-serif;
    }}
    h1 {{
      margin: 0 0 8px 0;
      color: #ff6a60;
    }}
    .subtitle {{
      margin: 0 0 18px 0;
      color: #b9c1da;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 14px;
    }}
    .card {{
      background: #1a1f2d;
      border: 1px solid #2d3550;
      border-radius: 10px;
      padding: 12px;
    }}
    .card h2 {{
      margin: 0 0 6px 0;
      color: #90d2ff;
      font-size: 18px;
    }}
    .card p {{
      margin: 0 0 10px 0;
      color: #c6cee6;
      min-height: 42px;
    }}
    .preview {{
      display: flex;
      gap: 8px;
      align-items: flex-end;
      flex-wrap: wrap;
    }}
    img {{
      image-rendering: pixelated;
      max-width: 100px;
      height: auto;
      border-radius: 6px;
      border: 1px solid #2d3550;
      background: #090c14;
      padding: 2px;
    }}
  </style>
</head>
<body>
  <h1>Fresh Mario Boutique Iterations</h1>
  <p class="subtitle">10 from-scratch sets, all visually different.</p>
  <div class="grid">{''.join(cards)}</div>
</body>
</html>
"""
    with open(os.path.join(OUTPUT_DIR, "index.html"), "w", encoding="utf-8") as file:
        file.write(html)


def write_manifest(records: list[dict[str, str]]) -> None:
    lines = [
        "Fresh Mario Boutique Iterations",
        f"Generated: {datetime.now(UTC).isoformat()}",
        "",
    ]
    for record in records:
        lines.append(f"{record['title']} -> {record['folder']}")
        lines.append(f"  {record['note']}")
    lines.append("")
    with open(os.path.join(OUTPUT_DIR, "manifest.txt"), "w", encoding="utf-8") as file:
        file.write("\n".join(lines))


def generate_all() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    records: list[dict[str, str]] = []

    for index_num, style in enumerate(STYLES, start=1):
        folder_name = f"iteration_{index_num:02d}_{style['id']}"
        folder_path = os.path.join(OUTPUT_DIR, folder_name)
        os.makedirs(folder_path, exist_ok=True)

        for state in SPRITE_STATES:
            raw = draw_sprite(style, state)
            outlined = add_outline(raw)
            shadowed = add_drop_shadow(outlined)
            final = shadowed.resize(
                (shadowed.width * style["scale"], shadowed.height * style["scale"]),
                Image.NEAREST,
            )
            final.save(os.path.join(folder_path, f"mario_{state}.png"))

        write_notes(folder_path, style, index_num)
        records.append(
            {
                "title": f"#{index_num:02d} {style['id']}",
                "folder": folder_name,
                "note": style["note"],
            }
        )
        print(f"Created {folder_name}")

    write_manifest(records)
    write_index(records)
    print(f"\nDone: {len(STYLES)} fresh iteration folders written to {OUTPUT_DIR}")


if __name__ == "__main__":
    generate_all()
