# docs/FEATURES.md — Lithe(Jarvis-Lite) Feature Specification

> **Status:** Living document — update as features are added or completed.
> **Audience:** AI coding agents, lead developer.
> **Format:** Each feature has a user story, acceptance criteria, and scope notes.

---

## Feature Index

| ID | Feature | Category | Status |
|---|---|---|---|
| F-01 | Core LLM Connection (The Brain) | Backend | ✅ Complete |
| F-02 | Minimal Chat Interface (The Face) | Frontend | ✅ Complete |
| F-03 | Local Directory Indexer (The Memory) | Backend | ✅ Complete |
| F-04 | RAG & File Context (Second Brain) | Backend | ✅ Complete |
| F-05 | Basic Task Execution (The Hands) | Tooling | ✅ Complete |
| F-06 | Candid Persona & Safeword | Backend | ✅ Complete |
| F-07 | Desktop Packaging (The Box) | DevOps | ✅ Complete |

## Upgrade Plan Index

| ID | Upgrade | Phase | Status |
|---|---|---|---|
| U-01 | SQLite WAL Mode | Phase 1: Foundation & Safety | ✅ Complete |
| U-02 | Circuit Breakers for Tool Execution | Phase 1: Foundation & Safety | ✅ Complete |
| U-03 | Ollama Fallback Pattern | Phase 2: Reliability | ✅ Complete |
| U-04 | Event-Driven Memory (File Watcher) | Phase 3: Efficiency & Context | ✅ Complete |
| U-05 | Heuristic Graph (Category Tagging) | Phase 3: Efficiency & Context | ✅ Complete |
| U-06 | HUD Redesign (Three-Pane Terminal UI) | Phase 4: Visual Identity | ✅ Complete |
| U-07 | UI & UX Fixes | Phase 4.1: Visual Polish | ✅ Complete |
| U-08 | Indexing Efficiency Upgrades | Phase 5: Performance | ✅ Complete |
| U-09 | Fast-Fail Fallback | Phase 2: Reliability | ✅ Complete |
| U-10 | Audit Log Export | Tier 3 | ✅ Complete |

---

## F-01 — Core LLM Connection (The Brain)
**User Story:** As a developer, I want a Python script that can securely connect to the Gemini API so that my assistant can process text and return intelligent responses.
**Acceptance Criteria:**
- [x] Python script uses the official SDK to send a prompt and receive a response.
- [x] API keys are loaded securely from a `.env` file (never hardcoded).
- [x] Includes a predefined "System Prompt" (e.g., "You are Lithe, a Data Science assistant").

## F-02 — Minimal Chat Interface (The Face)
**User Story:** As a user, I want a clean desktop window where I can type messages to the AI and read its responses, so I don't have to use a terminal.
**Acceptance Criteria:**
- [x] Electron wrapper spawns a secure, fixed-size desktop window.
- [x] React/TypeScript frontend renders a chat feed and a text input box.
- [x] Frontend communicates with the Python backend to send/receive messages.

## F-03 — Local Directory Indexer (The Memory)
**User Story:** As a user, I want the AI to map specific folders on my C: and D: drives so it knows where my files are without scanning my whole computer.
**Acceptance Criteria:**
- [x] A Python script takes a list of allowed directories (e.g., `D:\Projects`).
- [x] Script walks the directories and saves file paths and metadata to a local SQLite database.
- [x] Excludes `node_modules`, `.git`, and hidden system files to save compute.

## F-04 — RAG & File Context (Second Brain)
**User Story:** As a Data Science student, I want to ask questions about my local datasets or PDFs, and have the AI read them to give me an answer.
**Acceptance Criteria:**
- [x] When the user asks about a file, the AI queries the SQLite index (F-03) to find the file path.
- [x] The Python backend opens the file, reads the content, and appends it to the LLM prompt.
- [x] The AI generates an answer based *only* on the local file content.

## F-05 — Basic Task Execution (The Hands)
**User Story:** As a developer, I want to ask the AI to perform a simple task (like renaming a file or summarizing a CSV) and have it actually execute the code on my machine.
**Acceptance Criteria:**
- [x] Python backend registers basic tools using LLM Function Calling.
- [x] AI can decide to trigger a Python function based on the user's chat input.
- [x] User is asked for confirmation before any destructive action (like deleting or moving a file) occurs.

## F-06 — Candid Persona & Safeword Override
**User Story:** As a user, I want my AI to challenge my bad ideas and offer critical feedback rather than acting like a people-pleaser. However, I want a specific "safeword" that overrides this behavior when I need strict compliance.
**Acceptance Criteria:**
- [x] The Python backend's core system prompt strictly instructs the LLM to prioritize factual accuracy and critical feedback over politeness.
- [x] The AI must explicitly point out logic flaws or inefficiencies in the user's requests.
- [x] The system recognizes a hardcoded safeword (e.g., "Override Lithe").
- [x] When the safeword is present in the user's input, the AI drops all critical pushback, bypasses debate, and strictly executes the user's exact instructions.

## F-07 — Desktop Packaging (The Box)
**User Story:** As a developer, I want to distribute Lithe as a standalone Windows application that non-technical users can install and run without Python or Node.js.
**Acceptance Criteria:**
- [x] Python backend is compiled into a standalone `.exe` via PyInstaller.
- [x] Electron frontend + Python backend are packaged together using `electron-builder`.
- [x] NSIS installer is generated with Start Menu shortcut and uninstaller.
- [x] Application resolves `.env` and SQLite database from `%APPDATA%/Lithe` in production mode.

---

## U-01 — SQLite WAL Mode (Phase 1: Foundation & Safety)
**Rationale:** The background indexer writes to the database while the LLM reads from it concurrently. Without WAL, this causes "database is locked" errors.
**Implementation:**
- [x] `memory.py` executes `PRAGMA journal_mode=WAL;` on every connection.
- [x] `busy_timeout` set to 5000ms to handle brief contention gracefully.

## U-02 — Circuit Breakers for Tool Execution (Phase 1: Foundation & Safety)
**Rationale:** Prevents a poorly generated script from getting stuck in an infinite loop or modifying critical system files.
**Implementation:**
- [x] All OS tool operations wrapped in a 30-second hard timeout via `concurrent.futures`.
- [x] Path validation rejects empty paths, null bytes, and protected system directories (`C:\Windows`, `C:\Program Files`, etc.).
- [x] Paths normalized via `os.path.realpath()` to prevent symlink escapes.

## U-03 — Ollama Fallback Pattern (Phase 2: Reliability)
**Rationale:** Cloud models are highly capable but are at the mercy of rate limits and internet connections. Lithe must work offline.
**Implementation:**
- [x] If Gemini encounters a network drop or API error, the code catches the error and routes to a local Ollama model.
- [x] Dedicated `_ollama_chat()` function with proper `/api/chat` message roles (system + user).
- [x] `_check_ollama_available()` health check before attempting fallback.
- [x] Configurable via `.env`: `OLLAMA_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`.
- [x] Uses `httpx` for HTTP requests (replaced `urllib`).

## U-04 — Event-Driven Memory (Phase 3: Efficiency & Context)
**Rationale:** Full directory scans on startup cause massive boot delays as datasets and repositories grow.
**Implementation:**
- [x] OS-level file watcher via `watchdog` library, scoped to whitelisted directories.
- [x] 1-second debouncing to handle rapid IDE saves (temp file → rename patterns).
- [x] Automatically updates SQLite when files are created, modified, deleted, or moved.
- [x] Respects the same `EXCLUDED_DIRS` filter as the indexer for consistency.

## U-05 — Heuristic Graph (Phase 3: Efficiency & Context)
**Rationale:** Pure vector search (RAG) struggles to understand how local code files relate to one another. Folder-based heuristics provide instant semantic context.
**Implementation:**
- [x] `heuristics.py` — pure-function engine with 15+ folder pattern rules and 20+ extension rules.
- [x] Schema migration adds `category` column to the `files` table.
- [x] `indexer.py` applies category tags during `walk_and_index()`.
- [x] `watcher.py` applies category tags on real-time file events.
- [x] `search_files` LLM tool displays `[category]` tags in search results.

## U-06 — HUD Redesign (Phase 4: Visual Identity)
**Rationale:** Lithe is a local, developer-facing tool that reads file systems and executes code. The UI should reflect that — terminal-inspired, not consumer chatbot. Replaces the glassmorphism theme with an amber/HUD console aesthetic.
**Implementation:**
- [x] **CSS Design System:** Full replacement of `index.css` — amber accent (`#ffb020`), near-black palette (`#08080a`), JetBrains Mono monospace stack, 0–2px border-radius, flat 1px hairline borders, no gradients/blur/glow.
- [x] **Three-Pane Layout:** `[01] INDEX` (left, 220px) + `[02] CHAT` (center, flex) + `[03] SYSTEM` (bottom strip, full-width).
- [x] **IndexPanel:** New component showing watched directories with file counts, watcher live/stopped status, last event time.
- [x] **SystemPanel:** New component showing server health dot, candid/compliant mode, safeword indicator (violet when active), token count placeholder.
- [x] **Terminal Messages:** Replaced bubble paradigm with `user>` / `lithe>` prefix style, flat text, no rounded cards.
- [x] **Boot Screen:** Welcome screen restyled as init/boot log sequence with blinking cursor.
- [x] **Command-Line Input:** Input styled with `>` prompt prefix, amber caret, flat `[SEND]` button.
- [x] **Status API:** Added `GET /api/status` endpoint + `get_file_count_by_directory()` + `last_event_time` watcher state.
- [x] **Font:** Swapped Inter → JetBrains Mono via Google Fonts.
- [x] **Electron Window:** Background updated to `#08080a`, resizable with min 900×600, default 1100×720.

## U-07 — UI & UX Fixes (Phase 4.1: Visual Polish & Control)
**Rationale:** The initial HUD redesign lacked interactivity for the whitelist, executed mutating tools blindly without user confirmation, and had minor styling issues.
**Implementation:**
- [x] **Dynamic Whitelist Picker:** Replaced hardcoded `INDEX_WHITELIST` array with a dynamic UI in the `[01] INDEX` panel. Added `+ INDEX` native folder picker, manual text input, and `×` removal buttons.
- [x] **Unified Tool Confirmation UX:** Intercepted file-mutating LLM tool calls (`write_file`, `delete_file`, `rename_file`) in `brain.py` and paused execution.
- [x] **Diff Card Rendering:** `ToolProposalCard.tsx` component renders diff strings for tool proposals, allowing the user to ACCEPT or REJECT before execution resumes.
- [x] **Semantic Color Fixes:** Fixed `--success` drift in chat (green is only for actual success events, standard text uses `--text-dim` or `--text`).
- [x] **Live Token Telemetry:** `brain.py` extracts LLM token usage metadata, passed through `/api/status` to populate the `[03] SYSTEM` panel.
- [x] **Live Watcher Log Console:** Created `broadcaster.py` to stream indexing/removal events. Exposed `/ws/watcher-log` WebSocket in `server.py` with 100ms batching and a 500-event history ring buffer. Built an expandable `system-log-drawer` in `SystemPanel.tsx` with autoscroll, filtering, and 1000-line DOM cap.

## U-08 — Indexing Efficiency Upgrades (Phase 5: Performance)
**Rationale:** A full re-walk and database upsert of 141k+ files on every boot creates redundant I/O and CPU spikes. Furthermore, users need a way to filter out heavy binary extensions (like `.dll`, `.exe`) that pollute the LLM's context.
**Implementation:**
- [x] **Smart Extension Filtering (Backend):** Default `EXCLUDED_EXTENSIONS` master list implemented to block heavy binaries/bloatware out of the box, with persistence in `.env`. Respected by `indexer.py` and `watcher.py` (via `_is_excluded`).
- [x] **Smart Extension Filtering (Frontend):** Extension exclusion UI in `IndexPanel.tsx` renders strictly inline using Flexbox with a fixed-height scrollable container to gracefully handle the large default tag list.
- [x] **Startup Reconciliation:** `indexer.py` fetches all indexed files (`{path: modified_at}`) from SQLite before walking. Skips DB upserts for unchanged files. Cleans up missing or newly excluded files automatically.
- [x] **Summarized Logging:** Startup bulk scans now print a single reconciliation summary (e.g., `reconciled: 12 new/modified, 3 removed, 141074 unchanged`) instead of streaming events. Live watcher events are unaffected.

## U-08.1 — Minor Bugfixes & Guardrail Hardening
**Rationale:** The LLM was occasionally hallucinating instead of using the local RAG tools and ignoring C:\ drive scan restrictions in edge cases.
**Implementation:**
- [x] **Enforced RAG Pipeline:** Updated `CANDID_SYSTEM_PROMPT` and `search_files` docstring in `brain.py` to strictly mandate using the database search tool when asked about user files or keywords.
- [x] **Hard Guardrails:** Appended a strict refusal condition to the system prompt to universally block recursive root drive scans (e.g., `C:\`) without providing code workarounds, unless overridden by the safeword.

## U-09 — Fast-Fail Fallback & Active Engine Telemetry
**Rationale:** The Gemini API fallback logic was taking too long (60s) to route to Ollama when offline, and the UI lacked transparency about which compute engine generated the response.
**Implementation:**
- [x] **Fast-Fail Fallback (Backend):** Enforced a strict 5.0-second timeout in `brain.py`'s `genai.Client(http_options={'timeout': 5.0})` to instantly route failed connections to local compute.
- [x] **Active Engine Telemetry (Full Stack):** Injected a global `active_engine` tracker into `brain.py`, exposed via `/api/status`, and dynamically rendered an inline `[Engine: Gemini]` or blue `[Engine: Ollama (Local)]` indicator into the header of `SystemPanel.tsx`.

## U-10 — Audit Log Export (Tier 3)
**Rationale:** The user requires a structured way to export all AI decisions, proposed tools, execution results, and conversation context for auditing and review, expanding the existing Undo Stack's `action_history` table without breaking it.
**Implementation:**
- [x] **Database Migration:** Extended `action_history` in `memory.py` with `decision_outcome`, `execution_result`, and `conversation_id`.
- [x] **Tool Wrappers:** Modified `tools.py` and `brain.py` to record non-mutating actions (like `search_files`) and rejected/failed operations, distinguishing them from successful mutating tools used by the Undo Stack.
- [x] **REST API:** Added `GET /api/audit/export` endpoint in `server.py` supporting `application/json` and `text/csv` formats, with ISO date range filtering (`from` and `to`).
- [x] **HUD UI:** Added an inline `[↓ audit]` toggle in `SystemPanel.tsx` to configure format, pick dates, and trigger a Blob download with error handling for malformed requests.