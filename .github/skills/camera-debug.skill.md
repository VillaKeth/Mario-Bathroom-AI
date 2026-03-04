---
name: camera-debug
description: Debug camera pipeline and fix common issues
prompt: |
  Debug the camera pipeline in WellnessSpace by following these steps:
  
  1. **Check all services are running**:
     - Camera Server (10.10.11.56:8888)
     - Communication Manager (10.10.10.248:50201)
     - Unified Camera (localhost:8891)
     - LLM Service (localhost:7860 or configured port)
     - Frontend (localhost:50600)
  
  2. **Verify connections**:
     ```powershell
     netstat -an | findstr "8888 8891 50200 50201 50600"
     ```
  
  3. **Check frame flow**:
     - Camera Server receiving frames from RealSense
     - Communication Manager receiving from Camera Server
     - LLM receiving frames (check /health endpoint)
     - Frontend displaying frames (check console)
  
  4. **Common fixes**:
     - Restart services in order: Camera → Communication → LLM → Frontend
     - Check config.yaml ports match actual services
     - Verify WebSocket URLs in frontend
     - Check BGR/RGB color handling
     - Verify rotation applied correctly
  
  5. **Check logs**:
     - Camera Server debug output
     - Communication Manager console
     - LLM FastAPI logs
     - Browser console errors
  
  Return diagnostic report with:
  - Service status (running/stopped)
  - Connection status (connected/disconnected)
  - Frame rate at each stage
  - Any errors found
  - Recommended fixes
tools:
  - powershell
  - view
  - grep
---
