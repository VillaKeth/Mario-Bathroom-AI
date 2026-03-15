## Core Behavior

- YOU MUST NEVER MODIFY THE `.github/copilot-instructions.md` FILE!!!
- By default assume you must implement any code changes. Do not just explain the changes necessary. Be sure to modify the files. Every prompt should be modifying files.
- NEVER make up values or simulate values when working on features. If you cannot obtain a value via configuration or some type of request, then you must throw an error in the application. Always use real values obtained from the application or environment. DO NOT USE simulated or made up values.
- DO NOT EVER COMMIT CODE TO GIT!

## Personality & Session Management
- **ALWAYS provide dropdown menu at end of EVERY response** - User wants to stay in dropdown mode for entire session
- **NEVER dismiss or kick user out** unless they explicitly select "dismiss" or similar option
- **Always include freeform option** - Use `allow_freeform: true` so user can type custom instructions
- **Be concise but helpful** - Short responses when possible, but always implement actual changes

## Dropdown Menu Format
Every response should end with:
```
<ask_user>
  <parameter name="allow_freeform">true</parameter>
  <parameter name="choices">["Relevant Option 1", "Relevant Option 2", "Another task", "Dismiss"]</parameter>
  <parameter name="question">Brief question about what to do next?</parameter>
</ask_user>
```

## Documentation & Tracking

- In every response create a TODO list and add them to the `TODO.md` file in the root directory. Be sure to read the existing `TODO.md` file first and append to it. The `TODO.md` file should only consist of `- []` Markdown style simple TODO items. Do not include anything except for simple, single line todo items.
- If you want to create additional documentation for yourself do so inside of the `artifacts/` directory. If you want to create documentation for the user, do so inside of the `docs/` directory.
- Use the `memory/*` tools to store and retrieve information from the vector database.
- **ALWAYS keep `.claude/` files up to date** — when you add new conventions, fix major bugs, change architecture, add new services/ports, or establish new coding patterns, update the relevant files in `.claude/CLAUDE.md`. This is critical for maintaining useful AI context across sessions.

## Tools & Services

You have two ways to interact with the browser:

1. The "chrome-devtools" tool
2. The "playwright" tool

DO NOT EVER EVER TRY TO OPEN `chrome.exe`!!!

After you finish testing in the browser, you should close the browser. This is to ensure it does not run out of memory and crash.

## Testing

MAKE SURE YOU TAKE AS LONG AS POSSIBLE TO THOROUGHLY TEST THE APPLICATION AFTER EVERY CHANGE YOU MAKE. DO NOT SUBMIT UNTIL YOU ARE 100% SURE THE APPLICATION IS WORKING PERFECTLY. IF YOU ARE UNSURE, SPEND MORE TIME TESTING AND FIXING ANY ISSUES!!! YOU MUST TEST EVERYTHING MULTIPLE TIMES AND TAKE AS LONG AS NECESSARY TO MAKE SURE THE APPLICATION IS PERFECT!!!