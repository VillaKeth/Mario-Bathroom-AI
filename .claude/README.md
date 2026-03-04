# .claude Folder — Complete Reference Guide

This document explains **every feature, file, and subfolder** of the `.claude` configuration system used by Claude Code.

---

## Table of Contents

1. [Overview](#overview)
2. [CLAUDE.md — Project Memory](#claudemd--project-memory)
3. [CLAUDE.local.md — Personal Overlay](#claudelocalmd--personal-overlay)
4. [settings.json — Project Settings](#settingsjson--project-settings)
5. [settings.local.json — Personal Settings](#settingslocaljson--personal-settings)
6. [commands/ — Custom Slash Commands](#commands--custom-slash-commands)
7. [rules/ — Scoped Coding Rules](#rules--scoped-coding-rules)
8. [skills/ — Knowledge Modules](#skills--knowledge-modules)
9. [agents/ — AI Agent Personas](#agents--ai-agent-personas)
10. [hooks/ — Event-Driven Automations](#hooks--event-driven-automations)
11. [plans/ — Saved Implementation Plans](#plans--saved-implementation-plans)
12. [How Merging & Precedence Works](#how-merging--precedence-works)
13. [What to Commit vs Gitignore](#what-to-commit-vs-gitignore)
14. [.claude vs .github Comparison](#claude-vs-github-comparison)

---

## Overview

The `.claude/` directory is Claude Code's project-level configuration and extensibility hub. It controls:
- **What Claude knows** about your project (memory/context)
- **What Claude is allowed to do** (permissions)
- **What coding rules to follow** (rules)
- **What custom workflows exist** (commands, skills)
- **How Claude behaves** (agents, hooks)

Think of it as `.vscode/` + `.github/` but for your AI coding assistant.

### Full Directory Structure

```
.claude/
├── CLAUDE.md              # Project memory & context (loaded every session)
├── CLAUDE.local.md        # Personal context overlay (gitignored)
├── settings.json          # Project-wide settings & permissions (committed)
├── settings.local.json    # Personal setting overrides (gitignored)
├── README.md              # This file
│
├── commands/              # Custom slash commands (/commandname)
│   ├── status.md          # /status
│   ├── review.md          # /review
│   └── db/
│       └── migrate.md     # /db:migrate (subfolder = namespace)
│
├── rules/                 # Auto-applied coding rules (scoped by file paths)
│   ├── typescript.md      # Applied to *.ts, *.tsx
│   ├── python.md          # Applied to *.py
│   └── camera-system.md   # Applied to camera/WebSocket files
│
├── skills/                # Knowledge modules & reusable expertise
│   └── security-guardian/
│       ├── SKILL.md       # Main skill definition
│       └── reference.md   # Supporting material
│
├── agents/                # AI agent personas for delegation
│   ├── code-reviewer.md
│   └── debugger.md
│
├── hooks/                 # Event-driven automation scripts
│   ├── auto-format.sh
│   └── security-check.sh
│
└── plans/                 # Saved implementation plans
    └── feature-x-plan.md
```

---

## CLAUDE.md — Project Memory

**The single most important file in the entire `.claude` folder.**

Claude reads this at the start of every session to understand your project. It's the AI equivalent of onboarding a new developer.

### What to Include

| Section | Example Content |
|---------|----------------|
| **Project overview** | "WellnessScape is a robotics massage system with 5 microservices" |
| **Tech stack** | "TypeScript + Vite frontend, Python camera server, Node.js comm manager" |
| **Common commands** | `make dev`, `make kill`, `npm start` |
| **Architecture** | Services, ports, data flow diagram |
| **Key conventions** | "Always use async/await", "Never re-encode frames" |
| **Critical rules** | "Never block WebSocket during init", "Rate limit to 20 FPS" |
| **Doc pointers** | Links to `docs/ARCHITECTURE.md`, `docs/CAMERA_TESTING_PROTOCOL.md` |

### Best Practices

- **Keep it under ~100 lines** — Claude has limited context; be concise
- **Write for an AI** — be precise and actionable, not narrative
- **Update it regularly** — stale instructions cause wrong behavior
- **Don't duplicate** — point to detailed docs instead of copying them in

### Loading Hierarchy

Claude loads CLAUDE.md files in this order (later = higher priority):

```
1. ~/.claude/CLAUDE.md          ← Global (all your projects)
2. ./CLAUDE.md                  ← Project root (or .claude/CLAUDE.md)
3. ./subdir/CLAUDE.md           ← Directory-specific (monorepo modules)
4. ./CLAUDE.local.md            ← Personal overlay (gitignored)
```

All are **merged additively**. Conflicts resolve by priority (4 beats 3 beats 2 beats 1).

---

## CLAUDE.local.md — Personal Overlay

A personal, gitignored version of CLAUDE.md. Use for preferences that only apply to you.

### Use Cases

- Personal workflow preferences ("I prefer yarn over npm")
- Machine-specific paths or environment details
- Temporary debugging instructions ("Focus on the auth module this week")
- Sensitive project notes you don't want in git

### How It Merges with CLAUDE.md

- **No conflict** → Both are active simultaneously (additive)
- **Direct conflict** → `.local` wins (override)

```
CLAUDE.md:          "Use npm for package management"
CLAUDE.local.md:    "Use yarn instead of npm"
→ Claude uses yarn (local wins)

CLAUDE.md:          "Always run tests before committing"
CLAUDE.local.md:    "Also remind me to check robot connection"
→ Claude does BOTH (no conflict, additive)
```

---

## settings.json — Project Settings

Structured JSON configuration shared with your team (committed to git).

### Full Schema

```json
{
  "$schema": "https://json-schema.org/claude-code-settings.json",

  "permissions": {
    "allow": [
      "Read",
      "Edit",
      "Write",
      "Bash(make *)",
      "Bash(npm run *)",
      "Bash(git *)"
    ],
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Bash(rm -rf *)"
    ]
  },

  "hooks": {
    "PreToolUse": [...],
    "PostToolUse": [...],
    "Notification": [...],
    "Stop": [...]
  },

  "mcpServers": {
    "server-name": {
      "command": "npx",
      "args": ["-y", "@some/mcp-server"]
    }
  }
}
```

### Permission Patterns

Permissions use the format `ToolName(pattern)`:

| Pattern | Meaning |
|---------|---------|
| `"Read"` | Allow all file reads |
| `"Bash(make *)"` | Allow any make command |
| `"Bash(npm run test)"` | Allow only `npm run test` |
| `"Read(./.env)"` | Target specific file |
| `"Bash(rm -rf *)"` | Target dangerous command (use in deny) |

**Deny always overrides allow** at the same scope level.

### Hooks in settings.json

Hooks are event-driven automations configured in settings.json (scripts live in `hooks/` folder):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": ".claude/hooks/block-dangerous.sh"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "prettier --write $CLAUDE_FILE"
          }
        ]
      }
    ]
  }
}
```

### MCP Server Configuration

Connect to external tool servers:

```json
{
  "mcpServers": {
    "chrome-devtools": {
      "command": "npx",
      "args": ["-y", "@anthropic/chrome-devtools-mcp"]
    }
  }
}
```

---

## settings.local.json — Personal Settings

Same format as `settings.json` but **gitignored**. Only affects your machine.

### Use Cases

- Machine-specific tool paths
- Personal API keys or tokens
- Experimental feature flags
- Extra permissions only you need

### How It Merges with settings.json

Settings are **recursively deep-merged** at the key level:
- Only the keys you define in `.local` override the base
- Non-conflicting settings are **combined** (you get both)
- Deny still overrides allow at the same scope

```json
// settings.json (team): allows make and npm
{ "permissions": { "allow": ["Bash(make *)", "Bash(npm run *)"] } }

// settings.local.json (you): adds docker
{ "permissions": { "allow": ["Bash(docker *)"] } }

// Result: you can use make, npm run, AND docker
```

---

## commands/ — Custom Slash Commands

Each `.md` file becomes a `/command` in Claude Code. The filename (minus `.md`) is the command name.

### Naming

```
commands/status.md         →  /status
commands/deploy.md         →  /deploy
commands/db/migrate.md     →  /db:migrate     (subfolder = namespace)
commands/db/seed.md        →  /db:seed
```

### File Format

```markdown
---
description: Brief description (shown in command picker when you type /)
---

Your prompt/instructions here.

Use $ARGUMENTS for all user input after the command name.
Use $1, $2 for positional arguments.
```

### Example

```markdown
---
description: Show config for a specific service
---

Read config.yaml and display settings for: $ARGUMENTS

If no service specified, show a summary of all services.
```

**Usage**: `/config CAMERA_SERVER` → `$ARGUMENTS` = "CAMERA_SERVER"

### Tips

- Keep commands focused on one task
- Use subfolders to organize by domain
- Type `/` in Claude Code to see all available commands
- Commands can reference other files, run shell commands, etc.

---

## rules/ — Scoped Coding Rules

Rules are **auto-applied** based on which files Claude is currently editing. Each rule file has a `paths` directive in its YAML frontmatter that scopes activation.

### File Format

```markdown
---
description: What these rules cover
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "!**/node_modules/**"
---

# Your Rules

- Always use async/await, never .then()
- Use const by default
```

### Supported Frontmatter Directives

| Directive | Type | Purpose |
|-----------|------|---------|
| `description` | string | What the rule covers |
| `paths` | string[] | Glob patterns for when rules activate |

### Path Pattern Syntax

| Pattern | Matches |
|---------|---------|
| `**/*.ts` | All TypeScript files |
| `frontend/**/*.ts` | TS files only in frontend/ |
| `!**/node_modules/**` | Exclude node_modules (prefix with `!`) |
| `camera_server/**/*.py` | Python files in camera_server |

### How Rules Work

- Claude loads ALL matching rules when editing a file
- Multiple rules can apply simultaneously (they're additive)
- Rules are concise guardrails — keep them short and actionable
- Different from `skills/` (which are deeper knowledge modules)

---

## skills/ — Knowledge Modules

Skills contain **deeper procedural knowledge** — checklists, reference material, domain expertise. They're more detailed than rules.

### Structure

```
skills/
├── security-guardian/
│   ├── SKILL.md           # Main skill definition
│   └── reference.md       # Supporting reference material
├── tdd/
│   └── SKILL.md
└── camera-testing/
    ├── SKILL.md
    └── test-cases.md
```

### SKILL.md Format

```markdown
---
name: security-guardian
description: Security audit and vulnerability checking
---

# Security Guardian

## When to Activate
- When reviewing authentication code
- When handling user input
- When modifying API endpoints

## Checklist
1. Check for SQL injection
2. Validate all user input
3. Ensure proper auth on all routes
...
```

### Skills vs Rules vs Commands

| Feature | Rules | Skills | Commands |
|---------|-------|--------|----------|
| **Length** | Short (5-15 lines) | Long (detailed procedures) | Medium (task prompts) |
| **Activation** | Auto (by file path) | When relevant to task | Manual (`/command`) |
| **Purpose** | Constraints & conventions | Deep domain knowledge | Workflow shortcuts |
| **Example** | "Use async/await" | "Full security audit checklist" | "/deploy staging" |

---

## agents/ — AI Agent Personas

Define specialized Claude personas with different behaviors, expertise, and focus areas.

### Structure

```
agents/
├── code-reviewer.md       # Strict, detail-oriented reviewer
├── backend-architect.md   # System design expert
├── debugger.md            # Bug hunting specialist
└── security-auditor.md    # Security-focused analysis
```

### Agent File Format

```markdown
---
name: code-reviewer
description: Strict code reviewer focused on quality
---

# Code Reviewer

You are a strict code reviewer. Your job is to:
- Find bugs, not style issues
- Check for security vulnerabilities
- Verify error handling is complete
- Ensure tests cover edge cases

## Tone
Be direct and concise. Only flag genuine issues.

## Rules
- Never approve code with unhandled errors
- Always check for race conditions in async code
- Verify all user input is validated
```

### Use Cases

- Delegating code reviews to a specialized reviewer
- Architecture planning with a design-focused agent
- Parallel workflows where different agents handle different concerns
- Switching between "creative" and "strict" modes

---

## hooks/ — Event-Driven Automations

Scripts that run automatically on specific lifecycle events. Configured in `settings.json`, scripts live in `hooks/`.

### Lifecycle Events

| Event | When It Fires | Common Use |
|-------|---------------|------------|
| **PreToolUse** | Before any tool call | Block dangerous commands, enforce policies |
| **PostToolUse** | After a tool succeeds | Auto-format, run linters, trigger checks |
| **Notification** | When Claude sends a notification | Desktop alerts, logging |
| **Stop** | When Claude finishes responding | Final validation, summary, cleanup |
| **SessionStart** | When a session begins | Load context, check environment |
| **PermissionRequest** | When Claude asks for permission | Auto-approve/deny based on rules |

### Hook Types

| Type | Description |
|------|-------------|
| **command** | Runs a shell script. Receives JSON event via stdin, returns JSON via stdout |
| **prompt** | Sends a prompt to a Claude sub-model for fast evaluation |
| **agent** | Spawns a full Claude subagent for complex verification |

### Example: Block Dangerous Commands

**`hooks/block-dangerous.sh`:**
```bash
#!/bin/bash
# Read the JSON event from stdin
EVENT=$(cat)
COMMAND=$(echo "$EVENT" | jq -r '.tool_input.command')

# Block rm -rf
if echo "$COMMAND" | grep -q "rm -rf"; then
  echo '{"hookSpecificOutput":{"permissionDecision":"deny","permissionDecisionReason":"Destructive command blocked"}}'
  exit 0
fi
```

**In `settings.json`:**
```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Bash",
      "hooks": [{"type": "command", "command": ".claude/hooks/block-dangerous.sh"}]
    }]
  }
}
```

### Example: Auto-Format After Write

```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Write",
      "hooks": [{"type": "command", "command": "prettier --write $CLAUDE_FILE"}]
    }]
  }
}
```

---

## plans/ — Saved Implementation Plans

Where Claude saves actionable implementation plans that persist across sessions.

### Structure

```
plans/
├── feature-x-plan.md       # Feature implementation blueprint
├── refactor-auth.md         # Refactoring strategy
├── migration-v2.md          # Migration plan
└── sprint-2026-03.md        # Sprint planning
```

### Use Cases

- Persisting multi-step feature plans across sessions
- Tracking architectural decisions
- Sharing implementation strategies with the team
- Resuming work after a break

---

## How Merging & Precedence Works

### For CLAUDE.md Files (Context)

All CLAUDE.md files are **loaded and merged additively**. On conflict, more specific wins:

```
Priority (highest to lowest):
1. CLAUDE.local.md           ← Personal project overlay
2. ./subdir/CLAUDE.md         ← Directory-specific
3. ./CLAUDE.md                ← Project root
4. ~/.claude/CLAUDE.md        ← Global user
```

- **No conflict** → Both instructions are active (union)
- **Conflict** → Higher priority wins

### For settings.json Files (Config)

Settings are **recursively deep-merged**. More specific scopes override less specific:

```
Priority (highest to lowest):
1. IT managed policies (enterprise)
2. Command line flags
3. .claude/settings.local.json    ← Project personal
4. .claude/settings.json          ← Project shared
5. ~/.claude/settings.local.json  ← Global personal
6. ~/.claude/settings.json        ← Global shared
```

- Only keys you define in higher-priority files override lower ones
- Non-conflicting settings combine (you get the union)
- **Deny always overrides allow** at the same scope level

---

## What to Commit vs Gitignore

| File/Folder | Commit? | Reason |
|-------------|---------|--------|
| `CLAUDE.md` | ✅ Yes | Team shares project context |
| `settings.json` | ✅ Yes | Team shares permissions & hooks |
| `commands/` | ✅ Yes | Team shares workflows |
| `rules/` | ✅ Yes | Team shares conventions |
| `skills/` | ✅ Yes | Team shares knowledge |
| `agents/` | ✅ Yes | Team shares agent definitions |
| `hooks/` | ✅ Yes | Team shares automations |
| `README.md` | ✅ Yes | Documentation |
| `CLAUDE.local.md` | ❌ No | Personal preferences |
| `settings.local.json` | ❌ No | Personal machine config |
| `plans/` | ⚡ Optional | Depends if plans are team-shared |

**Add to `.gitignore`:**
```
.claude/settings.local.json
.claude/CLAUDE.local.md
```

---

## .claude vs .github Comparison

This project uses **both** — `.github/` for GitHub Copilot in VS Code, `.claude/` for Claude Code.

| Feature | `.claude/` (Claude Code) | `.github/` (Copilot) |
|---------|-------------------------|----------------------|
| Main config | `CLAUDE.md` | `copilot-instructions.md` |
| Scoped rules | `rules/*.md` (`paths` directive) | `instructions/*.md` (`applyTo` directive) |
| Commands | `commands/*.md` → `/slash` commands | `prompts/*.md` |
| Agents | `agents/*.md` | `agents/*.md` |
| Skills | `skills/*/SKILL.md` | `skills/*.skill.md` |
| Settings | `settings.json` | VS Code settings.json |
| Hooks | `hooks/` + `settings.json` | N/A |
| Plans | `plans/` | N/A |
| Personal override | `CLAUDE.local.md` | N/A |

**Both work simultaneously** — there's no conflict between them. Each AI tool reads its own config.

---

## Quick Reference: Current WellnessScape Setup

### Commands Available (`/commandname`)

| Command | Description |
|---------|-------------|
| `/status` | Check which services are running |
| `/start` | Start all services with make dev |
| `/camera-test` | Run 8 camera test cases |
| `/debug-camera` | Diagnose camera pipeline issues |
| `/check-robot` | Verify Doosan robot connection |
| `/review` | Code review against project rules |
| `/update-docs` | Update .claude, TODO.md, docs after changes |
| `/config [service]` | Show config.yaml settings |
| `/new-feature [name]` | Scaffold a new feature |

### Rules (auto-applied by file type)

| Rule File | Applied To |
|-----------|------------|
| `typescript.md` | `**/*.ts`, `**/*.tsx` |
| `python.md` | `**/*.py` |
| `camera-system.md` | Camera server, comm manager, frontend camera code |
| `frontend.md` | `frontend/**/*.ts`, `*.html`, `*.css` |

---

## External Resources

- [Official Claude Code Settings Docs](https://code.claude.com/docs/en/settings)
- [Official Hooks Reference](https://code.claude.com/docs/en/hooks)
- [Official Security & Permissions](https://code.claude.com/docs/en/security)
- [Official Skills Documentation](https://code.claude.com/docs/en/skills)
- [Claude.md Best Practices Blog](https://claude.com/blog/using-claude-md-files)
- [Community Guide (Cranot)](https://github.com/Cranot/claude-code-guide)
- [Everything Claude Code (affaan-m)](https://github.com/affaan-m/everything-claude-code)

---

*Last updated: 2026-02-23*
