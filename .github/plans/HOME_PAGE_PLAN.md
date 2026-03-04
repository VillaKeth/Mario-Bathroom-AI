# Plan: Make Home Page Fully Functional

## Problem Statement
The Home page has UI elements (body zone toggles, speed/pressure sliders, coverflow selectors, start/stop buttons) that are partially wired up. The goal is to make them fully functional so that:
1. **Sliders** send real-time STATE commands to the robot
2. **Body zone toggles** track upper/lower/left/right state
3. **Coverflow selectors** determine massage location & type
4. **Start button** builds a full PATH command by combining all UI state and loading the corresponding path file from `/demo_paths/`

## Current State Analysis

### What exists:
- **Body zones**: 4 SVG quadrants (upper-left, upper-right, lower-left, lower-right) with click-to-toggle
- **Speed slider**: Sends `send_velocity` → `velocity <seq> <level>~` (level 1-10)
- **Pressure slider**: Sends `send_force` → `change_force <seq> <level>~` (level 0-10)
- **Coverflows**: Select massage location (line/spiral/zig_zag) and type (elbow/palm/knead)
- **Start button**: Sends generic `outgoing_robot_command` with `start_session` (no PATH logic)
- **CM `send_path` handler**: Accepts waypoint arrays, builds PATH commands, supports bilateral/mirror
- **CM `outgoing_robot_command`**: Forwards raw string commands to robot
- **Path files**: 6 files in `/demo_paths/` (left_side_straight_down, right_side_straight_down, spiral, squiggly, zigzag_left, zigzag_right)

### What's missing:
- Sliders don't use the user-specified STATE command format
- No left/right side tracking (only upper/lower)
- Start button doesn't build PATH commands or load path files
- No mapping from UI state → path file name
- CM has no handler for loading path files from disk
- Path file naming doesn't match the zone+location convention

## Proposed Approach

### Architecture Decision
Add a new `start_massage` WebSocket handler in the Communication Manager that:
1. Receives all UI parameters (zones, speed, pressure, location, type)
2. Resolves the path file name from parameters
3. Reads the file from `/demo_paths/`
4. Parses waypoints from the file
5. Sends pre-path STATE commands (force, velocity, TCP)
6. Sends `PATH <seq> <speed> <pressure>\n<waypoints>~` to robot

This keeps file I/O on the server side (where the files live) and reuses existing `handleSendPath` infrastructure.

### File Naming Convention
Format: `<side>_<level>_<location>.txt`
- **side**: `left`, `right`, `both` (derived from body zone toggles)
- **level**: `upper`, `lower`, `full` (derived from body zone toggles)
- **location**: `line`, `spiral`, `zigzag`, `squiggly` (from massage location coverflow)

Examples: `left_upper_zigzag.txt`, `both_full_spiral.txt`, `right_lower_line.txt`

Existing files will be mapped/symlinked. Missing combinations will use fallback to the closest available file.

### Slider Command Formats
- **Speed**: `STATE 0 desiredVelocityLevel <speed_level_integer>~` (via `outgoing_robot_command`)
- **Pressure**: `STATE 0 desiredForceLevel <pressure_level_float>~` (via `outgoing_robot_command`)

### Massage Type → TCP Mapping
- `elbow` → `tcp_elbow`
- `palm` → `tcp_palm`
- `knead` → `tcp_knead`

---

## Todos

### 1. `slider-commands` — Update speed & pressure sliders to send STATE commands
- Modify `sendSpeed()` in `frontend/public/index.ts` to send `outgoing_robot_command` with `STATE 0 desiredVelocityLevel <level>~`
- Modify `sendPressure()` to send `outgoing_robot_command` with `STATE 0 desiredForceLevel <level>~`
- Map slider percentage (0-100) to appropriate integer/float levels
- **Add 1500ms debounce** to both slider send functions — only send command after user stops adjusting for 1.5 seconds. Implement a reusable `debounce()` utility or inline timer approach.

### 2. `body-zone-tracking` — Track left/right side state alongside upper/lower
- Add `leftActive` and `rightActive` boolean flags to HomeApp
- Update `syncBodyZoneState()` to compute: leftActive = upper-left || lower-left, rightActive = upper-right || lower-right
- These flags determine the "side" part of the path file name

### 3. `cm-start-massage` — Add `start_massage` WebSocket handler in Communication Manager
- Register new `start_massage` message type in WebSocket handler
- Handler receives: `{ zones: { upper, lower, left, right }, speed, pressure, location, massageType }`
- Resolves path file name from zones + location
- Reads file from `/demo_paths/` directory
- Parses waypoints (lines of `x y` pairs)
- Maps massageType to TCP name
- Determines bilateral mode from zone state
- Calls existing `handleSendPath` with constructed waypoint data, or builds raw PATH command
- Sends response back to frontend

### 4. `start-button` — Wire Start button to send `start_massage` message
- Replace current `startSession()` in index.ts with new logic
- Collect all UI state: zone toggles, slider values, coverflow selections
- Validate required selections (at least one zone, both coverflows selected)
- Send `start_massage` WebSocket message with collected data
- Handle response (success/error feedback)

### 5. `path-file-mapping` — Create file resolution logic and rename/create path files
- Define mapping function: (side, level, location) → filename
- Create fallback logic: if exact file missing, try broader match (e.g., `both_full_spiral.txt` → `spiral.txt`)
- Rename existing files to match convention or create symlinks/copies
- Document available paths

### 6. `ui-feedback` — Add visual feedback for Start button actions
- Show loading state while command is being sent
- Show success/error toast or indicator
- Disable Start button while massage is active
- Enable Stop button when massage starts

---

## Dependencies
- `body-zone-tracking` must complete before `start-button`
- `cm-start-massage` must complete before `start-button`
- `path-file-mapping` must complete before `cm-start-massage`
- `slider-commands` is independent
- `ui-feedback` depends on `start-button`

## Notes
- The existing `send_path` handler in CM already handles waypoints, STATE commands, TCP selection, bilateral mode, and mirror commands. The new `start_massage` handler should leverage this.
- Path files currently have mixed formats (some with log timestamps, some raw). The file parser needs to handle both.
- The `PATH <seq> <speed> <pressure>` format from the user matches the existing `PATH <seqNum> <velocity> <acceleration>` format in `handleSendPath`.
- **Path files**: 16 files now exist in `/demo_paths/` using `<side>_<level>_<location>.txt` naming. The `*_upper_*` files have content; `*_lower_*` files are 0-byte placeholders for now.
- **Debounce**: Slider send functions must debounce at 1500ms to avoid flooding the robot with commands during adjustment.
