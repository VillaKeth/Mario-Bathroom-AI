# WellnessScape

## Project Overview

WellnessScape is a robotics wellness/massage system with a microservices architecture. It controls a Doosan robot arm with an Intel RealSense camera, using computer vision (YOLO pose detection) to perform automated massage workflows. The system runs on a local network (10.10.10.x subnet).

## Tech Stack

- **Frontend**: TypeScript + Vite (port 50600)
- **Communication Manager**: Node.js + TypeScript (port 50400 HTTP, 50201 WebSocket)
- **Camera Server**: Python + OpenCV + RealSense SDK (port 50201 WS, 50100 TCP)
- **LLM/Inference**: Python + Ultralytics YOLO + FastAPI (port 50401)
- **Data Manager**: Python + Qdrant vector DB
- **Robot**: Doosan (hostname and ports defined in `config.yaml` under `COMMUNICATION_MANAGER.ROBOT`)
- **Config**: YAML-based (`config.yaml` at project root)

## Common Commands

```bash
make dev          # Start all services (except camera server)
make kill         # Kill app processes (preserves MCP servers)
make install      # Set up Python venv with uv
npm start         # Start all services including camera server
```

## Project Structure

```
camera_server/       # Python - RealSense camera capture & streaming
communication_manager/  # Node.js - Robot comms, WebSocket hub, API server
frontend/            # Vite + TypeScript - Browser UI (2D view, massage UI, state display)
llm/                 # Python - YOLO inference, pose detection, segmentation
data_manager/        # Python - Qdrant vector DB integration
docs/                # Architecture docs, testing protocols, fix logs
shell/               # Utility scripts (kill ports, chrome helpers)
prompts/             # LLM prompt templates
config.yaml          # Central configuration for all services
```

## Key Conventions

- **Async/await only** in TypeScript — no `.then()` or callbacks
- **Python dicts**: Use `.get()` without default values (let it return `None`)
- **Camera frames** flow: Camera Server → Comm Manager (WebSocket) → Frontend (WebSocket)
- **Robot commands** use TCP sockets with format: `COMMAND commandId args~`
- **State queries**: Use `requestStateKeys(['key1', 'key2'])` for specific keys, not full state polls
- **WebSocket messages**: All defined in `config.yaml` under INCOMING/OUTGOING_MESSAGES

## Critical Rules

1. **Never re-encode camera frames** — use pre-encoded JPEG from camera server
2. **Rate limit frame broadcasts** to 20 FPS max (browser can't keep up with 90 FPS)
3. **TCP camera connection is disabled** — WebSocket handles all frames
4. **YOLO overlay only on RGB camera**, never on depth
5. **Set up event listeners BEFORE subscribing** to WebSocket streams
6. **Preserve depth data** when updating RGB frames (they arrive independently)
7. **`make kill` is port-based** — it kills specific app ports, not all node.exe

## Testing

- Camera system: Follow `docs/CAMERA_TESTING_PROTOCOL.md` (8 test cases)
- Run `make dev` to start, hard refresh browser with Ctrl+Shift+R after changes
- All camera/WebSocket changes require full 8-test protocol

## Network Layout

All hostnames and ports are defined in `config.yaml`. **Never hard-code IP addresses or ports — always reference `config.yaml`.**

| Service              | Config Path                                    |
|---------------------|------------------------------------------------|
| Camera Server WS    | `CAMERA_SERVER.WEBSOCKET.HOSTNAME / PORT`      |
| Comm Manager HTTP   | `COMMUNICATION_MANAGER.API.HOSTNAME / PORT`    |
| Comm Manager WS     | `COMMUNICATION_MANAGER.WEBSOCKET.HOSTNAME / PORT` |
| Frontend (Vite)     | `FRONTEND.HOSTNAME / PORT`                     |
| LLM API             | `LLM.API.HOSTNAME / PORT`                      |
| Robot (Doosan)      | `COMMUNICATION_MANAGER.ROBOT.HOSTNAME / PORT`  |

## Documentation

- Architecture: `docs/ARCHITECTURE.md`
- Camera rules: `.github/instructions/camera-system.instructions.md`
- Robot commands: `docs/ROBOT_COMMANDS.md`
- State dictionary: `docs/STATE_DICTIONARY.md`
