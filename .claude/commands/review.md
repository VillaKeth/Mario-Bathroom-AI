---
description: Code review against project conventions and rules
---

Review the code changes (staged or unstaged) against WellnessScape project rules:

1. **Read the rules** from `.claude/rules/` and `.github/instructions/` first
2. **Check git diff** to see what changed: `git --no-pager diff` and `git --no-pager diff --cached`

Review checklist:
- [ ] TypeScript uses `async/await` (no `.then()` or callbacks)
- [ ] Python `.get()` calls have no default values
- [ ] Camera code preserves depth data during RGB updates
- [ ] Camera code has rate limiting on frame broadcasts
- [ ] YOLO overlay checks `cameraType === 'rgb'`
- [ ] Event listeners set up BEFORE subscriptions
- [ ] WebSocket messages match types defined in `config.yaml`
- [ ] Robot TCP commands use `COMMAND commandId args~` format
- [ ] State queries use `requestStateKeys()` not `requestRobotState()` (unless full state needed)
- [ ] No hardcoded IPs/ports (use config.yaml values)
- [ ] No simulated or made-up values

If camera/WebSocket code was changed, flag that the 8-test camera protocol is required.
Report only genuine issues — skip style nits.
