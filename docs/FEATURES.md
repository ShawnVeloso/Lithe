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