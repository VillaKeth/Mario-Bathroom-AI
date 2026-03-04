---
description: Run all 8 camera test cases from the testing protocol
---

Run the camera system test protocol. First read `docs/CAMERA_TESTING_PROTOCOL.md` to get the full test procedure.

The 8 tests cover:
1. RGB camera stream displays and FPS is acceptable (target: 15+ FPS)
2. Depth camera stream displays correctly
3. Camera switching (RGB → Depth → RGB) works without breaking
4. YOLO overlay shows on RGB only
5. YOLO overlay hides on depth camera
6. YOLO restarts when switching back to RGB
7. Depth data preserved when RGB frames update
8. Frame rate limiting works (no browser overload)

Use Chrome DevTools MCP tools to:
- Navigate to the 2d_view page (use FRONTEND.HOSTNAME and FRONTEND.PORT from `config.yaml` to build the URL: `http://{FRONTEND.HOSTNAME}:{FRONTEND.PORT}/2d_view/index.html`)
- Check console for errors
- Verify camera feed is rendering
- Test camera switching via UI controls
- Check YOLO overlay toggle

Report results as a checklist with PASS/FAIL for each test.
