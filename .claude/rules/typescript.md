---
description: TypeScript coding conventions
paths:
  - "**/*.ts"
  - "**/*.tsx"
---

# TypeScript Rules

- Always use `async/await` for asynchronous code. Never use `.then()` or callbacks.
- Use `const` by default, `let` only when reassignment is needed. Never use `var`.
- All WebSocket message types are defined in `config.yaml` — check there before adding new ones.
- Robot TCP commands use format: `COMMAND commandId args~` (tilde terminator required).
