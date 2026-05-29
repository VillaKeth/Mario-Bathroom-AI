# Character Content Auto-Generation — Design Spec

## Overview
Add a 7th wizard step "Content Generation" that uses LLM to auto-populate all ~50 YAML content pools for a new character. Supports cloud APIs (OpenAI/Anthropic) with Ollama fallback.

## Architecture

### New File: `server/content_generator.py`
- `ContentGenerator` class with methods per pool category
- Accepts: character name, description, personality traits, tone/vibe
- LLM selection: checks `config.json` for `openai_api_key` or `anthropic_api_key`, falls back to Ollama
- Each pool type has a structured prompt template with format examples
- Returns structured data that gets written to YAML files

### Pool Categories & Counts (matching Mario/Ani standard)

**Idle Messages (14 pools):**
- mumbles (30), jokes (30), songs (25), trivia (25), plumbing_facts→fun_facts (20)
- challenges (20), compliments (25), hand_wash_reminders (15), noise_reactions (15)
- time_comments (12), dj_announcements (10), lonely_mild (10), lonely_medium (10), lonely_deep (8)

**Game Pools (16 files):**
- trivia (30), rapid_fire (30), would_you_rather (25), wyr_extended (25)
- truth_or_dare (38: 15T/15D/8BD), reactions (30: 10W/10L/10T)
- name_that_character (25), simon (30), hangman (30), hot_takes (30)
- riddles (25), karaoke (25), nhie (30), story_starters (25)
- twenty_questions (25), word_chains (25)

**Extras (18 pools):**
- easter_eggs, roasts, fortunes, party_tricks, compliments_extended
- insults_playful, fun_facts_extended, catchphrases_extended, greetings
- farewells, reactions_positive, reactions_negative, encouragements
- teasing, storytelling_hooks, philosophical_questions, dad_jokes, puns

### API Endpoint
`POST /api/generate-content` on character_creator_server (port 8766)
- Request body: `{character_name, description, personality, tone, categories[], api_config}`
- Streams progress via SSE (Server-Sent Events) — each pool completion emits an event
- Response: final summary with pool counts

### Wizard UI Changes
- New Step 7 between Review and Create
- Shows 3 collapsible category sections with progress bars
- For known characters: auto-starts generation
- For custom characters: category checkboxes (all selected default) + tone field
- "Skip" button available (character works with LLM-fallback only, but slower)
- After completion: "Create Character" button becomes active

### LLM Prompting Strategy
Template per pool type with:
1. Character context (name, description, personality)
2. Exact output format (YAML structure with examples)
3. Count requirement
4. Content guidelines (stay in character, avoid offensive content)

Example prompt for trivia:
```
Generate 30 trivia questions for a character named "{name}".
Character: {description}
Personality: {personality}

Output EXACTLY this YAML format:
- q: "What is the speed of light?"
  a: "About 186,000 miles per second"
- q: "..."
  a: "..."

Requirements:
- Questions should relate to the character's world/interests
- Mix difficulty levels
- Keep answers concise (1-2 sentences)
```

### Post-Creation Content Management
- "Manage Content" link on success screen
- Opens page showing all pools with item counts
- "Regenerate" button per pool
- "Preview" expandable to see current content
- Future: "Add custom items" manual editor
