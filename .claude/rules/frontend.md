---
description: Frontend UI conventions
paths:
  - frontend/**/*.ts
  - frontend/**/*.html
  - frontend/**/*.css
---

# Frontend Rules

- Frontend is served by Vite on port 50600.
- Use `requestStateKeys(['key1', 'key2'])` for specific robot state, not full `requestRobotState()`.
- Camera frames are rendered on `<canvas>`, not `<img>` (needed for overlay support).
- WebSocket connection is managed by shared `wsService` in `frontend/public/shared/websockets.ts`.
- After CSS/JS changes, hard refresh with Ctrl+Shift+R (Vite caches aggressively).
