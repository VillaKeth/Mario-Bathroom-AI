"""Import hand-made / premium sprites (e.g. ChatGPT-generated) for a character.

Workflow for replacing drip sprites with better manual ones:
  1. Generate an image for a pose (e.g. positive/happy).
  2. Save it into  characters/<char>/_incoming/  named after the pose with the
     slash as a dash or underscore, e.g.:
        positive-happy.png   or   positive_happy.png   or   happy.png
  3. Run:  venv/Scripts/python.exe scripts/import_sprites.py reze
  4. Each image is background-removed (rembg, transparent), installed to
     characters/<char>/sprites/<pose>.png, marked done in the flux drip state
     so the drip never overwrites your premium version, and the source moved to
     _incoming/done/.

Filename → pose matching is fuzzy: it matches the trailing segment of any of
the 39 canonical pose paths, so "happy.png" -> positive/happy, "wave.png" ->
greeting/wave, "talking_excited.png" -> speech/talking_excited.
"""
import json
import os
import shutil
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from character_creator import sprite_generator as sg  # noqa: E402

STATE_PATH = os.path.join(BASE, ".secrets", "flux_drip_state.json")


def _add_pose(idx, p):
    idx[p.replace("/", "_")] = p             # speech_talking_excited
    idx[p.replace("/", "-")] = p
    idx[p.split("/")[-1]] = p                # talking_excited


def _pose_index(char=None):
    """Map every matchable key -> sprite pose path.

    Starts from the canonical generation plan, then layers the ACTIVE
    character's own pose paths (from its character.yaml emotion/state/fallback
    maps) on top — so characters with custom pose names (e.g. Rudi's
    positive/smirk, greeting/casual_wave) match too. Character paths are added
    last so they win any trailing-segment collision for that character."""
    idx = {}
    for info in sg._generation_pose_plan():
        _add_pose(idx, info["sprite_path"])  # canonical fallback set

    if char:
        ypath = os.path.join(BASE, "characters", char, "character.yaml")
        if os.path.exists(ypath):
            import yaml
            v = (yaml.safe_load(open(ypath, encoding="utf-8")) or {}).get("visuals", {}) or {}
            for section in ("emotion_sprite_map", "state_sprite_map", "fallback_sprites"):
                for val in (v.get(section) or {}).values():
                    for p in (val if isinstance(val, list) else [val]):
                        if p:
                            _add_pose(idx, p)
    return idx


def _already_transparent(src_path, min_frac=0.02):
    """True if the image already has a real alpha channel with a meaningful
    amount of transparent pixels — i.e. someone already cut the background."""
    try:
        from PIL import Image
        import numpy as np
        im = Image.open(src_path)
        if im.mode not in ("RGBA", "LA", "PA"):
            return False
        a = np.asarray(im.convert("RGBA").split()[3])
        return (a < 10).mean() > min_frac
    except Exception:
        return False


_ANIME_SESSION = None


def _remove_bg_anime(src_path, out_path):
    """Best cutout for anime/illustration art: rembg's isnet-anime model + alpha
    matting. Trained on anime, so it keeps soft hair wisps, ribbon tails and
    thin limbs cleanly (matches the Win11 'Remove background' AI) without eating
    clothes. Used as the PRIMARY method for premium imports; flood-fill is the
    fallback for flat studio renders it might choke on. Returns True on success.
    """
    global _ANIME_SESSION
    try:
        from rembg import new_session, remove
        from PIL import Image
        import numpy as np
        if _ANIME_SESSION is None:
            _ANIME_SESSION = new_session("isnet-anime")
        out = remove(
            Image.open(src_path),
            session=_ANIME_SESSION,
            alpha_matting=True,
            alpha_matting_foreground_threshold=240,
            alpha_matting_background_threshold=10,
            alpha_matting_erode_size=10,
        )
        # Sanity: must keep a believable amount of the figure (not erase it,
        # not leave the whole frame opaque).
        kept = (np.asarray(out.split()[3]) > 30).mean()
        if 0.04 < kept < 0.97:
            out.save(out_path)
            return True
    except Exception as e:
        print(f"[import] isnet-anime failed ({e}); falling back")
    return False


def _remove_flat_bg(src_path, out_path, tol=46, feather=0):
    """Remove a FLAT studio background by flood-filling from the borders.

    Only pixels that are (a) close to the corner/background color AND (b)
    connected to the image edge become transparent. Interior regions of the
    same color (e.g. a white blouse, pale skin) are NEVER removed because they
    are not connected to the border — unlike ML matting (rembg), which was
    eating her clothes. Returns True on success.
    """
    import numpy as np
    from PIL import Image, ImageFilter
    from scipy import ndimage

    im = Image.open(src_path).convert("RGB")
    arr = np.asarray(im).astype(np.int16)
    h, w, _ = arr.shape

    # Background color = median of the four corners (robust to a noisy corner)
    corners = np.array([arr[0, 0], arr[0, w - 1], arr[h - 1, 0], arr[h - 1, w - 1]])
    bg = np.median(corners, axis=0)

    dist = np.sqrt(((arr - bg) ** 2).sum(axis=2))
    bg_like = dist < tol                      # pixels near the background color

    # Keep only the bg-like region CONNECTED to the border. Seed a 1px border
    # frame as background, label connected bg-like components, keep those that
    # touch the frame.
    seed = np.zeros((h, w), bool)
    seed[0, :] = seed[-1, :] = seed[:, 0] = seed[:, -1] = True
    labels, _ = ndimage.label(bg_like)
    border_labels = set(labels[seed & bg_like].tolist())
    border_labels.discard(0)
    background = np.isin(labels, list(border_labels))

    alpha = np.where(background, 0, 255).astype(np.uint8)
    out = Image.fromarray(arr.astype(np.uint8), "RGB").convert("RGBA")
    a_img = Image.fromarray(alpha, "L")
    if feather:
        a_img = a_img.filter(ImageFilter.GaussianBlur(feather))
    out.putalpha(a_img)
    final_alpha = np.asarray(out.split()[3])
    kept = (final_alpha > 30).mean()
    # Success only if: kept a sensible amount AND all 4 corners cleared. A
    # leftover opaque corner means the background was a gradient (e.g. 3D studio
    # render), not flat — bail to rembg instead of saving a half-keyed image.
    ch, cw = final_alpha.shape
    corners_clear = max(final_alpha[0, 0], final_alpha[0, cw - 1],
                        final_alpha[ch - 1, 0], final_alpha[ch - 1, cw - 1]) < 30
    if 0.04 < kept < 0.95 and corners_clear:
        out.save(out_path)
        return True
    return False


def _autocrop(png_path, pad_frac=0.04):
    """Crop a transparent-background PNG to the character's bounding box (+ small
    margin) so the figure fills the sprite instead of floating tiny in a huge
    landscape canvas. Keeps it RGBA."""
    from PIL import Image
    im = Image.open(png_path).convert("RGBA")
    bbox = im.split()[3].getbbox()  # alpha bounding box
    if not bbox:
        return
    w, h = im.size
    pad = int(max(w, h) * pad_frac)
    l, t, r, b = bbox
    l = max(0, l - pad); t = max(0, t - pad)
    r = min(w, r + pad); b = min(h, b + pad)
    im.crop((l, t, r, b)).save(png_path)


def _mark_done(char, pose):
    try:
        state = json.load(open(STATE_PATH, encoding="utf-8"))
    except Exception:
        state = {"done": []}
    key = f"{char}/{pose}"
    if key not in state.setdefault("done", []):
        state["done"].append(key)
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    json.dump(state, open(STATE_PATH, "w", encoding="utf-8"), indent=1)


def main():
    char = sys.argv[1] if len(sys.argv) > 1 else "reze"
    inbox = os.path.join(BASE, "characters", char, "_incoming")
    if not os.path.isdir(inbox):
        os.makedirs(inbox, exist_ok=True)
        print(f"[import] created {inbox} — drop pose-named images there and re-run")
        return
    done_dir = os.path.join(inbox, "done")
    os.makedirs(done_dir, exist_ok=True)
    idx = _pose_index(char)

    imported = 0
    for fn in sorted(os.listdir(inbox)):
        src = os.path.join(inbox, fn)
        if not os.path.isfile(src) or not fn.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            continue
        stem = os.path.splitext(fn)[0].lower().strip()
        pose = idx.get(stem)
        if not pose:
            print(f"[import] {fn}: no matching pose (use names like positive_happy.png) — skipped")
            continue
        out = os.path.join(BASE, "characters", char, "sprites", f"{pose}.png")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        # If the source ALREADY has a transparent background (e.g. you cut it
        # yourself with the Win11 'Remove background' tool), keep it verbatim —
        # don't re-key a clean cutout. Otherwise: isnet-anime (best for anime
        # soft edges), then flat-bg flood fill, then general rembg.
        if _already_transparent(src):
            from PIL import Image
            Image.open(src).convert("RGBA").save(out)
            print(f"[import] {fn}: already transparent — kept as-is")
        elif not _remove_bg_anime(src, out) and not _remove_flat_bg(src, out):
            with open(src, "rb") as f:
                sg._try_remove_background(f.read(), out)
        _autocrop(out)  # trim huge transparent margins so the figure fills the sprite
        _mark_done(char, pose)
        shutil.move(src, os.path.join(done_dir, fn))
        imported += 1
        print(f"[import] {fn} -> sprites/{pose}.png (bg removed, drip-protected)")

    print(f"[import] DONE: {imported} sprite(s) imported for {char}")


if __name__ == "__main__":
    main()
