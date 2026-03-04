---
description: Check which WellnessScape services are running
---

Check the status of all WellnessScape services by testing their ports:

1. **Camera Server** - WebSocket on port 50201, TCP on port 50100
2. **Communication Manager** - HTTP API on port 50400, WebSocket on port 50201
3. **Frontend (Vite)** - HTTP on port 50600
4. **LLM/Inference** - HTTP API on port 50401
5. **Robot (Doosan)** - TCP on ports defined in `config.yaml` under `COMMUNICATION_MANAGER.ROBOT.PERSISTENT.PORT` and `COMMUNICATION_MANAGER.ROBOT.INTERMITTENT.PORT` at the hostname in `COMMUNICATION_MANAGER.ROBOT.HOSTNAME`

Run `netstat -an | findstr "50100 50201 50400 50401 50600 8060"` to check listening ports.

Also check for running processes:
- `Get-Process -Name python -ErrorAction SilentlyContinue` for Camera Server and LLM
- `Get-Process -Name node -ErrorAction SilentlyContinue` for Communication Manager and Frontend

Report a clear table showing each service, its expected port, and whether it's UP or DOWN.
If any service is down, suggest the command to start it.
