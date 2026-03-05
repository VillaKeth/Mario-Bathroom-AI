"""
Mario Expressive Poses V2 — ACTUAL body manipulation.
Segments arms from body and repositions them, paints face expressions,
creates genuinely different poses (not just tilts + overlays).
"""
import os
import math
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance

OUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'mario_3d_assets', 'expressive_v2')
BASE_PATH = os.path.join(os.path.dirname(__file__), '..', 'mario_assets', 'Mario_New_Super_Mario_Bros_U_Deluxe.webp')
CANVAS_W, CANVAS_H = 400, 500

# ─── Prepare base image ──────────────────────────────────────────────
def prepare_base():
    img = Image.open(BASE_PATH).convert('RGBA')
    arr = np.array(img)
    corners = [arr[0,0,:3], arr[0,-1,:3], arr[-1,0,:3], arr[-1,-1,:3]]
    bg = np.mean(corners, axis=0)
    dist = np.sqrt(np.sum((arr[:,:,:3].astype(float) - bg)**2, axis=2))
    arr[dist < 30, 3] = 0
    alpha = arr[:,:,3]
    rows = np.any(alpha > 0, axis=1)
    cols = np.any(alpha > 0, axis=0)
    y1, y2 = np.where(rows)[0][[0,-1]]
    x1, x2 = np.where(cols)[0][[0,-1]]
    cropped = Image.fromarray(arr[y1:y2+1, x1:x2+1])
    cropped.thumbnail((380, 480), Image.LANCZOS)
    canvas = Image.new('RGBA', (CANVAS_W, CANVAS_H), (0,0,0,0))
    ox = (CANVAS_W - cropped.width) // 2
    oy = (CANVAS_H - cropped.height) // 2
    canvas.paste(cropped, (ox, oy), cropped)
    return canvas

# ─── Body part segmentation ──────────────────────────────────────────
class MarioBody:
    """Segments Mario into manipulable body parts."""
    def __init__(self, base_img):
        self.base = base_img.copy()
        self.arr = np.array(base_img)
        self.h, self.w = self.arr.shape[:2]
        r, g, b, a = self.arr[:,:,0], self.arr[:,:,1], self.arr[:,:,2], self.arr[:,:,3]
        self.visible = a > 128
        self.red_mask = self.visible & (r > 150) & (g < 80) & (b < 80)
        self.blue_mask = self.visible & (b > 120) & (r < 100) & (g < 100)
        self.white_mask = self.visible & (r > 200) & (g > 200) & (b > 200)
        self.skin_mask = self.visible & (r > 180) & (g > 130) & (g < 200) & (b > 80) & (b < 160)
        self.dark_mask = self.visible & (r < 60) & (g < 60) & (b < 60)
        self.brown_mask = self.visible & (r > 100) & (r < 180) & (g > 40) & (g < 110) & (b < 80)
        self._find_body_parts()

    def _find_body_parts(self):
        # Overall bounding box from blue overalls
        bc = np.where(self.blue_mask)
        self.body_top = bc[0].min() if len(bc[0]) > 0 else 200
        self.body_left = bc[1].min() if len(bc[0]) > 0 else 110
        self.body_right = bc[1].max() if len(bc[0]) > 0 else 290
        # Face region
        fc = np.where(self.skin_mask & (np.arange(self.h)[:,None] < self.body_top))
        if len(fc[0]) > 0:
            self.face_y1, self.face_y2 = fc[0].min(), fc[0].max()
            self.face_x1, self.face_x2 = fc[1].min(), fc[1].max()
        else:
            self.face_y1, self.face_y2 = 25, 106
            self.face_x1, self.face_x2 = 141, 257
        self.face_cx = (self.face_x1 + self.face_x2) // 2
        self.face_cy = (self.face_y1 + self.face_y2) // 2
        # Body center x
        self.body_cx = (self.body_left + self.body_right) // 2

    def extract_arm(self, side='right'):
        """Extract arm+glove as separate image. Returns (image, mask, bbox)."""
        arm_or_glove = self.red_mask | self.white_mask
        if side == 'right':
            # Right arm: pixels to the right of the body center, below face, that are red/white
            # Find body right edge per row using blue pixels
            arm_mask = np.zeros_like(self.visible)
            for y in range(self.face_y2, self.h):
                blue_row = np.where(self.blue_mask[y])[0]
                if len(blue_row) > 0:
                    edge = blue_row.max()
                else:
                    edge = self.body_cx + 20
                # Arm pixels are arm-colored pixels past the body edge
                arm_mask[y, edge-5:] = arm_or_glove[y, edge-5:]
            # Also get red sleeve pixels above overalls on right side
            for y in range(self.face_y2, self.body_top):
                arm_mask[y, self.body_cx+20:] = self.red_mask[y, self.body_cx+20:]
        else:
            arm_mask = np.zeros_like(self.visible)
            for y in range(self.face_y2, self.h):
                blue_row = np.where(self.blue_mask[y])[0]
                if len(blue_row) > 0:
                    edge = blue_row.min()
                else:
                    edge = self.body_cx - 20
                arm_mask[y, :edge+5] = arm_or_glove[y, :edge+5]
            for y in range(self.face_y2, self.body_top):
                arm_mask[y, :self.body_cx-20] = self.red_mask[y, :self.body_cx-20]

        # Get bounding box of arm
        coords = np.where(arm_mask)
        if len(coords[0]) == 0:
            return None, None, None
        ay1, ay2 = coords[0].min(), coords[0].max()
        ax1, ax2 = coords[1].min(), coords[1].max()
        # Extract
        arm_img = self.arr[ay1:ay2+1, ax1:ax2+1].copy()
        arm_m = arm_mask[ay1:ay2+1, ax1:ax2+1]
        arm_img[~arm_m, 3] = 0  # Make non-arm pixels transparent
        return Image.fromarray(arm_img), arm_mask, (ax1, ay1, ax2, ay2)

    def get_body_without_arm(self, side='right'):
        """Return base image with the specified arm erased (filled with overalls blue)."""
        result = self.arr.copy()
        _, arm_mask, bbox = self.extract_arm(side)
        if arm_mask is None:
            return Image.fromarray(result)
        # Fill arm area with nearby blue overalls color or transparent
        # Sample blue color from overalls
        bc = np.where(self.blue_mask)
        if len(bc[0]) > 0:
            avg_blue = np.mean(self.arr[bc[0][:100], bc[1][:100]], axis=0).astype(np.uint8)
        else:
            avg_blue = np.array([30, 50, 180, 255], dtype=np.uint8)
        # Only fill where arm overlaps body region (not protruding parts)
        for y in range(self.h):
            for x in range(self.w):
                if arm_mask[y, x]:
                    # Check if there's body behind (blue overalls area)
                    if self.body_left-10 <= x <= self.body_right+10 and y >= self.body_top-5:
                        result[y, x] = avg_blue
                    else:
                        result[y, x, 3] = 0  # Transparent where arm was outside body
        return Image.fromarray(result)

    def get_shoulder_point(self, side='right'):
        """Get approximate shoulder connection point."""
        if side == 'right':
            return (self.body_right - 15, self.body_top + 20)
        else:
            return (self.body_left + 15, self.body_top + 20)


def rotate_arm(arm_img, angle, pivot_ratio=(0.5, 0.0)):
    """Rotate arm image around a pivot point. angle in degrees, 0=down, positive=counterclockwise."""
    if arm_img is None:
        return None
    w, h = arm_img.size
    px, py = int(w * pivot_ratio[0]), int(h * pivot_ratio[1])
    # Expand canvas for rotation
    diag = int(math.sqrt(w*w + h*h)) + 20
    expanded = Image.new('RGBA', (diag, diag), (0,0,0,0))
    ex = (diag - w) // 2
    ey = (diag - h) // 2
    expanded.paste(arm_img, (ex, ey), arm_img)
    # Rotate around center
    rotated = expanded.rotate(angle, Image.BICUBIC, expand=False, center=(ex+px, ey+py))
    # Crop to content
    arr = np.array(rotated)
    alpha = arr[:,:,3]
    rows = np.any(alpha > 0, axis=1)
    cols = np.any(alpha > 0, axis=0)
    if not np.any(rows):
        return arm_img
    ry1, ry2 = np.where(rows)[0][[0,-1]]
    rx1, rx2 = np.where(cols)[0][[0,-1]]
    return Image.fromarray(arr[ry1:ry2+1, rx1:rx2+1])


# ─── Face painting ───────────────────────────────────────────────────
class FacePainter:
    """Paint different facial expressions onto Mario."""
    def __init__(self, body: MarioBody):
        self.body = body
        # Eye positions (approximate from analysis)
        face_h = body.face_y2 - body.face_y1
        face_w = body.face_x2 - body.face_x1
        # Eyes are roughly in the upper-middle of the face
        eye_y_center = body.face_y1 + int(face_h * 0.45)
        self.left_eye_center = (body.face_cx - int(face_w * 0.18), eye_y_center)
        self.right_eye_center = (body.face_cx + int(face_w * 0.18), eye_y_center)
        self.eye_radius = max(4, int(face_w * 0.09))
        # Mouth is in the lower face (under mustache)
        self.mouth_center = (body.face_cx, body.face_y2 - int(face_h * 0.15))
        self.mouth_width = int(face_w * 0.3)

    def paint_eyes(self, img, style='open'):
        """Paint different eye styles. Returns modified image."""
        draw = ImageDraw.Draw(img)
        lx, ly = self.left_eye_center
        rx, ry = self.right_eye_center
        r = self.eye_radius

        if style == 'closed':
            # Horizontal lines for closed eyes
            draw.line([(lx-r, ly), (lx+r, ly)], fill=(0,0,0,255), width=3)
            draw.line([(rx-r, ry), (rx+r, ry)], fill=(0,0,0,255), width=3)
        elif style == 'half':
            # Half-closed (sleepy/suspicious)
            draw.arc([(lx-r, ly-r//2), (lx+r, ly+r//2)], 0, 180, fill=(0,0,0,255), width=2)
            draw.arc([(rx-r, ry-r//2), (rx+r, ry+r//2)], 0, 180, fill=(0,0,0,255), width=2)
        elif style == 'wide':
            # Extra-wide eyes (surprised)
            wr = int(r * 1.5)
            draw.ellipse([(lx-wr, ly-wr), (lx+wr, ly+wr)], fill=(255,255,255,255), outline=(0,0,0,255), width=2)
            draw.ellipse([(lx-r//2, ly-r//2), (lx+r//2, ly+r//2)], fill=(30,100,200,255))
            draw.ellipse([(rx-wr, ry-wr), (rx+wr, ry+wr)], fill=(255,255,255,255), outline=(0,0,0,255), width=2)
            draw.ellipse([(rx-r//2, ry-r//2), (rx+r//2, ry+r//2)], fill=(30,100,200,255))
        elif style == 'angry':
            # Angled eyebrows + narrowed eyes
            draw.line([(lx-r-3, ly-r-5), (lx+r+3, ly-r+2)], fill=(0,0,0,255), width=4)
            draw.line([(rx-r-3, ry-r+2), (rx+r+3, ry-r-5)], fill=(0,0,0,255), width=4)
        elif style == 'sad':
            # Droopy eyebrows
            draw.arc([(lx-r-3, ly-r-8), (lx+r+3, ly-2)], 200, 340, fill=(0,0,0,255), width=3)
            draw.arc([(rx-r-3, ry-r-8), (rx+r+3, ry-2)], 200, 340, fill=(0,0,0,255), width=3)
        elif style == 'wink_right':
            # Right eye closed, left normal
            draw.line([(rx-r, ry), (rx+r, ry)], fill=(0,0,0,255), width=3)
        elif style == 'wink_left':
            draw.line([(lx-r, ly), (lx+r, ly)], fill=(0,0,0,255), width=3)
        elif style == 'looking_left':
            # Pupils shifted left
            off = r // 2
            draw.ellipse([(lx-off-2, ly-2), (lx-off+2, ly+2)], fill=(0,0,0,255))
            draw.ellipse([(rx-off-2, ry-2), (rx-off+2, ry+2)], fill=(0,0,0,255))
        elif style == 'looking_right':
            off = r // 2
            draw.ellipse([(lx+off-2, ly-2), (lx+off+2, ly+2)], fill=(0,0,0,255))
            draw.ellipse([(rx+off-2, ry-2), (rx+off+2, ry+2)], fill=(0,0,0,255))
        elif style == 'looking_up':
            off = r // 2
            draw.ellipse([(lx-2, ly-off-2), (lx+2, ly-off+2)], fill=(0,0,0,255))
            draw.ellipse([(rx-2, ry-off-2), (rx+2, ry-off+2)], fill=(0,0,0,255))
        elif style == 'sparkle':
            # Sparkling star eyes
            for cx, cy in [(lx, ly), (rx, ry)]:
                for angle in range(0, 360, 45):
                    ex = cx + int(r * 1.2 * math.cos(math.radians(angle)))
                    ey = cy + int(r * 1.2 * math.sin(math.radians(angle)))
                    draw.line([(cx, cy), (ex, ey)], fill=(255,215,0,255), width=2)
        elif style == 'heart':
            for cx, cy in [(lx, ly), (rx, ry)]:
                hr = r
                draw.ellipse([(cx-hr, cy-hr), (cx, cy)], fill=(255,0,80,255))
                draw.ellipse([(cx, cy-hr), (cx+hr, cy)], fill=(255,0,80,255))
                draw.polygon([(cx-hr, cy-hr//3), (cx, cy+hr), (cx+hr, cy-hr//3)], fill=(255,0,80,255))
        elif style == 'spiral':
            # Dizzy spiral eyes
            for cx, cy in [(lx, ly), (rx, ry)]:
                for t in range(0, 720, 15):
                    rad = t / 720 * r * 1.5
                    px = cx + int(rad * math.cos(math.radians(t)))
                    py = cy + int(rad * math.sin(math.radians(t)))
                    draw.point((px, py), fill=(0,0,0,255))
        return img

    def paint_mouth(self, img, style='neutral'):
        draw = ImageDraw.Draw(img)
        mx, my = self.mouth_center
        mw = self.mouth_width

        if style == 'open':
            draw.ellipse([(mx-mw//3, my-4), (mx+mw//3, my+8)], fill=(40,0,0,255), outline=(0,0,0,255), width=2)
        elif style == 'wide_open':
            draw.ellipse([(mx-mw//2, my-6), (mx+mw//2, my+12)], fill=(40,0,0,255), outline=(0,0,0,255), width=2)
            # Tongue
            draw.ellipse([(mx-mw//4, my+2), (mx+mw//4, my+10)], fill=(220,80,80,255))
        elif style == 'smile':
            draw.arc([(mx-mw//2, my-6), (mx+mw//2, my+8)], 10, 170, fill=(0,0,0,255), width=3)
        elif style == 'big_smile':
            draw.arc([(mx-mw//2, my-8), (mx+mw//2, my+10)], 0, 180, fill=(0,0,0,255), width=3)
            draw.chord([(mx-mw//2, my-2), (mx+mw//2, my+10)], 0, 180, fill=(40,0,0,255), outline=(0,0,0,255))
        elif style == 'frown':
            draw.arc([(mx-mw//3, my), (mx+mw//3, my+12)], 190, 350, fill=(0,0,0,255), width=3)
        elif style == 'tongue_out':
            draw.ellipse([(mx-4, my+2), (mx+4, my+12)], fill=(220,80,80,255), outline=(0,0,0,255))
        elif style == 'gritted':
            # Gritted teeth
            draw.rectangle([(mx-mw//3, my-2), (mx+mw//3, my+6)], fill=(255,255,255,255), outline=(0,0,0,255))
            for i in range(-mw//3+4, mw//3, 5):
                draw.line([(mx+i, my-2), (mx+i, my+6)], fill=(0,0,0,180), width=1)
        elif style == 'whistle':
            draw.ellipse([(mx-4, my-3), (mx+4, my+5)], fill=(40,0,0,255), outline=(0,0,0,255), width=2)
        return img

    def add_blush(self, img, intensity=1.0):
        draw = ImageDraw.Draw(img)
        face_w = self.body.face_x2 - self.body.face_x1
        r = int(face_w * 0.12)
        alpha = int(120 * intensity)
        ly = self.left_eye_center[1] + int(r * 1.5)
        ry = self.right_eye_center[1] + int(r * 1.5)
        draw.ellipse([(self.left_eye_center[0]-r, ly-r//2),
                       (self.left_eye_center[0]+r, ly+r//2)],
                      fill=(255, 100, 100, alpha))
        draw.ellipse([(self.right_eye_center[0]-r, ry-r//2),
                       (self.right_eye_center[0]+r, ry+r//2)],
                      fill=(255, 100, 100, alpha))
        return img

    def add_tears(self, img, count=2):
        draw = ImageDraw.Draw(img)
        for cx, cy in [(self.left_eye_center[0]-2, self.left_eye_center[1]+self.eye_radius+2),
                       (self.right_eye_center[0]+2, self.right_eye_center[1]+self.eye_radius+2)]:
            for i in range(count):
                ty = cy + i * 12
                draw.ellipse([(cx-2, ty), (cx+2, ty+6)], fill=(100,180,255,200))
        return img

    def add_sweat_drop(self, img, side='right'):
        draw = ImageDraw.Draw(img)
        if side == 'right':
            sx = self.body.face_x2 + 5
        else:
            sx = self.body.face_x1 - 10
        sy = self.body.face_y1 + 10
        draw.polygon([(sx+3, sy), (sx, sy+10), (sx+6, sy+10)], fill=(100,180,255,220))
        draw.ellipse([(sx, sy+7), (sx+6, sy+13)], fill=(100,180,255,220))
        return img

    def add_anger_veins(self, img, count=2):
        draw = ImageDraw.Draw(img)
        positions = [(self.body.face_x2-5, self.body.face_y1+5),
                     (self.body.face_x1+5, self.body.face_y1+5)]
        for i in range(min(count, len(positions))):
            cx, cy = positions[i]
            s = 6
            draw.line([(cx-s, cy), (cx+s, cy)], fill=(200,0,0,255), width=2)
            draw.line([(cx, cy-s), (cx, cy+s)], fill=(200,0,0,255), width=2)
            draw.line([(cx-s+2, cy-s+2), (cx+s-2, cy+s-2)], fill=(200,0,0,255), width=2)
            draw.line([(cx+s-2, cy-s+2), (cx-s+2, cy+s-2)], fill=(200,0,0,255), width=2)
        return img


# ─── Overlay drawing helpers ─────────────────────────────────────────
def draw_speech_bubble(img, text, pos=None, size='medium'):
    draw = ImageDraw.Draw(img)
    if pos is None:
        pos = (CANVAS_W // 2 + 40, 30)
    try:
        font_size = {'small': 11, 'medium': 14, 'large': 18}[size]
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = ImageFont.load_default()
    tw = len(text) * (font_size * 0.6)
    th = font_size + 4
    bx1 = pos[0] - 5
    by1 = pos[1] - 3
    bx2 = pos[0] + int(tw) + 10
    by2 = pos[1] + int(th) + 6
    draw.rounded_rectangle([(bx1, by1), (bx2, by2)], radius=8, fill=(255,255,255,230), outline=(0,0,0,200), width=2)
    # Tail
    tx = bx1 + 10
    draw.polygon([(tx, by2), (tx+5, by2+10), (tx+12, by2)], fill=(255,255,255,230), outline=(0,0,0,200))
    draw.text((pos[0]+3, pos[1]+2), text, fill=(0,0,0,255), font=font)
    return img

def draw_thought_bubble(img, text='', pos=None):
    draw = ImageDraw.Draw(img)
    if pos is None:
        pos = (CANVAS_W // 2 + 30, 20)
    try:
        font = ImageFont.truetype("arial.ttf", 12)
    except:
        font = ImageFont.load_default()
    tw = max(60, len(text) * 7 + 20) if text else 50
    # Cloud shape
    cx, cy = pos[0] + tw//2, pos[1] + 15
    for ox, oy, r in [(-tw//4, 0, 18), (0, -5, 22), (tw//4, 0, 18), (-tw//6, 8, 14), (tw//6, 8, 14)]:
        draw.ellipse([(cx+ox-r, cy+oy-r), (cx+ox+r, cy+oy+r)], fill=(255,255,255,220), outline=(200,200,200,200))
    # Thought dots
    for i, r in enumerate([6, 4, 3]):
        draw.ellipse([(cx-tw//3-5-i*8, cy+25+i*8-r), (cx-tw//3-5-i*8+r*2, cy+25+i*8+r)],
                     fill=(255,255,255,220), outline=(200,200,200,200))
    if text:
        draw.text((cx - len(text)*3, cy-5), text, fill=(80,80,80,255), font=font)
    return img

def draw_sparkles(img, count=6, region=None):
    draw = ImageDraw.Draw(img)
    if region is None:
        region = (50, 20, CANVAS_W-50, CANVAS_H//3)
    for _ in range(count):
        x = np.random.randint(region[0], region[2])
        y = np.random.randint(region[1], region[3])
        s = np.random.randint(2, 6)
        color = random.choice([(255,255,100,255), (255,220,50,255), (255,255,200,255)])
        draw.line([(x-s, y), (x+s, y)], fill=color, width=1)
        draw.line([(x, y-s), (x, y+s)], fill=color, width=1)
    return img

def draw_music_notes(img, count=4):
    draw = ImageDraw.Draw(img)
    for i in range(count):
        x = np.random.randint(30, CANVAS_W-30)
        y = np.random.randint(20, CANVAS_H//3)
        s = np.random.randint(6, 12)
        color = random.choice([(50,200,50,255), (200,50,200,255), (50,150,255,255), (255,200,50,255)])
        draw.ellipse([(x, y), (x+s, y+s-2)], fill=color)
        draw.line([(x+s, y+s-2), (x+s, y-s*2)], fill=color, width=2)
        if np.random.random() > 0.5:
            draw.line([(x+s, y-s*2), (x+s+s, y-s*2+3)], fill=color, width=2)
    return img

def draw_zzz(img, count=3, pos=None):
    draw = ImageDraw.Draw(img)
    if pos is None:
        pos = (CANVAS_W // 2 + 50, 30)
    try:
        fonts = [ImageFont.truetype("arial.ttf", s) for s in [10, 14, 18]]
    except:
        fonts = [ImageFont.load_default()] * 3
    for i in range(count):
        x = pos[0] + i * 18
        y = pos[1] - i * 20
        draw.text((x, y), 'Z', fill=(200,200,255,200-i*40), font=fonts[min(i, len(fonts)-1)])
    return img

def draw_hearts(img, count=4):
    draw = ImageDraw.Draw(img)
    for i in range(count):
        cx = np.random.randint(50, CANVAS_W-50)
        cy = np.random.randint(20, CANVAS_H//3)
        s = np.random.randint(4, 10)
        color = (255, np.random.randint(50,150), np.random.randint(100,180), 220)
        draw.ellipse([(cx-s, cy-s), (cx, cy)], fill=color)
        draw.ellipse([(cx, cy-s), (cx+s, cy)], fill=color)
        draw.polygon([(cx-s, cy-s//3), (cx, cy+s), (cx+s, cy-s//3)], fill=color)
    return img

def draw_exclamation(img, pos=None):
    draw = ImageDraw.Draw(img)
    if pos is None:
        pos = (CANVAS_W//2 + 60, 15)
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except:
        font = ImageFont.load_default()
    draw.text(pos, '!', fill=(255,50,50,255), font=font)
    return img

def draw_question_marks(img, count=2, pos=None):
    draw = ImageDraw.Draw(img)
    if pos is None:
        pos = (CANVAS_W//2 + 40, 15)
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()
    for i in range(count):
        draw.text((pos[0]+i*20, pos[1]-i*5), '?', fill=(100,150,255,220), font=font)
    return img

def draw_motion_lines(img, direction='up'):
    draw = ImageDraw.Draw(img)
    cx = CANVAS_W // 2
    if direction == 'up':
        for i in range(5):
            x = cx - 40 + i * 20
            draw.line([(x, CANVAS_H-30), (x, CANVAS_H-30-np.random.randint(15,40))],
                     fill=(100,100,100,150), width=2)
    elif direction == 'horizontal':
        for i in range(4):
            y = 200 + i * 30
            draw.line([(20, y), (20+np.random.randint(20,50), y)],
                     fill=(100,100,100,150), width=2)
    return img

def draw_shadow(img, y=None, width=None):
    draw = ImageDraw.Draw(img)
    if y is None:
        y = CANVAS_H - 25
    if width is None:
        width = 80
    draw.ellipse([(CANVAS_W//2-width, y-5), (CANVAS_W//2+width, y+5)],
                fill=(0,0,0,60))
    return img

def draw_fire_particles(img, count=5):
    draw = ImageDraw.Draw(img)
    for _ in range(count):
        x = np.random.randint(30, CANVAS_W-30)
        y = np.random.randint(CANVAS_H//2, CANVAS_H-50)
        s = np.random.randint(3, 8)
        colors = [(255,100,0,200), (255,200,0,200), (255,50,0,200)]
        c = random.choice(colors)
        draw.ellipse([(x-s, y-s), (x+s, y+s)], fill=c)
    return img

def apply_color_tint(img, color, strength=0.3):
    """Apply color tint to image. color=(r,g,b), strength 0-1."""
    arr = np.array(img).astype(float)
    alpha = arr[:,:,3:]
    rgb = arr[:,:,:3]
    tint = np.array(color, dtype=float)
    rgb = rgb * (1 - strength) + tint * strength
    rgb = np.clip(rgb, 0, 255)
    result = np.concatenate([rgb, alpha], axis=2).astype(np.uint8)
    return Image.fromarray(result)

def apply_brightness(img, factor=1.0):
    """Adjust brightness. <1 = darker, >1 = brighter."""
    enhancer = ImageEnhance.Brightness(img)
    return enhancer.enhance(factor)


# ─── Pose composition ────────────────────────────────────────────────
def compose_with_raised_arm(body: MarioBody, side='right', angle=90, arm_offset=(0,0)):
    """Create image with arm raised to specified angle."""
    # Get body without the arm
    base = body.get_body_without_arm(side)
    # Get isolated arm
    arm_img, _, bbox = body.extract_arm(side)
    if arm_img is None:
        return base
    # Rotate arm
    pivot = (0.5, 0.0) if side == 'right' else (0.5, 0.0)
    if side == 'right':
        rotated = rotate_arm(arm_img, angle, pivot)
    else:
        rotated = rotate_arm(arm_img, -angle, pivot)
    if rotated is None:
        return base
    # Get shoulder point
    sx, sy = body.get_shoulder_point(side)
    # Position rotated arm at shoulder
    px = sx - rotated.width // 2 + arm_offset[0]
    py = sy - 10 + arm_offset[1]
    if side == 'left':
        px = sx - rotated.width // 2 + arm_offset[0]
    # Paste arm
    base.paste(rotated, (px, py), rotated)
    return base


# ─── POSE DEFINITIONS ────────────────────────────────────────────────
POSES = []

def pose(name, category, description):
    def decorator(func):
        POSES.append((name, category, description, func))
        return func
    return decorator

# ── IDLE / NEUTRAL ──
@pose('idle', 'Neutral', 'Default standing pose')
def _(body, face):
    return body.base.copy()

@pose('idle_blink', 'Neutral', 'Eyes closed — blink frame')
def _(body, face):
    img = body.base.copy()
    return face.paint_eyes(img, 'closed')

@pose('idle_wink', 'Neutral', 'Playful wink — right eye closed')
def _(body, face):
    img = body.base.copy()
    img = face.paint_eyes(img, 'wink_right')
    return face.paint_mouth(img, 'smile')

@pose('looking_left', 'Neutral', 'Eyes shifted left')
def _(body, face):
    img = body.base.copy()
    return face.paint_eyes(img, 'looking_left')

@pose('looking_right', 'Neutral', 'Eyes shifted right')
def _(body, face):
    img = body.base.copy()
    return face.paint_eyes(img, 'looking_right')

@pose('looking_up', 'Neutral', 'Eyes looking upward')
def _(body, face):
    img = body.base.copy()
    return face.paint_eyes(img, 'looking_up')

# ── WAVING (ACTUAL ARM MOVEMENT) ──
@pose('wave_right_high', 'Greeting', 'Right arm raised high — actual wave!')
def _(body, face):
    img = compose_with_raised_arm(body, 'right', angle=120, arm_offset=(20, -40))
    img = face.paint_mouth(img, 'big_smile')
    return draw_speech_bubble(img, "Hey there!", (CANVAS_W//2+20, 15))

@pose('wave_right_mid', 'Greeting', 'Right arm at shoulder height wave')
def _(body, face):
    img = compose_with_raised_arm(body, 'right', angle=70, arm_offset=(15, -20))
    return face.paint_mouth(img, 'smile')

@pose('wave_left_high', 'Greeting', 'Left arm raised high wave')
def _(body, face):
    img = compose_with_raised_arm(body, 'left', angle=120, arm_offset=(-20, -40))
    img = face.paint_mouth(img, 'big_smile')
    return draw_speech_bubble(img, "Ciao!", (30, 15))

@pose('wave_both', 'Greeting', 'Both arms raised — big hello!')
def _(body, face):
    # Remove both arms
    base = body.get_body_without_arm('right')
    body2 = MarioBody(base)
    base2 = body2.get_body_without_arm('left')
    # Get and rotate both arms
    r_arm, _, _ = body.extract_arm('right')
    l_arm, _, _ = body.extract_arm('left')
    if r_arm:
        r_rot = rotate_arm(r_arm, 130, (0.5, 0.0))
        if r_rot:
            sx, sy = body.get_shoulder_point('right')
            base2.paste(r_rot, (sx-r_rot.width//2+20, sy-50), r_rot)
    if l_arm:
        l_rot = rotate_arm(l_arm, -130, (0.5, 0.0))
        if l_rot:
            sx, sy = body.get_shoulder_point('left')
            base2.paste(l_rot, (sx-l_rot.width//2-20, sy-50), l_rot)
    base2 = face.paint_mouth(base2, 'big_smile')
    return draw_speech_bubble(base2, "Welcome!!", (CANVAS_W//2-30, 10), 'large')

@pose('greeting_hello', 'Greeting', 'Friendly hello with right arm wave + sparkles')
def _(body, face):
    img = compose_with_raised_arm(body, 'right', angle=100, arm_offset=(18, -30))
    img = face.paint_mouth(img, 'big_smile')
    img = draw_sparkles(img, 4)
    return draw_speech_bubble(img, "It's-a me!", (CANVAS_W//2+10, 15))

@pose('greeting_welcome', 'Greeting', 'Welcoming with both arms out')
def _(body, face):
    img = compose_with_raised_arm(body, 'right', angle=60, arm_offset=(20, -10))
    img = face.paint_mouth(img, 'smile')
    return draw_speech_bubble(img, "Welcome!", (CANVAS_W//2+30, 20))

@pose('farewell', 'Greeting', 'Goodbye wave — arm up + speech')
def _(body, face):
    img = compose_with_raised_arm(body, 'right', angle=110, arm_offset=(18, -35))
    img = face.paint_mouth(img, 'smile')
    return draw_speech_bubble(img, "See ya!", (CANVAS_W//2+20, 15))

# ── TALKING ──
@pose('talking_mouth_open', 'Speech', 'Mouth open — talking frame 1')
def _(body, face):
    img = body.base.copy()
    return face.paint_mouth(img, 'open')

@pose('talking_mouth_wide', 'Speech', 'Mouth wide open — loud/shouting')
def _(body, face):
    img = body.base.copy()
    img = face.paint_mouth(img, 'wide_open')
    return draw_speech_bubble(img, "WAHOO!", (CANVAS_W//2+30, 15), 'large')

@pose('talking_excited', 'Speech', 'Excited talking — arm gesture + big mouth')
def _(body, face):
    img = compose_with_raised_arm(body, 'right', angle=45, arm_offset=(10, -5))
    img = face.paint_mouth(img, 'open')
    return draw_speech_bubble(img, "Let's-a go!", (CANVAS_W//2+20, 20))

@pose('talking_quiet', 'Speech', 'Quiet talking — small mouth, leaning in')
def _(body, face):
    # Slight tilt
    img = body.base.copy().rotate(-3, Image.BICUBIC, expand=False, fillcolor=(0,0,0,0))
    img = face.paint_mouth(img, 'whistle')
    return draw_speech_bubble(img, "psst...", (CANVAS_W//2+40, 25), 'small')

@pose('shouting', 'Speech', 'Shouting — very wide mouth + arm up')
def _(body, face):
    img = compose_with_raised_arm(body, 'right', angle=80, arm_offset=(15, -20))
    img = face.paint_eyes(img, 'wide')
    img = face.paint_mouth(img, 'wide_open')
    return draw_speech_bubble(img, "MAMA MIA!", (CANVAS_W//2+10, 10), 'large')

@pose('singing', 'Speech', 'Singing — open mouth + music notes')
def _(body, face):
    img = body.base.copy()
    img = face.paint_mouth(img, 'open')
    img = draw_music_notes(img, 5)
    return face.paint_eyes(img, 'closed')

@pose('whistling', 'Speech', 'Whistling — puckered mouth + notes')
def _(body, face):
    img = body.base.copy()
    img = face.paint_mouth(img, 'whistle')
    return draw_music_notes(img, 3)

@pose('listening', 'Speech', 'Listening attentively — head tilted')
def _(body, face):
    img = body.base.copy().rotate(5, Image.BICUBIC, expand=False, fillcolor=(0,0,0,0))
    return face.paint_eyes(img, 'looking_right')

# ── HAPPY / POSITIVE ──
@pose('happy_smile', 'Positive', 'Happy with big smile + blush')
def _(body, face):
    img = body.base.copy()
    img = face.paint_mouth(img, 'big_smile')
    img = face.add_blush(img, 0.7)
    return draw_sparkles(img, 4)

@pose('very_happy', 'Positive', 'Very happy — eyes squinted, huge smile')
def _(body, face):
    img = body.base.copy()
    img = face.paint_eyes(img, 'half')
    img = face.paint_mouth(img, 'big_smile')
    img = face.add_blush(img, 1.0)
    return draw_sparkles(img, 8)

@pose('excited_jump', 'Positive', 'Excited — jumping with fist pump!')
def _(body, face):
    img = compose_with_raised_arm(body, 'right', angle=140, arm_offset=(20, -50))
    # Shift body up for jump effect
    arr = np.array(img)
    shifted = np.zeros_like(arr)
    shift_y = 30
    shifted[:-shift_y] = arr[shift_y:]
    img = Image.fromarray(shifted)
    img = face.paint_mouth(img, 'wide_open')
    img = draw_sparkles(img, 6)
    img = draw_shadow(img)
    return draw_speech_bubble(img, "Yahoo!", (CANVAS_W//2+20, 5), 'large')

@pose('laughing', 'Positive', 'Laughing — eyes squinted, mouth wide')
def _(body, face):
    img = body.base.copy()
    img = face.paint_eyes(img, 'half')
    img = face.paint_mouth(img, 'wide_open')
    img = face.add_blush(img, 0.5)
    return draw_speech_bubble(img, "Ha ha ha!", (CANVAS_W//2+20, 20))

@pose('laughing_hard', 'Positive', 'Laughing so hard — body shaking')
def _(body, face):
    img = body.base.copy().rotate(3, Image.BICUBIC, expand=False, fillcolor=(0,0,0,0))
    img = face.paint_eyes(img, 'closed')
    img = face.paint_mouth(img, 'wide_open')
    img = face.add_blush(img, 0.8)
    return draw_speech_bubble(img, "WAHAHA!", (CANVAS_W//2+10, 15), 'large')

@pose('love', 'Positive', 'In love — heart eyes + floating hearts')
def _(body, face):
    img = body.base.copy()
    img = face.paint_eyes(img, 'heart')
    img = face.paint_mouth(img, 'smile')
    img = face.add_blush(img, 1.0)
    return draw_hearts(img, 6)

@pose('proud_fist', 'Positive', 'Proud — fist pump + determined face')
def _(body, face):
    img = compose_with_raised_arm(body, 'right', angle=100, arm_offset=(18, -30))
    img = face.paint_mouth(img, 'big_smile')
    return draw_sparkles(img, 3)

@pose('victorious', 'Positive', 'Victory pose — both arms up + sparkles')
def _(body, face):
    base = body.get_body_without_arm('right')
    body2 = MarioBody(base)
    base2 = body2.get_body_without_arm('left')
    r_arm, _, _ = body.extract_arm('right')
    l_arm, _, _ = body.extract_arm('left')
    if r_arm:
        r_rot = rotate_arm(r_arm, 140, (0.5, 0.0))
        if r_rot:
            sx, sy = body.get_shoulder_point('right')
            base2.paste(r_rot, (sx-r_rot.width//2+20, sy-55), r_rot)
    if l_arm:
        l_rot = rotate_arm(l_arm, -140, (0.5, 0.0))
        if l_rot:
            sx, sy = body.get_shoulder_point('left')
            base2.paste(l_rot, (sx-l_rot.width//2-20, sy-55), l_rot)
    base2 = face.paint_mouth(base2, 'wide_open')
    base2 = draw_sparkles(base2, 10, (30, 10, CANVAS_W-30, CANVAS_H//2))
    return draw_speech_bubble(base2, "WAHOO!!", (CANVAS_W//2-20, 5), 'large')

@pose('thumbs_up', 'Positive', 'Thumbs up — arm extended with fist')
def _(body, face):
    img = compose_with_raised_arm(body, 'right', angle=60, arm_offset=(15, -10))
    img = face.paint_mouth(img, 'smile')
    img = face.paint_eyes(img, 'wink_right')
    return img

# ── SAD / NEGATIVE ──
@pose('sad', 'Negative', 'Sad — droopy eyes, frown, muted colors')
def _(body, face):
    img = body.base.copy()
    img = face.paint_eyes(img, 'sad')
    img = face.paint_mouth(img, 'frown')
    return apply_color_tint(img, (100, 100, 150), 0.15)

@pose('very_sad', 'Negative', 'Very sad — tears streaming, blue tint')
def _(body, face):
    img = body.base.copy()
    img = face.paint_eyes(img, 'sad')
    img = face.paint_mouth(img, 'frown')
    img = face.add_tears(img, 3)
    return apply_color_tint(img, (80, 80, 160), 0.2)

@pose('crying', 'Negative', 'Crying — closed eyes, many tears, slumped')
def _(body, face):
    img = body.base.copy()
    img = face.paint_eyes(img, 'closed')
    img = face.paint_mouth(img, 'wide_open')
    img = face.add_tears(img, 4)
    img = apply_color_tint(img, (80, 80, 160), 0.15)
    return apply_brightness(img, 0.85)

@pose('angry', 'Negative', 'Angry — angry brows, gritted teeth, red tint')
def _(body, face):
    img = body.base.copy()
    img = face.paint_eyes(img, 'angry')
    img = face.paint_mouth(img, 'gritted')
    img = face.add_anger_veins(img, 2)
    return apply_color_tint(img, (200, 50, 50), 0.15)

@pose('furious', 'Negative', 'Furious — shaking, very red, veins everywhere')
def _(body, face):
    img = body.base.copy().rotate(2, Image.BICUBIC, expand=False, fillcolor=(0,0,0,0))
    img = face.paint_eyes(img, 'angry')
    img = face.paint_mouth(img, 'wide_open')
    img = face.add_anger_veins(img, 2)
    img = apply_color_tint(img, (220, 30, 30), 0.25)
    return draw_speech_bubble(img, "GRRRR!", (CANVAS_W//2+20, 15), 'large')

@pose('annoyed', 'Negative', 'Annoyed — half-closed eyes, slight frown')
def _(body, face):
    img = body.base.copy()
    img = face.paint_eyes(img, 'half')
    img = face.paint_mouth(img, 'frown')
    return img

@pose('disappointed', 'Negative', 'Disappointed — head down, sad eyes')
def _(body, face):
    img = body.base.copy().rotate(3, Image.BICUBIC, expand=False, fillcolor=(0,0,0,0))
    img = face.paint_eyes(img, 'sad')
    img = face.paint_mouth(img, 'frown')
    return apply_brightness(img, 0.9)

@pose('scared', 'Negative', 'Scared — wide eyes, shaking, blue tint')
def _(body, face):
    img = body.base.copy().rotate(-2, Image.BICUBIC, expand=False, fillcolor=(0,0,0,0))
    img = face.paint_eyes(img, 'wide')
    img = face.paint_mouth(img, 'wide_open')
    img = face.add_sweat_drop(img)
    img = apply_color_tint(img, (100, 100, 200), 0.15)
    return draw_exclamation(img, (CANVAS_W//2+50, 10))

@pose('nervous', 'Negative', 'Nervous — sweat drops, shifty eyes')
def _(body, face):
    img = body.base.copy()
    img = face.paint_eyes(img, 'looking_left')
    img = face.paint_mouth(img, 'smile')
    img = face.add_sweat_drop(img, 'right')
    return face.add_sweat_drop(img, 'left')

@pose('embarrassed', 'Negative', 'Embarrassed — blushing hard, eyes averted')
def _(body, face):
    img = body.base.copy()
    img = face.paint_eyes(img, 'looking_left')
    img = face.paint_mouth(img, 'frown')
    img = face.add_blush(img, 1.5)
    return apply_color_tint(img, (200, 100, 100), 0.1)

# ── THINKING / PROCESSING ──
@pose('thinking', 'Thinking', 'Thinking — eyes up, thought bubble')
def _(body, face):
    img = body.base.copy()
    img = face.paint_eyes(img, 'looking_up')
    return draw_thought_bubble(img, 'Hmm...', (CANVAS_W//2+20, 15))

@pose('thinking_deep', 'Thinking', 'Deep thinking — head tilted, multiple ?')
def _(body, face):
    img = body.base.copy().rotate(5, Image.BICUBIC, expand=False, fillcolor=(0,0,0,0))
    img = face.paint_eyes(img, 'looking_up')
    return draw_question_marks(img, 3, (CANVAS_W//2+30, 10))

@pose('confused', 'Thinking', 'Confused — tilted head, question mark')
def _(body, face):
    img = body.base.copy().rotate(-5, Image.BICUBIC, expand=False, fillcolor=(0,0,0,0))
    img = face.paint_eyes(img, 'looking_right')
    return draw_question_marks(img, 2)

@pose('curious', 'Thinking', 'Curious — wide eyes, leaning forward')
def _(body, face):
    img = body.base.copy().rotate(-3, Image.BICUBIC, expand=False, fillcolor=(0,0,0,0))
    img = face.paint_eyes(img, 'wide')
    return draw_question_marks(img, 1)

@pose('surprised', 'Thinking', 'Surprised — very wide eyes, open mouth')
def _(body, face):
    img = body.base.copy()
    img = face.paint_eyes(img, 'wide')
    img = face.paint_mouth(img, 'wide_open')
    return draw_exclamation(img)

@pose('shocked', 'Thinking', 'Shocked — extreme surprise, stepped back')
def _(body, face):
    # Shift body slightly right (stepped back)
    arr = np.array(body.base.copy())
    shifted = np.zeros_like(arr)
    shifted[:, 10:] = arr[:, :-10]
    img = Image.fromarray(shifted)
    img = face.paint_eyes(img, 'wide')
    img = face.paint_mouth(img, 'wide_open')
    img = face.add_sweat_drop(img)
    return draw_exclamation(img, (CANVAS_W//2+55, 8))

@pose('mischievous', 'Thinking', 'Mischievous — wink + sly grin')
def _(body, face):
    img = body.base.copy()
    img = face.paint_eyes(img, 'wink_right')
    img = face.paint_mouth(img, 'smile')
    return draw_speech_bubble(img, "Heh heh...", (CANVAS_W//2+30, 20), 'small')

@pose('determined', 'Thinking', 'Determined — fist up, focused eyes')
def _(body, face):
    img = compose_with_raised_arm(body, 'right', angle=90, arm_offset=(15, -25))
    img = face.paint_eyes(img, 'angry')
    img = face.paint_mouth(img, 'gritted')
    return draw_speech_bubble(img, "Let's-a go!", (CANVAS_W//2+10, 15))

@pose('processing', 'Thinking', 'Processing/loading — gear thought bubble')
def _(body, face):
    img = body.base.copy()
    img = face.paint_eyes(img, 'looking_up')
    return draw_thought_bubble(img, '...', (CANVAS_W//2+30, 15))

@pose('dizzy', 'Thinking', 'Dizzy — spiral eyes, wobbling')
def _(body, face):
    img = body.base.copy().rotate(5, Image.BICUBIC, expand=False, fillcolor=(0,0,0,0))
    img = face.paint_eyes(img, 'spiral')
    img = face.paint_mouth(img, 'tongue_out')
    return draw_sparkles(img, 3)

# ── SLEEP ──
@pose('sleepy', 'Sleep', 'Sleepy — half-closed eyes, dim, small Zzz')
def _(body, face):
    img = body.base.copy()
    img = face.paint_eyes(img, 'half')
    img = apply_brightness(img, 0.85)
    return draw_zzz(img, 2)

@pose('sleeping', 'Sleep', 'Fully asleep — eyes closed, tilted, big Zzz')
def _(body, face):
    img = body.base.copy().rotate(8, Image.BICUBIC, expand=False, fillcolor=(0,0,0,0))
    img = face.paint_eyes(img, 'closed')
    img = apply_brightness(img, 0.75)
    return draw_zzz(img, 3)

@pose('yawning', 'Sleep', 'Yawning — wide mouth, eyes closed')
def _(body, face):
    img = body.base.copy()
    img = face.paint_eyes(img, 'closed')
    img = face.paint_mouth(img, 'wide_open')
    return apply_brightness(img, 0.9)

# ── MOVEMENT ──
@pose('jumping', 'Movement', 'Jumping — raised up with shadow below')
def _(body, face):
    img = compose_with_raised_arm(body, 'right', angle=130, arm_offset=(20, -45))
    arr = np.array(img)
    shifted = np.zeros_like(arr)
    shifted[:-40] = arr[40:]
    img = Image.fromarray(shifted)
    img = face.paint_mouth(img, 'wide_open')
    img = draw_shadow(img, CANVAS_H-20)
    return draw_speech_bubble(img, "Yahoo!", (CANVAS_W//2+20, 5))

@pose('jumping_high', 'Movement', 'High jump — way up + motion lines')
def _(body, face):
    img = compose_with_raised_arm(body, 'right', angle=150, arm_offset=(22, -55))
    arr = np.array(img)
    shifted = np.zeros_like(arr)
    shifted[:-60] = arr[60:]
    img = Image.fromarray(shifted)
    img = face.paint_mouth(img, 'wide_open')
    img = draw_shadow(img, CANVAS_H-15, 50)
    return draw_motion_lines(img, 'up')

@pose('running', 'Movement', 'Running — leaning forward, motion lines')
def _(body, face):
    img = body.base.copy().rotate(-8, Image.BICUBIC, expand=False, fillcolor=(0,0,0,0))
    img = face.paint_mouth(img, 'open')
    return draw_motion_lines(img, 'horizontal')

@pose('dancing_1', 'Movement', 'Dancing pose 1 — tilted right + music')
def _(body, face):
    img = compose_with_raised_arm(body, 'right', angle=100, arm_offset=(18, -30))
    img = img.rotate(-8, Image.BICUBIC, expand=False, fillcolor=(0,0,0,0))
    img = face.paint_mouth(img, 'big_smile')
    img = face.paint_eyes(img, 'closed')
    return draw_music_notes(img, 5)

@pose('dancing_2', 'Movement', 'Dancing pose 2 — tilted left + music')
def _(body, face):
    img = compose_with_raised_arm(body, 'left', angle=100, arm_offset=(-18, -30))
    img = img.rotate(8, Image.BICUBIC, expand=False, fillcolor=(0,0,0,0))
    img = face.paint_mouth(img, 'big_smile')
    img = face.paint_eyes(img, 'half')
    return draw_music_notes(img, 5)

@pose('pointing_forward', 'Movement', 'Pointing forward — arm extended')
def _(body, face):
    img = compose_with_raised_arm(body, 'right', angle=50, arm_offset=(25, -5))
    img = face.paint_eyes(img, 'looking_right')
    return face.paint_mouth(img, 'smile')

@pose('pointing_up', 'Movement', 'Pointing up — arm aimed skyward')
def _(body, face):
    img = compose_with_raised_arm(body, 'right', angle=150, arm_offset=(20, -55))
    img = face.paint_eyes(img, 'looking_up')
    return face.paint_mouth(img, 'open')

@pose('flexing', 'Movement', 'Flexing — arm bent showing muscle')
def _(body, face):
    img = compose_with_raised_arm(body, 'right', angle=90, arm_offset=(15, -25))
    img = face.paint_mouth(img, 'big_smile')
    img = face.paint_eyes(img, 'wink_right')
    return draw_sparkles(img, 3)

@pose('crouching', 'Movement', 'Crouching — body squished down')
def _(body, face):
    img = body.base.copy()
    # Squash vertically
    arr = np.array(img)
    pil = Image.fromarray(arr)
    squashed = pil.resize((CANVAS_W, int(CANVAS_H * 0.7)), Image.LANCZOS)
    result = Image.new('RGBA', (CANVAS_W, CANVAS_H), (0,0,0,0))
    result.paste(squashed, (0, CANVAS_H - squashed.height), squashed)
    return result

# ── EATING ──
@pose('eating', 'Action', 'Eating a mushroom — nom nom!')
def _(body, face):
    img = body.base.copy()
    img = face.paint_eyes(img, 'closed')
    img = face.paint_mouth(img, 'open')
    # Draw small mushroom near mouth
    draw = ImageDraw.Draw(img)
    mx = body.face_x2 + 5
    my = body.face_cy + 10
    draw.ellipse([(mx, my-8), (mx+12, my+2)], fill=(255,50,50,255), outline=(0,0,0,200))
    draw.rectangle([(mx+3, my+2), (mx+9, my+8)], fill=(240,220,180,255), outline=(0,0,0,200))
    draw.ellipse([(mx+2, my-6), (mx+5, my-3)], fill=(255,255,255,200))
    return draw_speech_bubble(img, "Nom nom!", (CANVAS_W//2+30, 20), 'small')

# ── POWER-UPS ──
@pose('star_power', 'Power-Up', 'Star power — rainbow shimmer, invincible!')
def _(body, face):
    img = body.base.copy()
    # Rainbow color cycle
    arr = np.array(img).astype(float)
    alpha = arr[:,:,3]
    visible = alpha > 128
    hue_shift = np.random.randint(0, 360)
    from colorsys import hsv_to_rgb
    for y in range(arr.shape[0]):
        for x in range(arr.shape[1]):
            if visible[y, x]:
                h = ((y + x) * 3 + hue_shift) % 360 / 360.0
                rr, gg, bb = hsv_to_rgb(h, 0.3, 1.0)
                arr[y, x, 0] = min(255, arr[y, x, 0] * 0.6 + rr * 255 * 0.4)
                arr[y, x, 1] = min(255, arr[y, x, 1] * 0.6 + gg * 255 * 0.4)
                arr[y, x, 2] = min(255, arr[y, x, 2] * 0.6 + bb * 255 * 0.4)
    img = Image.fromarray(arr.astype(np.uint8))
    img = face.paint_mouth(img, 'big_smile')
    return draw_sparkles(img, 12, (20, 10, CANVAS_W-20, CANVAS_H-20))

@pose('fire_flower', 'Power-Up', 'Fire Mario — white/red color swap + fireballs')
def _(body, face):
    img = body.base.copy()
    arr = np.array(img)
    # Swap red -> white, blue -> red
    r, g, b, a = arr[:,:,0], arr[:,:,1], arr[:,:,2], arr[:,:,3]
    vis = a > 128
    red_px = vis & (r > 150) & (g < 80) & (b < 80)
    blue_px = vis & (b > 120) & (r < 100) & (g < 100)
    arr[red_px, 0] = 240
    arr[red_px, 1] = 240
    arr[red_px, 2] = 240
    arr[blue_px, 0] = 200
    arr[blue_px, 1] = 50
    arr[blue_px, 2] = 30
    img = Image.fromarray(arr)
    img = face.paint_mouth(img, 'smile')
    return draw_fire_particles(img, 6)

@pose('ice_mario', 'Power-Up', 'Ice Mario — blue/white color scheme + ice crystals')
def _(body, face):
    img = body.base.copy()
    arr = np.array(img)
    r, g, b, a = arr[:,:,0], arr[:,:,1], arr[:,:,2], arr[:,:,3]
    vis = a > 128
    red_px = vis & (r > 150) & (g < 80) & (b < 80)
    arr[red_px, 0] = 150
    arr[red_px, 1] = 200
    arr[red_px, 2] = 255
    img = Image.fromarray(arr)
    img = apply_color_tint(img, (180, 220, 255), 0.15)
    return draw_sparkles(img, 8, (30, 30, CANVAS_W-30, CANVAS_H-30))

@pose('mega_mushroom', 'Power-Up', 'Mega Mario — enlarged body, MEGA!')
def _(body, face):
    img = body.base.copy()
    # Scale up
    big = img.resize((int(CANVAS_W*1.3), int(CANVAS_H*1.3)), Image.LANCZOS)
    result = Image.new('RGBA', (CANVAS_W, CANVAS_H), (0,0,0,0))
    ox = (CANVAS_W - big.width) // 2
    oy = CANVAS_H - big.height
    result.paste(big, (ox, oy), big)
    return draw_speech_bubble(result, "MEGA!", (CANVAS_W//2+20, 5), 'large')

@pose('mini_mushroom', 'Power-Up', 'Mini Mario — tiny body, squeaky!')
def _(body, face):
    img = body.base.copy()
    small = img.resize((int(CANVAS_W*0.5), int(CANVAS_H*0.5)), Image.LANCZOS)
    result = Image.new('RGBA', (CANVAS_W, CANVAS_H), (0,0,0,0))
    ox = (CANVAS_W - small.width) // 2
    oy = CANVAS_H - small.height - 10
    result.paste(small, (ox, oy), small)
    return draw_speech_bubble(result, "So tiny!", (ox+small.width, oy), 'small')

@pose('metal_mario', 'Power-Up', 'Metal Mario — metallic silver sheen')
def _(body, face):
    img = body.base.copy()
    arr = np.array(img).astype(float)
    vis = arr[:,:,3] > 128
    gray = np.mean(arr[:,:,:3], axis=2, keepdims=True)
    arr[:,:,:3] = arr[:,:,:3] * 0.3 + gray * 0.5 + 40
    arr[:,:,:3] = np.clip(arr[:,:,:3], 0, 255)
    return Image.fromarray(arr.astype(np.uint8))

@pose('gold_mario', 'Power-Up', 'Gold Mario — golden shimmer')
def _(body, face):
    img = body.base.copy()
    arr = np.array(img).astype(float)
    vis = arr[:,:,3] > 128
    gold = np.array([255, 215, 0], dtype=float)
    arr[vis, :3] = arr[vis, :3] * 0.4 + gold * 0.6
    arr[:,:,:3] = np.clip(arr[:,:,:3], 0, 255)
    img = Image.fromarray(arr.astype(np.uint8))
    return draw_sparkles(img, 10, (30, 10, CANVAS_W-30, CANVAS_H-30))

# ── MISC ──
@pose('salute', 'Action', 'Saluting — hand at hat brim')
def _(body, face):
    img = compose_with_raised_arm(body, 'right', angle=130, arm_offset=(10, -50))
    img = face.paint_mouth(img, 'smile')
    return img

@pose('shrug', 'Action', 'Shrugging — arms out to sides')
def _(body, face):
    img = compose_with_raised_arm(body, 'right', angle=50, arm_offset=(20, -5))
    img = face.paint_mouth(img, 'frown')
    return draw_question_marks(img, 1)

@pose('facepalm', 'Action', 'Facepalm — hand on face, disappointed')
def _(body, face):
    img = compose_with_raised_arm(body, 'right', angle=120, arm_offset=(0, -45))
    img = face.paint_eyes(img, 'closed')
    return face.paint_mouth(img, 'frown')

@pose('dabbing', 'Action', 'Dabbing — the classic dab pose')
def _(body, face):
    img = compose_with_raised_arm(body, 'right', angle=140, arm_offset=(25, -55))
    img = img.rotate(-10, Image.BICUBIC, expand=False, fillcolor=(0,0,0,0))
    return face.paint_eyes(img, 'closed')


# ─── HTML Gallery ─────────────────────────────────────────────────────
def generate_gallery():
    categories = {}
    for name, cat, desc, _ in POSES:
        if cat not in categories:
            categories[cat] = []
        categories[cat].append((name, desc))

    cat_emojis = {
        'Neutral': '😐', 'Greeting': '👋', 'Speech': '💬', 'Positive': '😄',
        'Negative': '😢', 'Thinking': '🤔', 'Sleep': '💤', 'Movement': '🏃',
        'Action': '⚡', 'Power-Up': '⭐'
    }

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Mario Expressive Poses V2</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:#0a0e27; color:#e0e0e0; font-family:'Segoe UI',sans-serif; padding:20px; }}
h1 {{ text-align:center; color:#ff4757; font-size:2.2em; margin:20px 0 5px; }}
h1 span {{ font-size:1.2em; }}
.subtitle {{ text-align:center; color:#a0a0a0; margin-bottom:10px; }}
.count {{ text-align:center; color:#ff6b81; font-size:1.1em; margin-bottom:30px; }}
.category {{ margin:30px 0; }}
.cat-title {{ font-size:1.4em; color:#ff4757; padding:10px 20px; border-left:4px solid #ff4757;
  background:linear-gradient(90deg,rgba(255,71,87,0.1),transparent); margin-bottom:15px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:15px; padding:0 10px; }}
.card {{ background:linear-gradient(135deg,#1a1e3a,#15192e); border-radius:12px; overflow:hidden;
  border:1px solid #2a2e4a; transition:all 0.3s; cursor:pointer; }}
.card:hover {{ transform:translateY(-5px); border-color:#ff4757; box-shadow:0 8px 25px rgba(255,71,87,0.2); }}
.card img {{ width:100%; height:250px; object-fit:contain; background:#1a3a5c; padding:5px; }}
.card .info {{ padding:10px; }}
.card .name {{ color:#ff6b81; font-weight:bold; font-size:0.95em; }}
.card .desc {{ color:#808080; font-size:0.8em; margin-top:3px; }}
.modal {{ display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.9);
  z-index:100; justify-content:center; align-items:center; }}
.modal.active {{ display:flex; }}
.modal img {{ max-width:90%; max-height:90%; object-fit:contain; border-radius:8px; }}
.modal-close {{ position:fixed; top:20px; right:30px; color:white; font-size:30px; cursor:pointer; z-index:101; }}
</style></head><body>
<h1><span>🎭</span> Mario Expressive Poses V2</h1>
<p class="subtitle">ACTUAL body manipulation — arms move, faces change, poses are real!</p>
<p class="count">🍄 {len(POSES)} unique manipulated poses from NSMBU Deluxe Mario</p>
"""
    for cat, items in categories.items():
        emoji = cat_emojis.get(cat, '🎮')
        html += f'<div class="category"><h2 class="cat-title">{emoji} {cat}</h2><div class="grid">\n'
        for name, desc in items:
            html += f'''<div class="card" onclick="showModal('{name}.png')">
<img src="{name}.png" alt="{name}" loading="lazy">
<div class="info"><div class="name">{name}</div><div class="desc">{desc}</div></div></div>\n'''
        html += '</div></div>\n'

    html += """
<div class="modal" id="modal" onclick="this.classList.remove('active')">
<span class="modal-close" onclick="document.getElementById('modal').classList.remove('active')">&times;</span>
<img id="modal-img" src="">
</div>
<script>
function showModal(src) {
  document.getElementById('modal-img').src = src;
  document.getElementById('modal').classList.add('active');
}
document.addEventListener('keydown', e => {
  if(e.key==='Escape') document.getElementById('modal').classList.remove('active');
});
</script></body></html>"""
    return html


# ─── Main ─────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  MARIO EXPRESSIVE POSES V2 — ACTUAL BODY MANIPULATION!")
    print("=" * 60)

    os.makedirs(OUT_DIR, exist_ok=True)

    print("\nLoading and preparing base image...")
    base = prepare_base()
    body = MarioBody(base)
    face = FacePainter(body)

    print(f"  Body parts found:")
    print(f"    Face: y=[{body.face_y1}-{body.face_y2}], x=[{body.face_x1}-{body.face_x2}]")
    print(f"    Body center: x={body.body_cx}")
    print(f"    Overalls top: y={body.body_top}")

    success = 0
    fail = 0
    for name, cat, desc, func in POSES:
        try:
            print(f"  [{cat}] {name}...", end=' ')
            # Re-create body for each pose (clean state)
            body = MarioBody(base)
            face = FacePainter(body)
            result = func(body, face)
            if result is not None:
                result.save(os.path.join(OUT_DIR, f"{name}.png"))
                print("OK")
                success += 1
            else:
                print("SKIP (None)")
                fail += 1
        except Exception as e:
            print(f"FAIL: {e}")
            fail += 1

    # Gallery
    print("\nGenerating gallery...")
    html = generate_gallery()
    html_path = os.path.join(OUT_DIR, 'index.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  Gallery: {os.path.abspath(html_path)}")

    print(f"\n{'=' * 60}")
    print(f"  DONE! {success}/{success+fail} poses generated")
    if fail > 0:
        print(f"  ({fail} failed)")
    print(f"  Output: {os.path.abspath(OUT_DIR)}")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
