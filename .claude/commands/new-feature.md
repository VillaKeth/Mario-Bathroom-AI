---
description: Scaffold a new feature with proper testing and docs plan
---

Help plan and scaffold a new feature: $ARGUMENTS

Steps:
1. **Understand the feature** - Ask clarifying questions if the scope is unclear
2. **Identify affected services** - Which microservices need changes (Camera, Comm Manager, Frontend, LLM)?
3. **Create a plan** with:
   - Files to create or modify
   - New WebSocket messages needed (add to config.yaml)
   - New API endpoints needed
   - New config.yaml settings needed
   - UI changes needed

4. **Scaffold the code**:
   - Add new message types to `config.yaml` if needed
   - Create TypeScript interfaces/types
   - Add handler stubs in affected services
   - Add UI controls in frontend

5. **Update documentation**:
   - Add TODO items to `TODO.md`
   - Update `.claude/CLAUDE.md` if architecture changes
   - Create a doc in `docs/` for the feature

6. **Testing plan**:
   - What manual tests are needed
   - How to verify the feature works end-to-end

Follow all project conventions from `.claude/rules/`.
