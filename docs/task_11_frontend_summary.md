# Task 11: Frontend — CSS Theme & Wizard Shell

## Status: ✅ DONE

## What Was Implemented

### 1. Dark Theme CSS (`character_creator/static/styles.css`)

Created a comprehensive, production-ready dark theme with **~900 lines of CSS** including:

#### Core Design System
- **CSS Custom Properties**: All colors, spacing, transitions as variables
- **Dark Navy Palette**: `#0d0d1a` background, `#1a1a2e` cards, `#2a2a3e` inputs
- **Accent Colors**: Purple (#7B2FBE), Blue (#1E90FF), Red (#E52521), Green (#00A86B), Gold (#FFD700)
- **Typography**: System font stack, responsive heading sizes, 1.6 line-height

#### UI Components Styled
- **Progress Bar**: 6-segment horizontal progress indicator with active/completed states
- **Form Elements**: Dark inputs with purple focus rings, visible focus outlines
- **Buttons**: Primary (purple), secondary (outline), danger (red), success (green), with hover/active states
- **Cards**: Subtle borders, hover effects, consistent padding
- **Radio/Checkbox Cards**: Interactive selection cards with visual feedback
- **Tag Input**: Pill-style tags with add/remove functionality
- **Color Pickers**: 4-color grid for theme customization
- **Sliders**: Custom thumb/track styling for voice tuning
- **Upload Zone**: Dashed border with drag-over highlight state
- **Sprite Grid**: Responsive grid for image thumbnails (120px min)
- **Progress Bars**: Horizontal bars with gradient fill
- **Toast Notifications**: Fixed position, color-coded (success/error/warning/info)
- **Modal Overlay**: Backdrop + centered modal with slide-in animation
- **Loading Spinner**: Animated spinner with size variants

#### Accessibility Features
- `.sr-only` class for screen-reader-only content
- Skip link (visible on focus)
- `:focus-visible` rings on all interactive elements (2px purple outline)
- ARIA-friendly markup support
- High contrast mode support
- Reduced motion support (`prefers-reduced-motion`)

#### Responsive Design
- **Mobile breakpoints**: 768px, 480px
- **Tablet**: Single-column grids, stacked navigation
- **Mobile**: Condensed progress bar (hide labels), simplified layouts
- **Toast**: Full-width on small screens

#### Animations & Transitions
- Fade-in on step transitions (250ms)
- Slide-in on modals (300ms)
- Hover lift on cards (-2px translateY)
- Smooth color transitions (150ms)
- Spinner rotation animation

---

### 2. Wizard HTML Shell (`character_creator/static/index.html`)

Replaced minimal placeholder with **full 6-step wizard app shell** (~550 lines of HTML):

#### Structure
- Skip link for keyboard navigation
- Resume draft banner (hidden by default)
- Wizard header with title + subtitle
- 6-segment progress bar with step labels
- Status/error message region (ARIA live)
- 6 wizard steps (sections with `role="tabpanel"`)
- Success screen
- Navigation buttons (Back/Next)
- Toast container

#### Step 1: Identity
- Character type radio cards (Known vs Original)
- Character name input with auto-fill detection
- Display name, tagline, description fields
- 4-color theme picker (primary, secondary, accent, text)
- Auto-filled badges (✨ visual indicator when fields are populated by auto-fill)

#### Step 2: Personality
- Skip checkbox for known characters
- System prompt textarea (6 rows)
- Tag inputs for accent markers and catchphrases
- Help text explaining each field

#### Step 3: Voice
- Voice engines card (grid of available engines)
- Reference audio upload zone (drag & drop)
- Audio preview player
- Record button + Auto-find online button
- Edge TTS fallback selector (voice + gender filter)
- Speed/pitch sliders with live value display
- Pronunciation rules editor (add/remove rows)

#### Step 4: Appearance
- Sprite source radio cards (AI Generate vs Upload)
- Visual description textarea with auto-fill badge
- Art style picker (5 buttons: 3D Figurine, Anime, Pixel Art, Realistic, Cartoon)
- Generate sprites button + progress bar
- Upload grids for emotion/state sprites (populated by JS)

#### Step 5: Hardware & Models
- Hardware detection card (shows GPU, VRAM, etc.)
- Model selection grid (shows compatibility)
- No-Ollama warning banner
- Advanced toggle for dual model selection (quality vs fast)

#### Step 6: Review & Create
- Review cards (populated by JS)
- Create character button + progress bar
- Success screen with "Start Server" and "Create Another" buttons

#### Accessibility Enhancements
- Semantic HTML5 (`<nav>`, `<main>`, `<section>`, `<fieldset>`)
- ARIA roles (`progressbar`, `tabpanel`, `alert`, `status`)
- ARIA labels on all interactive elements
- ARIA live regions for dynamic content
- `tabindex="-1"` on step headings for focus management
- `<legend class="sr-only">` for fieldsets
- `aria-labelledby` linking steps to headings
- Required field indicators (`<span class="required">*</span>`)

---

## Files Modified
- ✅ `character_creator/static/styles.css` (0 → ~900 lines)
- ✅ `character_creator/static/index.html` (15 → ~550 lines)

## Commit
```
commit 103293c
feat: dark theme CSS and accessible wizard HTML shell

- Complete dark navy theme with purple/blue accents
- CSS custom properties for all colors and spacing
- Progress bar, forms, buttons, cards, modals, toasts
- Full 6-step wizard HTML with ARIA attributes
- Skip links, focus management, screen-reader support
- Responsive design (mobile/tablet breakpoints)
- Reduced motion and high contrast support
```

## Next Steps (Not Part of This Task)
- Task 12: JavaScript wizard controller (`wizard.js`)
- Task 13: Backend endpoints (auto-fill, voice engines, hardware detection, etc.)
- Task 14: Sprite generation orchestration
- Task 15: Character creation + file generation

---

## Notes
- **Did NOT verify in browser** (as instructed — browser testing will come with Task 12 when JS is wired)
- HTML/CSS are **syntactically correct** and complete
- All IDs/classes referenced in HTML have corresponding CSS rules
- Ready for JavaScript wiring and API integration
