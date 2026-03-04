---
description: Start all WellnessScape services
---

Start all WellnessScape services using the Makefile:

1. First run `make kill` to cleanly stop any existing app processes (this preserves MCP servers)
2. Then run `make dev` to start all services (Camera Server excluded — it runs on separate hardware)

If the user wants to include the Camera Server, use `npm start` instead of `make dev`.

Wait for all services to be ready, then verify by checking:
- Frontend accessible on port 50600
- Communication Manager API on port 50400
- LLM service health on port 50401

Report which services started successfully.
