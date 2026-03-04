---
description: Update .claude, TODO.md, and docs after making changes
---

After completing work, update all project documentation:

1. **TODO.md** - Read the existing file, then:
   - Mark completed items with `[x]`
   - Add any new TODO items discovered during work
   - Keep format as simple `- [ ]` / `- [x]` items only

2. **`.claude/CLAUDE.md`** - Update if any of these changed:
   - New services or ports added
   - New coding conventions established
   - Architecture changes
   - New commands or workflows

3. **`.claude/rules/`** - Update or create rules if:
   - New development patterns were established
   - New critical rules were discovered (especially around regressions)
   - File scope patterns need updating

4. **`docs/`** - Create or update documentation if:
   - A significant bug was fixed (document root cause and fix)
   - New features were added (document usage)
   - Testing procedures changed

5. **`.github/copilot-instructions.md`** - Update if major conventions changed

Show what was updated and summarize the changes made.
