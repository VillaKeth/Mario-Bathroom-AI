---
name: tester-agent
description: 'Tester Agent'
model: GPT-5.2-Codex (copilot)
target: vscode
user-invokable: true
disable-model-invocation: false
tools: ['execute/getTerminalOutput', 'execute/runTask', 'execute/createAndRunTask', 'execute/runInTerminal', 'read/readFile', 'read/terminalSelection', 'read/terminalLastCommand', 'read/getTaskOutput', 'edit/createDirectory', 'edit/createFile', 'edit/editFiles', 'search', 'web', 'memory/*', 'io.github.chromedevtools/chrome-devtools-mcp/click', 'io.github.chromedevtools/chrome-devtools-mcp/evaluate_script', 'io.github.chromedevtools/chrome-devtools-mcp/fill', 'io.github.chromedevtools/chrome-devtools-mcp/fill_form', 'io.github.chromedevtools/chrome-devtools-mcp/get_console_message', 'io.github.chromedevtools/chrome-devtools-mcp/get_network_request', 'io.github.chromedevtools/chrome-devtools-mcp/handle_dialog', 'io.github.chromedevtools/chrome-devtools-mcp/list_console_messages', 'io.github.chromedevtools/chrome-devtools-mcp/list_network_requests', 'io.github.chromedevtools/chrome-devtools-mcp/list_pages', 'io.github.chromedevtools/chrome-devtools-mcp/navigate_page', 'io.github.chromedevtools/chrome-devtools-mcp/resize_page', 'io.github.chromedevtools/chrome-devtools-mcp/select_page', 'io.github.chromedevtools/chrome-devtools-mcp/take_screenshot', 'io.github.chromedevtools/chrome-devtools-mcp/take_snapshot', 'io.github.chromedevtools/chrome-devtools-mcp/wait_for', 'todo']
---
# Overview

To test this project you need to use the Test Manager. It is located in the `/test_manager` directory and you can start it with the command `npm run test:all`. This will run the entire test suite and save the results to files in the `test_manager/artifacts` directory.

You can view these files to see the results of each test.

ONLY LOOK AT AND EDIT FILES IN THESE DIRECTORIES:

1. `/config.yaml` - A file in the root directory.
2. `/TODO.md` - A file in the root directory.
3. `/.github` - This directory and all of its contents.
4. `/test_manager` - This directory but do not look inside of the `node_modules` directory inside of it... This is library code that should NEVER be modified.