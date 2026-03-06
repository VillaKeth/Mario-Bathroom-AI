## Core Behavior

- By default assume you must implement any code changes. Do not just explain the changes necessary. Be sure to modify the files. Every prompt should be modifying files.
- NEVER make up values or simulate values when working on features. If you cannot obtain a value via configuration or some type of request, then you must throw an error in the application. Always use real values obtained from the application or environment. DO NOT USE simulated or made up values.
- MAKE SURE YOU TAKE AS LONG AS POSSIBLE TO THOROUGHLY TEST THE APPLICATION AFTER EVERY CHANGE YOU MAKE. DO NOT SUBMIT UNTIL YOU ARE 100% SURE THE APPLICATION IS WORKING PERFECTLY. IF YOU ARE UNSURE, SPEND MORE TIME TESTING AND FIXING ANY ISSUES!!! YOU MUST TEST EVERYTHING MULTIPLE TIMES AND TAKE AS LONG AS NECESSARY TO MAKE SURE THE APPLICATION IS PERFECT!!!
- ALWAYS USE THE "chrome-devtools" TOOL TO INTERACT WITH THE BROWSER!!! DO NOT EVER EVER TRY TO OPEN `chrome.exe`!

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
- If you want to create additional documentation either for yourself or the user, do so inside of the `docs/` directory.
- Make sure to use the `memory/*` tools to store and retrieve information from the vector database.
- **ALWAYS keep `.claude/` files up to date** — when you add new conventions, fix major bugs, change architecture, add new services/ports, or establish new coding patterns, update the relevant files in `.claude/CLAUDE.md` and `.claude/rules/`. This is critical for maintaining useful AI context across sessions.