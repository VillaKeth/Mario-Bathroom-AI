---
description: Check Doosan robot connection and state
---

Verify the Doosan M1013 robot connection:

1. **Check robot reachability** - Read `config.yaml` to get the robot hostname (`COMMUNICATION_MANAGER.ROBOT.HOSTNAME`) and ports (`COMMUNICATION_MANAGER.ROBOT.PERSISTENT.PORT` for persistent TCP, `COMMUNICATION_MANAGER.ROBOT.INTERMITTENT.PORT` for intermittent TCP connections)

2. **Check Communication Manager connection** - Read `config.yaml` to get the API hostname and port (`COMMUNICATION_MANAGER.API.HOSTNAME` and `COMMUNICATION_MANAGER.API.PORT`), then use the HTTP API:
   - `GET http://{HOSTNAME}:{PORT}/health` - Service health
   - `GET http://{HOSTNAME}:{PORT}/status` - Connection status

3. **Check robot state** - Use the WebSocket or API (same hostname/port from `config.yaml`):
   - `GET http://{HOSTNAME}:{PORT}/keypoints` - Current YOLO keypoints
   - Request robot state via WebSocket `request_robot_state` message

4. **Check state dictionary** - Reference `docs/STATE_DICTIONARY.md` for available state keys

Report:
- Robot reachable: YES/NO
- Connection status: CONNECTED/DISCONNECTED
- Last state update timestamp
- Any connection errors in Communication Manager logs
