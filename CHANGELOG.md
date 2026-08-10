# Changelog

Auto-generated from `docs/agent-logs/INDEX.md`.

## 2026-08-10
- **Feature 1 (Tier 3): Streaming Responses (SSE).** Added `chat_stream()` generator to `brain.py` using `generate_content_stream` for token-by-token Gemini output. Added `GET /api/chat/stream` SSE endpoint to `server.py`. Implemented `chatStream()` in preload with `ReadableStream` SSE parsing. Rewired `App.tsx` to create a streaming placeholder message and progressively render tokens via `onToken` callback. Added `.streaming-cursor` CSS animation to `MessageBubble.tsx`. Mutating tool proposals (`write_file`, `delete_file`, `rename_file`) still pause the stream and render `ToolProposalCard` for confirmation. Ollama fallback yields full response as single chunk.

## 2026-08-09
- **Feature 1:** Added `src/backend/changelog.py` script and a startup hook in `server.py` to auto-generate `CHANGELOG.md` at the project root based on this index file.
- **Feature 2:** Added UI toggle in `SystemPanel.tsx` for a global session override safeword mode. Added `/api/config/safeword` endpoint in `server.py` and state in `brain.py` to track and enforce it without requiring the phrase per-message.
- **Feature 3:** Added search input to `IndexPanel.tsx` calling `search_files_by_name()` from `memory.py` via a new `/api/search` endpoint in `server.py` to render file paths inline directly.
- **Bugfix:** Fixed `NameError: name 'brain' is not defined` in `GET /api/status` — replaced individual-name import (`from src.backend.brain import ...`) with module import (`import src.backend.brain as brain`) to match the pattern used by `toggle_safeword`.
- **Feature 1 (Tier 2):** Added token budget indicator. Configured `TOKEN_BUDGET_WARNING` in `config.py` (default 1.5M), exposed it via `/api/status`, and styled the `tokens` readout in `SystemPanel.tsx` to turn amber (`system-stat__value--accent`) when the budget is exceeded.
- **Feature 2 (Tier 2):** Added `CommandPalette.tsx` overlay accessible via `Ctrl+K`. Wired actions to focus chat, toggle the system log drawer, and trigger the index whitelist dialog. Styled to match the HUD aesthetic.
- **Feature 3 (Tier 2):** Implemented Undo Stack for mutating tools (`rename`, `delete`, `write`). Added `action_history` table to `memory.py` and intercepted OS operations in `tools.py` to cache file contents pre-mutation. Added an undo button to `SystemPanel.tsx` connecting to new `/api/undo` endpoints.
- **Feature 4 (Tier 2):** Implemented Persistent Chat History. Added `messages` table to `memory.py` and synchronized `_chat_history` in `brain.py` with the database. Exposed history via `/api/chat/history` endpoint in `server.py` and loaded it on application mount in `App.tsx`.
- **Feature 5 (Tier 2):** Implemented Onboarding Wizard. Modified `config.py` to set `NEEDS_ONBOARDING` instead of `sys.exit()` on missing key. Added `/api/onboarding` to `server.py` to save `.env`. Created `OnboardingWizard.tsx` and wired it into `App.tsx` on first run if health check indicates missing configuration.
- **Feature 6 (Tier 2):** Implemented Pytest Suite. Added `pytest` to `requirements.txt`. Created `tests/test_memory.py` and `tests/test_tools.py` with 100% pass rate. Used `tmp_path` and monkeypatched `DB_PATH` to ensure tests run in isolation without polluting production state.

## 2026-08-08
- Fixed Lithe hallucinating tool execution by adding `disable=True` to `AutomaticFunctionCallingConfig` in `brain.py`. Found that the new `google.genai` SDK was auto-executing Python tools under the hood, silently bypassing `ToolProposalCard` UI interception and creating files directly. Also added `[TOOL EXECUTED]` log lines to `tools.py` for auditability, and patched `COMPLIANT_SYSTEM_PROMPT` to properly route tool instructions during safeword mode.
- **Bugfix:** Injected strict tool execution rules into `system_prompt.py` to prevent text-based confirmation loops. Fixed context-dropping issue by implementing a global `_chat_history` list in `brain.py` to maintain standard conversational context across API requests.

## 2026-08-07
- Fixed Gemini timeout issue (removed hardcoded 5s limit) & refactored tool schema to fix 400 Bad Request errors.
- **HUD Redesign — Backend:** Added `GET /api/status` endpoint to `server.py`, `get_file_count_by_directory()` to `memory.py`, exposed `last_event_time` in `watcher.py` — all read-only, feeds the new HUD panels
- **HUD Redesign — Preload/Types:** Added `litheAPI.getStatus()` to preload API and `StatusResponse` to `env.d.ts`
- **HUD Redesign — CSS:** Full replacement of `index.css` — amber accent, near-black palette, JetBrains Mono monospace stack, 0-2px radii, hairline borders, three-pane HUD grid layout
- **HUD Redesign — Components:** Rebuilt `App.tsx` as three-pane HUD orchestrator, created `IndexPanel.tsx` and `SystemPanel.tsx`, restyled `ChatWindow.tsx` (boot screen + cursor indicator), `MessageBubble.tsx` (terminal prefixes), `ChatInput.tsx` (command-line style)
- **HUD Redesign — Electron:** Updated `main/index.ts` — `backgroundColor: #08080a`, enabled resizing (min 900×600), default 1100×720
- **HUD Redesign — Font:** Swapped `index.html` from Inter to JetBrains Mono Google Font
- **UI Fixes — Whitelist Picker:** Replaced blind full-drive indexing with a dynamic whitelist picker in `IndexPanel.tsx`, added `+ INDEX` and text input, exposed via `dialog.showOpenDialog` in main, updated `watcher.py` and `indexer.py` to handle dynamic watch/index adding.
- **UI Fixes — Unified Tool Confirmation UX:** Intercepted mutating LLM tool calls (`write_file`, `delete_file`, `rename_file`) in `brain.py` to pause execution and send a `tool_proposal` to the frontend. Implemented `ToolProposalCard.tsx` with diffs and ACCEPT/REJECT buttons.
- **UI Fixes — Semantic Colors:** Fixed `--success` drift in chat, re-colored `lithe>` prefix to `--text-dim`.
- **UI Fixes — System Panel:** Added `[03] SYSTEM` header to match conventions, extracted live LLM token counts in `brain.py`, and piped to `SystemPanel.tsx` via `/api/status`.
- **Live Watcher Log Console:** Created `broadcaster.py` to stream indexing/removal events. Exposed `/ws/watcher-log` WebSocket in `server.py` with 100ms batching and a 500-event history ring buffer. Built an expandable `system-log-drawer` in `SystemPanel.tsx` with autoscroll, filtering, and 1000-line DOM cap.
- **UI Fixes — Themed Title Bar:** Added `titleBarStyle: 'hidden'` and `titleBarOverlay` to `index.ts`. Replaced default header with draggable custom title bar in `App.tsx` and `index.css`. Upgraded brand logo with `lithe-mark-hero.svg` and `icon.ico`. Fixed `[01] INDEX`'s `last event` missing updates by lifting WebSocket to `App.tsx`. Fixed port binding conflict by pinging server health before spawning `pythonProcess`.

## 2026-08-06
- **Documentation Audit:** Full sync of INDEX.md, FEATURES.md, and ARCHITECTURE.md — added UPGRADE Phase statuses, updated file manifest, added running instructions, expanded architecture notes, defined suggested next directions

## 2026-08-04
- **UPGRADE Phase 1.1:** Enabled SQLite WAL mode + busy_timeout in `memory.py` — prevents "database is locked" errors from concurrent indexer/LLM access
- **UPGRADE Phase 1.2:** Added circuit breakers to `tools.py` — path validation (empty, null bytes, protected system dirs), path normalization (`realpath`), and 30-second timeout wrapper via `concurrent.futures`
- Minor: Added `TypeError` catch in `brain.py` function calling handler for malformed LLM arguments
- **UPGRADE Phase 2:** Refactored Ollama fallback in `brain.py` — dedicated `_ollama_chat()` function, `_check_ollama_available()` health check, httpx client (replaced urllib), Ollama `/api/chat` with proper message roles
- **UPGRADE Phase 2:** Added configurable Ollama settings to `config.py` (`OLLAMA_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`) and documented them in `.env.example`
- **UPGRADE Phase 3.4:** Created `heuristics.py` — pure-function engine mapping 15+ folder patterns and 20+ extension rules to semantic category tags
- **UPGRADE Phase 3.4:** Schema migration in `memory.py` — added `category` column, `delete_file_by_path()` function, updated upsert/search queries
- **UPGRADE Phase 3.4:** Created `watcher.py` — `watchdog`-based real-time file watcher with 1s debouncing, EXCLUDED_DIRS filtering, auto SQLite updates
- **UPGRADE Phase 3.4:** Updated `indexer.py` to apply heuristic category tags during `walk_and_index()`
- **UPGRADE Phase 3.4:** Updated `server.py` startup — runs initial index then starts file watcher
- **UPGRADE Phase 3.5:** Updated `brain.py` — `search_files` tool now shows `[category]` tags in results

## 2026-08-03
- Updated outdated documentation states
- Implemented Customization Rules for AI Agents (.agents/AGENTS.md)
- Fixed Gemini timeout — removed broken custom http_options from GenerateContentConfig; SDK defaults work correctly
- Added auto-indexing on server startup in server.py — no more manual POST /api/index needed
- Added search_files LLM tool (memory.py + brain.py) — fuzzy file search by keyword via function calling
- Packaged Lithe as a standalone Windows desktop app using PyInstaller and electron-builder (F-07)
- Generated a comprehensive feature rundown document in `personal saved copies/Lithe_Features.md`

## 2026-07-12
- Implemented F-03 (Local Directory Indexer)
- Implemented F-04 (RAG & File Context)

## 2026-07-11
- Scaffolded project directory structure
- Implemented F-01 (Core LLM Connection)
- Implemented F-06 (Candid Persona & Safeword)
- Implemented F-02 (Minimal Chat Interface)
- Created `docs/agent-logs/INDEX.md`
