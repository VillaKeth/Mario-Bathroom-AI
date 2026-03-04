---
description: Show config.yaml settings for a specific service
---

Read `config.yaml` and display the configuration for the requested service: $ARGUMENTS

If no service is specified, show a summary of all services with their key settings (hostname, port).

Available service sections:
- **CAMERA_SERVER** - Camera capture settings, ports, resolution
- **COMMUNICATION_MANAGER** - API endpoints, robot connection, WebSocket messages
- **FRONTEND** - Serve settings, WebSocket message definitions
- **LLM** - Inference API, YOLO model selection, Gradio settings
- **POSE_DETECTION** - Detection source, browser settings, confidence thresholds
- **ANATOMICAL_REGIONS** - Region toggle, active regions, overlay settings
- **AUTO_QUAD** - Automatic QUAD sending settings
- **ROBOT_STATE** - State polling interval

For each setting, briefly explain what it controls and what valid values look like.
