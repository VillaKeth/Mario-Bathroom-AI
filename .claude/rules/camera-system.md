---
description: Rules for camera server, WebSocket streaming, and frame handling code
paths:
  - camera_server/**/*.py
  - communication_manager/**/*.ts
  - frontend/public/2d_view/**/*.ts
  - frontend/public/shared/websockets.ts
---

# Camera System Rules

1. Never re-encode frames — use pre-encoded JPEG from the camera capture loop
2. Rate limit broadcasts to 20 FPS max (50ms minimum interval)
3. Preserve existing depth data when updating RGB frames
4. Initialize `latestCameraFrame` when depth arrives before RGB
5. Check pending WebSocket messages before sending default subscriptions
6. Set up event listeners BEFORE subscribing to streams
7. YOLO overlay only renders when `cameraType === 'rgb'`
8. Restart YOLO polling when switching back to RGB camera
9. TCP camera connection is disabled — WebSocket handles all frames
10. After ANY camera/WebSocket changes, run ALL 8 tests from `docs/CAMERA_TESTING_PROTOCOL.md`
