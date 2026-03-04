---
description: Diagnose camera pipeline issues
---

Debug the camera pipeline by checking each stage of the frame flow:

**Frame Flow**: Camera Server → Communication Manager (WebSocket) → Frontend (WebSocket) → Canvas

Steps:
1. **Check Camera Server** - Is it running? Check port 50201 WebSocket
2. **Check Communication Manager** - Is it receiving frames? Look for frame-related logs
3. **Check Frontend WebSocket** - Use Chrome DevTools to evaluate `wsService.isConnected()` on the 2d_view page
4. **Check Browser Console** - Look for WebSocket errors, frame errors, or connection issues
5. **Check FPS** - Look for FPS counters or timing logs in console

Common issues to check:
- TCP connection competing with WebSocket (should be disabled)
- Frame re-encoding (should use pre-encoded JPEG)
- Missing rate limiting on broadcasts (should be 20 FPS max)
- Depth data being wiped by RGB updates
- Event listeners set up after subscription (race condition)

Use Chrome DevTools MCP tools to inspect the browser state.
Report findings with specific file locations and line numbers for any issues found.
