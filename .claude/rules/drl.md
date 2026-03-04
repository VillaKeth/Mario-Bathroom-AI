---
description: Doosan Robot Language (DRL) programming conventions
paths:
  - "**/*.drl"
---

# DRL (Doosan Robot Language) Rules

- DRL is Python-based — follow Python 3.2.3 conventions (indentation, no semicolons)
- Reference the Doosan API documentation in `Doosan_API/` for command syntax and parameters
- Key API references by topic:
  - **Motion commands** (movej, movel, etc.): `Doosan_API/02-motion-commands/`
  - **Position creation** (posj, posx, trans): `Doosan_API/02-motion-commands/01-pos-creation.md`
  - **Async motion** (amovej, amovel): `Doosan_API/02-motion-commands/04-asynchronous-motion.md`
  - **Force control** (set_desired_force, compliance): `Doosan_API/05-force-stiffness-control/`
  - **IO operations** (set_digital_output, get_digital_input): `Doosan_API/06-system-commands/01-io-related.md`
  - **Modbus** (add_modbus_signal, get_modbus_input): `Doosan_API/08-external-communication/05-modbus.md`
  - **TCP sockets** (client_socket_open, server_socket_open): `Doosan_API/08-external-communication/03-tcp-client.md`
  - **Math/trig** (sin, cos, rotm2eul): `Doosan_API/07-mathematical-functions/`
  - **Threads** (thread_run, thread_stop): `Doosan_API/06-system-commands/03-thread.md`
  - **Robot state** (get_current_posj, get_tool_force): `Doosan_API/03-auxiliary-control/01-robot-current-value.md`
- Always verify command signatures against the API docs before writing DRL code
- Use `set_velj()` / `set_accj()` before joint motions, `set_velx()` / `set_accx()` before task motions
- Robot TCP commands sent from WellnessScape use format: `COMMAND commandId args~` (tilde terminator)
