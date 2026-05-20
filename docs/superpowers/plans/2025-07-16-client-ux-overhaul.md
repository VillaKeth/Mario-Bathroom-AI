# Client UX Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the Mario AI pygame client from amateurish prototype to polished party-ready experience — better speech bubbles, distinct thinking animation, prominent emotion display, fixed fullscreen, and cleaner layout.

**Architecture:** All changes are in `client/mario_display.py` (the rendering engine). The rendering pipeline draws at 800×600 then scales to fullscreen via render buffer. We improve each visual layer without changing the data flow from server. No new files needed — this is purely visual polish on existing render methods.

**Tech Stack:** Python 3.11, pygame 2.x, math/random stdlib

---

### Task 1: Fix Fullscreen Scaling Bug

**Problem:** Fullscreen mode uses `pygame.FULLSCREEN | pygame.SCALED` which fights with the manual render-buffer scaling (lines 1419-1428). The `SCALED` flag tells pygame to auto-scale, but then the code ALSO does manual `smoothscale` + centered blitting, causing double-scaling artifacts, wrong positioning, and visual breakage.

**Files:**
- Modify: `client/mario_display.py:1041-1085` (_toggle_fullscreen)
- Modify: `client/mario_display.py:1419-1428` (fullscreen blit in _draw)

- [ ] **Step 1: Fix fullscreen mode flag**

Remove `pygame.SCALED` from the fullscreen mode. The manual render-buffer approach is correct (draw at 800×600, scale up), but `SCALED` double-scales everything.

```python
# In _toggle_fullscreen, line 1050-1051, change:
self._screen = pygame.display.set_mode(
    (info.current_w, info.current_h), pygame.FULLSCREEN | pygame.SCALED
)
# To:
self._screen = pygame.display.set_mode(
    (info.current_w, info.current_h), pygame.FULLSCREEN
)
```

- [ ] **Step 2: Ensure render buffer is always used in fullscreen**

The current code in `_draw()` at line 1296-1297 redirects `self._screen` to the render buffer, then at 1420-1428 scales and blits back. Verify this works without `SCALED` flag. The key is that `_native_width` and `_native_height` must match the actual display size.

- [ ] **Step 3: Test by launching client and pressing F11**

Run client, press F11, verify:
- No stretching/distortion
- Speech bubbles render correctly
- Mario sprite centered
- All overlays (banner, status bar) visible

- [ ] **Step 4: Commit**

```bash
git add client/mario_display.py
git commit -m "fix: fullscreen scaling - remove SCALED flag that conflicts with manual render buffer"
```

---

### Task 2: Redesign Speech Bubbles

**Problem:** Current bubbles are flat white rectangles with black borders. They look like a Windows 95 tooltip. Need: drop shadow, subtle gradient, better shape, more personality.

**Files:**
- Modify: `client/mario_display.py:1843-1967` (_draw_speech_bubble)

- [ ] **Step 1: Add drop shadow to speech bubble**

Before drawing the main bubble rect, draw a slightly offset dark semi-transparent rect:

```python
# Shadow (draw before main bubble)
shadow_offset = 4
shadow_surf = pygame.Surface((bubble_w + shadow_offset, bubble_h + shadow_offset), pygame.SRCALPHA)
shadow_surf.fill((0, 0, 0, 60))
self._screen.blit(shadow_surf, (bubble_x + shadow_offset // 2, bubble_y + shadow_offset // 2))
```

- [ ] **Step 2: Improve bubble colors with subtle gradients**

Replace flat white with a warm off-white. Add emotion-tinted backgrounds:
- Normal: warm white (255, 252, 245) with dark gray border (60, 60, 60)
- Question: soft blue (230, 240, 255) with blue border (80, 120, 200)
- Whisper: light gray (240, 240, 240) with soft border (180, 180, 180)
- Shout: warm yellow (255, 250, 220) with red border (200, 50, 50)

- [ ] **Step 3: Add rounded pointer triangle with anti-aliasing**

Replace the flat triangle pointer with a smoother curved connector using `pygame.gfxdraw` (aalines) or manual smoothing.

- [ ] **Step 4: Better font selection**

Switch from `pygame.font.Font(None, size)` (which uses a default monospace-like font) to a friendlier font. Try "Segoe UI", "Calibri", or "Comic Sans MS" (fits Mario's personality).

Update `init()` line 408-411:
```python
bubble_font_name = None  # Will try system fonts
for font_name in ["segoeuiemoji", "segoeui", "calibri", "comicsansms", "arial"]:
    if pygame.font.match_font(font_name):
        bubble_font_name = pygame.font.match_font(font_name)
        break
self._bubble_fonts = {
    size: pygame.font.Font(bubble_font_name, size)
    for size in range(14, 30, 2)
}
```

- [ ] **Step 5: Add subtle breathing animation to bubble**

The bubble should have a very subtle scale pulse while typewriter is active (expanding slightly as text fills in), using a sine wave that's barely perceptible.

- [ ] **Step 6: Test and commit**

```bash
git add client/mario_display.py
git commit -m "feat: redesign speech bubbles with shadows, better colors, and smoother styling"
```

---

### Task 3: Distinct Thinking/Waiting Animation

**Problem:** Thinking shows "Hmm..." in the same speech bubble as regular speech. Users can't tell Mario is processing vs. speaking. Need a visually distinct loading indicator.

**Files:**
- Modify: `client/mario_display.py:1326-1330` (thinking draw in _draw)
- Add new method: `_draw_thinking_indicator`

- [ ] **Step 1: Create dedicated thinking indicator method**

Replace the `_draw_speech_bubble("Hmm...")` with a dedicated visual — three bouncing dots (like iMessage typing indicator) in a small pill-shaped container:

```python
def _draw_thinking_indicator(self):
    """Draw bouncing dots indicator (like iMessage typing) while waiting for response."""
    self._thinking_dots = (self._thinking_dots + 1) % 60
    
    # Pill-shaped container
    pill_w, pill_h = 80, 40
    pill_x = WINDOW_WIDTH // 2 - pill_w // 2
    pill_y = getattr(self, '_banner_bottom', 48) + 12
    
    # Shadow
    shadow = pygame.Surface((pill_w + 4, pill_h + 4), pygame.SRCALPHA)
    shadow.fill((0, 0, 0, 40))
    self._screen.blit(shadow, (pill_x + 2, pill_y + 2))
    
    # Pill background
    pygame.draw.rect(self._screen, (50, 50, 70), (pill_x, pill_y, pill_w, pill_h), border_radius=20)
    pygame.draw.rect(self._screen, (80, 80, 110), (pill_x, pill_y, pill_w, pill_h), 2, border_radius=20)
    
    # Three bouncing dots with staggered timing
    for i in range(3):
        phase = (self._thinking_dots + i * 10) % 60
        bounce = math.sin(phase * math.pi / 30) * 6 if phase < 30 else 0
        dot_x = pill_x + 22 + i * 18
        dot_y = pill_y + pill_h // 2 - int(bounce)
        dot_size = 5
        # Brighter when bouncing
        brightness = 200 + int(55 * max(0, bounce / 6))
        color = (brightness, brightness, brightness)
        pygame.draw.circle(self._screen, color, (dot_x, dot_y), dot_size)
```

- [ ] **Step 2: Replace thinking section in _draw()**

At lines 1326-1330, replace:
```python
elif self._thinking:
    self._thinking_dots = (self._thinking_dots + 1) % 90
    dots = "." * ((self._thinking_dots // 15) % 4)
    self._draw_speech_bubble(f"Hmm{dots}")
```
With:
```python
elif self._thinking:
    self._draw_thinking_indicator()
```

- [ ] **Step 3: Add "Processing..." subtitle while thinking**

When thinking starts, also show a subtle subtitle so user knows Mario heard them:

In `client/main.py`, around line 201, after `self.display.set_thinking(True)`:
```python
self.display.subtitle_text = "Processing..."
self.display._subtitle_set_frame = self.display._frame
```

- [ ] **Step 4: Test and commit**

```bash
git add client/mario_display.py client/main.py
git commit -m "feat: add bouncing dots thinking indicator (replaces 'Hmm...' bubble)"
```

---

### Task 4: Prominent Emotion Display

**Problem:** Emotion is a tiny "Mood: happy" text buried in the info strip. Users don't notice it. Need Mario's current emotion to be visually prominent.

**Files:**
- Modify: `client/mario_display.py` — new method `_draw_emotion_badge`
- Modify: `client/mario_display.py:1286-1340` (_draw method, add emotion badge draw call)
- Modify: `client/mario_display.py:1478-1483` (remove mood from info strip)

- [ ] **Step 1: Create emotion badge with emoji + label**

Draw a floating badge near Mario's head showing the current emotion with an emoji and colored background:

```python
EMOTION_EMOJI = {
    "happy": "😊", "excited": "🤩", "surprised": "😲", "confused": "🤔",
    "annoyed": "😤", "sleepy": "😴", "mischievous": "😏", "laughing": "😂",
    "sad": "😢", "angry": "😡", "loving": "💕", "love": "💕",
    "proud": "😤", "frustrated": "😠", "embarrassed": "😳", "worried": "😟",
    "bored": "😐", "determined": "💪", "nervous": "😰", "scared": "😨",
}

EMOTION_BADGE_COLORS = {
    "happy": (255, 220, 50), "excited": (255, 180, 0), "surprised": (200, 100, 255),
    "confused": (150, 150, 255), "annoyed": (255, 120, 50), "sleepy": (120, 120, 200),
    "mischievous": (50, 220, 100), "laughing": (255, 230, 50), "sad": (100, 150, 255),
    "angry": (255, 50, 50), "loving": (255, 100, 150), "love": (255, 80, 130),
    "proud": (255, 200, 0), "frustrated": (255, 80, 30), "embarrassed": (255, 170, 200),
    "worried": (180, 180, 255), "bored": (160, 160, 160), "determined": (255, 165, 0),
    "nervous": (200, 200, 255), "scared": (180, 180, 255),
}

def _draw_emotion_badge(self):
    """Draw a floating emotion badge near Mario showing current mood."""
    if not self._emotion:
        return
    
    emoji = EMOTION_EMOJI.get(self._emotion, "😐")
    color = EMOTION_BADGE_COLORS.get(self._emotion, (200, 200, 200))
    
    # Position: to the right of Mario, floating
    badge_x = WINDOW_WIDTH // 2 + 130
    badge_y = WINDOW_HEIGHT // 2 - 60
    
    # Gentle float animation
    float_offset = math.sin(time.time() * 2) * 4
    badge_y += int(float_offset)
    
    # Badge background (rounded pill)
    font = self._bubble_fonts.get(18, self._font_small)
    label = f" {self._emotion.capitalize()}"
    emoji_font = self._bubble_fonts.get(20, self._font)
    
    emoji_surf = emoji_font.render(emoji, True, (255, 255, 255))
    label_surf = font.render(label, True, (40, 40, 40))
    
    badge_w = emoji_surf.get_width() + label_surf.get_width() + 16
    badge_h = max(emoji_surf.get_height(), label_surf.get_height()) + 10
    
    # Shadow
    shadow = pygame.Surface((badge_w + 4, badge_h + 4), pygame.SRCALPHA)
    shadow.fill((0, 0, 0, 50))
    self._screen.blit(shadow, (badge_x + 2, badge_y + 2))
    
    # Background with emotion color
    bg_r, bg_g, bg_b = color
    pygame.draw.rect(self._screen, (bg_r, bg_g, bg_b),
                     (badge_x, badge_y, badge_w, badge_h), border_radius=badge_h // 2)
    pygame.draw.rect(self._screen, (min(255, bg_r + 30), min(255, bg_g + 30), min(255, bg_b + 30)),
                     (badge_x, badge_y, badge_w, badge_h), 2, border_radius=badge_h // 2)
    
    # Emoji + label
    self._screen.blit(emoji_surf, (badge_x + 8, badge_y + (badge_h - emoji_surf.get_height()) // 2))
    self._screen.blit(label_surf, (badge_x + 8 + emoji_surf.get_width(), badge_y + (badge_h - label_surf.get_height()) // 2))
```

- [ ] **Step 2: Add emotion badge to _draw() pipeline**

After `_draw_emotion_flash()` (line 1312), add:
```python
self._draw_emotion_badge()
```

- [ ] **Step 3: Remove "Mood:" from info strip**

In `_draw_party_banner`, remove the mood text from the info strip (lines 1478-1484) since it's now shown prominently via the badge.

- [ ] **Step 4: Add emotion transition animation**

When emotion changes, the badge should have a brief scale-up/pop animation:
- Track `_emotion_badge_scale` in `set_emotion()`
- In `_draw_emotion_badge()`, scale badge by `_emotion_badge_scale` (starts at 1.3, decays to 1.0 over 0.3s)

- [ ] **Step 5: Test and commit**

```bash
git add client/mario_display.py
git commit -m "feat: add floating emotion badge with emoji and pop animation"
```

---

### Task 5: Clean Up Bottom Status Bar

**Problem:** Bottom of screen has duplicate connection status (once in banner, once in status bar), cluttered hint text, and the `[IDLE]` state label that looks debug-y.

**Files:**
- Modify: `client/mario_display.py:1340-1361` (status indicators and hint in _draw)

- [ ] **Step 1: Replace debug-style status bar with clean minimal bar**

Replace the current status indicators block (lines 1343-1356) with a cleaner, less intrusive version:

```python
# Minimal bottom bar — just essential info, no debug labels
bottom_bar = pygame.Surface((WINDOW_WIDTH, 24), pygame.SRCALPHA)
bottom_bar.fill((0, 0, 0, 100))
self._screen.blit(bottom_bar, (0, WINDOW_HEIGHT - 24))

# Connection dot (left)
conn_color = (50, 200, 50) if self.connected else (200, 50, 50)
pygame.draw.circle(self._screen, conn_color, (12, WINDOW_HEIGHT - 12), 4)

# Hint text (right, smaller and dimmer)
hint = "TAB:type | 1-8:games | F11:fullscreen"
hint_surf = self._font_small.render(hint, True, (80, 80, 100))
self._screen.blit(hint_surf, (WINDOW_WIDTH - hint_surf.get_width() - 8, WINDOW_HEIGHT - 20))
```

- [ ] **Step 2: Remove redundant `[STATE]` display**

The `[IDLE]`, `[TALKING]`, etc. labels are debug info — remove them from the visible UI. The user can tell Mario's state from his sprite and speech bubble.

- [ ] **Step 3: Test and commit**

```bash
git add client/mario_display.py
git commit -m "feat: clean up bottom status bar - remove debug labels, minimal design"
```

---

### Task 6: Integration Test & Polish

**Files:**
- Modify: `client/mario_display.py` (any final tweaks)

- [ ] **Step 1: Launch server + client, verify all changes work together**

Start server and client. Test:
1. Speech bubble appears with shadow and better styling
2. Thinking shows bouncing dots (not "Hmm...")  
3. Emotion badge floats next to Mario
4. Emotion badge pops when emotion changes
5. Fullscreen (F11) works without distortion
6. Bottom bar is clean, no `[IDLE]` debug text
7. All existing features still work (events, keyboard input, party mode)

- [ ] **Step 2: Fix any visual overlap issues**

Ensure speech bubble doesn't overlap with emotion badge. Ensure thinking dots don't fight with subtitle. Adjust positions if needed.

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "polish: final UX overhaul tweaks and visual cleanup"
```

---

## Summary of Changes

| Component | Before | After |
|-----------|--------|-------|
| Speech bubbles | Flat white rect, black border | Drop shadow, warm colors, better font, personality |
| Thinking state | "Hmm..." in speech bubble | Bouncing dots pill (iMessage-style) |
| Emotion display | Tiny "Mood: happy" in HUD | Floating emoji badge near Mario with pop animation |
| Fullscreen | Broken (double-scaling) | Fixed (removed conflicting SCALED flag) |
| Bottom bar | `[IDLE]` debug text, cluttered | Minimal — connection dot + hints only |
