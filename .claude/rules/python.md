---
description: Python coding conventions
paths:
  - "**/*.py"
---

# Python Rules

- When using `.get()` for dictionaries, NEVER provide a default value. Always let it default to `None`.
- Use `uv` for dependency management, not raw pip.
- Camera server uses asyncio — all frame handling must be non-blocking.
- Use `base64.b64encode()` only once per frame in the capture loop, not per-client.
