# Lithe — Agent Log Index

start here

> **Purpose:** Persistent state-tracking for AI agents and the lead developer.
> **Last Updated:** 2026-08-09T22:10 (PHT)

---

## Project Status Overview

| Feature | Status | Notes |
|---------|--------|-------|
| **F-01** — Core LLM Connection | ✅ Complete | Gemini API via `google-genai`, env-var loaded |
| **F-02** — Minimal Chat Interface | ✅ Complete | Electron + React, electron-vite, FastAPI bridge |
| **F-03** — Local Directory Indexer | ✅ Complete | SQLite + whitelisted directory crawling |
| **F-04** — RAG & File Context | ✅ Complete | Regex extraction, SQLite lookup, context injection |
| **F-05** — Basic Task Execution | ✅ Complete | LLM Function Calling with dynamic safeword wrappers |
| **F-06** — Candid Persona & Safeword | ✅ Complete | Dual system prompts, case-insensitive safeword |
| **F-07** — Desktop Packaging | ✅ Complete | PyInstaller backend + electron-builder NSIS installer |
| **UPGRADE Phase 1** — Foundation & Safety | ✅ Complete | SQLite WAL mode, circuit breakers with path validation & timeouts |
| **UPGRADE Phase 2** — Reliability | ✅ Complete | Ollama fallback with health check, configurable model/URL/timeout |
| **UPGRADE Phase 3** — Efficiency & Context | ✅ Complete | Real-time file watcher (watchdog), heuristic category tagging |

---

## Generated Boilerplate — File Manifest

### Project Root

| File | Purpose |
|------|---------|
| [.gitignore](file:///d:/Lithe/.gitignore) | Python, Node, Electron, `.env`, SQLite, OS artifact exclusions |
| [.env.example](file:///d:/Lithe/.env.example) | Template documenting `GEMINI_API_KEY`, `INDEX_WHITELIST`, Ollama config |
| [requirements.txt](file:///d:/Lithe/requirements.txt) | `google-genai`, `python-dotenv`, `fastapi`, `uvicorn[standard]`, `watchdog`, `httpx` |

### Python Backend (`src/backend/`)

| File | Feature | Purpose |
|------|---------|---------|
| [\_\_init\_\_.py](file:///d:/Lithe/src/__init__.py) | — | Root package init |
| [backend/\_\_init\_\_.py](file:///d:/Lithe/src/backend/__init__.py) | — | Backend package init |
| [config.py](file:///d:/Lithe/src/backend/config.py) | F-01 + Phase 2 | Loads `GEMINI_API_KEY` from `.env`, fails fast if missing; exposes `GEMINI_MODEL`, Ollama fallback config (`OLLAMA_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`), `DB_PATH`, `INDEX_WHITELIST`; supports 3-tier .env resolution (AppData → exe-adjacent → project root) |
| [brain.py](file:///d:/Lithe/src/backend/brain.py) | F-01 + F-05 + F-06 + Phase 2 | `chat(user_message) → str` — Gemini client, function calling loop (rename, delete, search_files), safeword-gated tool wrappers, Ollama fallback via `_ollama_chat()` |
| [server.py](file:///d:/Lithe/src/backend/server.py) | F-02 + F-03 + Phase 3 | FastAPI on `localhost:8321` — `POST /api/chat`, `GET /api/health`, `POST /api/index`; auto-indexes then starts file watcher on boot |
| [server_entry.py](file:///d:/Lithe/src/backend/server_entry.py) | F-07 | PyInstaller entry point — standalone `.env` resolution for packaged mode |
| [memory.py](file:///d:/Lithe/src/backend/memory.py) | F-03 + Phase 1 + Phase 3 | SQLite DB init with WAL mode + busy_timeout, schema with `category` column, `upsert_files()`, `delete_file_by_path()`, `find_file_paths()`, `search_files_by_name()` |
| [indexer.py](file:///d:/Lithe/src/backend/indexer.py) | F-03 + Phase 3 | `walk_and_index()` using `os.walk` with strict exclusions, heuristic category tagging, batch upsert |
| [heuristics.py](file:///d:/Lithe/src/backend/heuristics.py) | Phase 3 | `categorize_path()` — maps 15+ folder patterns and 20+ extension rules to semantic category tags |
| [watcher.py](file:///d:/Lithe/src/backend/watcher.py) | Phase 3 | Real-time file system watcher via `watchdog`; debounced events (1s), auto-updates SQLite on create/modify/delete/move |
| [retrieval.py](file:///d:/Lithe/src/backend/retrieval.py) | F-04 | Extracts file mentions via regex, resolves via SQLite, reads local file content (100KB cap) |
| [tools.py](file:///d:/Lithe/src/backend/tools.py) | F-05 + Phase 1 | System-level functions (`rename_file`, `delete_file`) with circuit breakers: path validation (empty, null bytes, protected system dirs), path normalization (`realpath`), 30-second timeout wrapper via `concurrent.futures` |
| [prompts/\_\_init\_\_.py](file:///d:/Lithe/src/backend/prompts/__init__.py) | — | Prompts package init |
| [prompts/system_prompt.py](file:///d:/Lithe/src/backend/prompts/system_prompt.py) | F-06 | `CANDID_SYSTEM_PROMPT`, `COMPLIANT_SYSTEM_PROMPT`, `SAFEWORD`, `detect_safeword()` |

### Electron Frontend (`src/frontend/`)

| File | Purpose |
|------|---------|
| [package.json](file:///d:/Lithe/src/frontend/package.json) | Deps: Electron 36, React 19, electron-vite 3, TypeScript 5 |
| [electron.vite.config.ts](file:///d:/Lithe/src/frontend/electron.vite.config.ts) | Build config for main, preload, and renderer |
| [tsconfig.json](file:///d:/Lithe/src/frontend/tsconfig.json) | Root TS config (references node + web) |
| [tsconfig.node.json](file:///d:/Lithe/src/frontend/tsconfig.node.json) | TS config for main + preload |
| [tsconfig.web.json](file:///d:/Lithe/src/frontend/tsconfig.web.json) | TS config for React renderer |
| [src/main/index.ts](file:///d:/Lithe/src/frontend/src/main/index.ts) | Electron main process — fixed 1000×700 window, spawns/kills Python server, dev/prod path resolution |
| [src/preload/index.ts](file:///d:/Lithe/src/frontend/src/preload/index.ts) | `litheAPI.chat()` + `litheAPI.healthCheck()` via contextBridge |
| [src/renderer/index.html](file:///d:/Lithe/src/frontend/src/renderer/index.html) | HTML shell, Inter font, React mount point |
| [src/renderer/src/main.tsx](file:///d:/Lithe/src/frontend/src/renderer/src/main.tsx) | React entry point |
| [src/renderer/src/App.tsx](file:///d:/Lithe/src/frontend/src/renderer/src/App.tsx) | Chat shell — message state, health polling (10s), error handling |
| [src/renderer/src/env.d.ts](file:///d:/Lithe/src/frontend/src/renderer/src/env.d.ts) | TypeScript declarations for `window.litheAPI` |
| [src/renderer/src/index.css](file:///d:/Lithe/src/frontend/src/renderer/src/index.css) | Design system — dark navy, glassmorphism, gradients, micro-animations |
| [src/renderer/src/components/ChatWindow.tsx](file:///d:/Lithe/src/frontend/src/renderer/src/components/ChatWindow.tsx) | Scrollable message feed, welcome screen, typing indicator |
| [src/renderer/src/components/MessageBubble.tsx](file:///d:/Lithe/src/frontend/src/renderer/src/components/MessageBubble.tsx) | Role-based message cards (user gradient / assistant glass) |
| [src/renderer/src/components/ChatInput.tsx](file:///d:/Lithe/src/frontend/src/renderer/src/components/ChatInput.tsx) | Command-line style input with `>` prompt, monospace, flat `[SEND]` button |
| [src/renderer/src/components/IndexPanel.tsx](file:///d:/Lithe/src/frontend/src/renderer/src/components/IndexPanel.tsx) | [01] INDEX HUD panel — watched dirs, file counts, watcher status, last event |
| [src/renderer/src/components/SystemPanel.tsx](file:///d:/Lithe/src/frontend/src/renderer/src/components/SystemPanel.tsx) | [03] SYSTEM HUD strip — server health, mode, safeword indicator, token placeholder |

---

## Architecture Summary

```
User → ChatInput → App.tsx state → window.litheAPI.chat()
       → preload (contextBridge) → POST localhost:8321/api/chat
       → FastAPI server.py → brain.chat() → Gemini API
       → response bubbles back through the same chain
```

- **Renderer** has zero access to `electron` or `node` — all backend calls go through `contextBridge`.
- **Electron main** spawns the Python server as a child process and polls `/api/health` before showing the window.
- **Safeword** (`"Override Lithe"`, case-insensitive) toggles the system prompt per-message.
- **Ollama Fallback:** When Gemini fails (network, rate limit, API error), `brain.py` automatically routes the prompt to a local Ollama instance.
- **File Watcher:** On server startup, the indexer runs a full crawl of `INDEX_WHITELIST`, then `watchdog` begins real-time monitoring for create/modify/delete/move events.
- **Heuristic Graph:** Every indexed file receives a semantic category tag (e.g., "Backend Logic", "Data / Datasets") based on its folder path and extension.

---

## Key Configuration

| Variable | Source | Value |
|----------|--------|-------|
| `GEMINI_API_KEY` | `.env` file | User-provided |
| `GEMINI_MODEL` | `config.py` | `gemini-3.6-flash` |
| `OLLAMA_URL` | `.env` / default | `http://localhost:11434` |
| `OLLAMA_MODEL` | `.env` / default | `llama3` |
| `OLLAMA_TIMEOUT` | `.env` / default | `60` seconds |
| `INDEX_WHITELIST` | `.env` | Comma-separated directories (currently: `D:\`) |
| `SAFEWORD` | `system_prompt.py` | `"Override Lithe"` |
| Python server port | `server.py` | `8321` |
| Electron window | `main/index.ts` | 1000×700, non-resizable |
| SQLite DB (dev) | `config.py` | `<project_root>/.lithe/lithe_memory.db` |
| SQLite DB (prod) | `config.py` | `%APPDATA%/Lithe/lithe_memory.db` |

---

## Running the App

### Development Mode
```bash
# Terminal 1: Start the Python backend
cd d:\Lithe
python -m src.backend.server

# Terminal 2: Start the Electron frontend
cd d:\Lithe\src\frontend
npm run dev
```

### Production Mode
- Install via `D:\Lithe\src\frontend\release\Lithe Setup 1.0.0.exe`
- Launch from Start Menu → "Lithe"

---

## Immediate Next Steps

### Milestone Achieved
All F-01 through F-06 roadmap features AND all UPGRADE_PLAN phases (1–3) are complete.

Lithe is now a fully functional, permissioned local desktop assistant with:
1. Gemini LLM with configurable Ollama offline fallback (F-01 + Phase 2)
2. Premium Electron+React Chat UI (F-02)
3. SQLite index with WAL mode for concurrent access (F-03 + Phase 1)
4. RAG via regex-based file extraction (F-04)
5. Function calling with circuit-breaker safety (F-05 + Phase 1)
6. Candid persona with safeword gating (F-06)
7. Real-time file watching and heuristic category tagging (Phase 3)
8. Standalone Windows installer (F-07)

### Suggested Next Directions (Pick One)
1. **Re-package** the updated backend with PyInstaller and rebuild the NSIS installer to include all Phase 1–3 upgrades.
2. **Chat History Persistence** — Save conversations to SQLite so they survive app restarts.
3. **Streaming Responses** — Token-by-token output in the UI via Server-Sent Events instead of waiting for the full response.
4. **Markdown Rendering** — Render code blocks, bold, lists, and other formatting in assistant chat bubbles.
5. **Settings Panel** — In-app UI for managing API keys, whitelist directories, and toggling Ollama.

---

## Log Entries

| Date | Agent | Action |
|------|-------|--------|
| 2026-07-11 | Antigravity | Scaffolded project directory structure |
| 2026-07-11 | Antigravity | Implemented F-01 (Core LLM Connection) |
| 2026-07-11 | Antigravity | Implemented F-06 (Candid Persona & Safeword) |
| 2026-07-11 | Antigravity | Implemented F-02 (Minimal Chat Interface) |
| 2026-07-11 | Antigravity | Created `docs/agent-logs/INDEX.md` |
| 2026-07-12 | Antigravity | Implemented F-03 (Local Directory Indexer) |
| 2026-07-12 | Antigravity | Implemented F-04 (RAG & File Context) |
| 2026-08-03 | Antigravity | Updated outdated documentation states |
| 2026-08-03 | Antigravity | Implemented Customization Rules for AI Agents (.agents/AGENTS.md) |
| 2026-08-07 | AntiGravity | Fixed Gemini timeout issue (removed hardcoded 5s limit) & refactored tool schema to fix 400 Bad Request errors. |
| 2026-08-08 | AntiGravity | Fixed Lithe hallucinating tool execution by adding `disable=True` to `AutomaticFunctionCallingConfig` in `brain.py`. Found that the new `google.genai` SDK was auto-executing Python tools under the hood, silently bypassing `ToolProposalCard` UI interception and creating files directly. Also added `[TOOL EXECUTED]` log lines to `tools.py` for auditability, and patched `COMPLIANT_SYSTEM_PROMPT` to properly route tool instructions during safeword mode. |
| 2026-08-03 | Antigravity | Fixed Gemini timeout — removed broken custom http_options from GenerateContentConfig; SDK defaults work correctly |
| 2026-08-03 | Antigravity | Added auto-indexing on server startup in server.py — no more manual POST /api/index needed |
| 2026-08-03 | Antigravity | Added search_files LLM tool (memory.py + brain.py) — fuzzy file search by keyword via function calling |
| 2026-08-03 | Antigravity | Packaged Lithe as a standalone Windows desktop app using PyInstaller and electron-builder (F-07) |
| 2026-08-03 | Antigravity | Generated a comprehensive feature rundown document in `personal saved copies/Lithe_Features.md` |
| 2026-08-04 | Antigravity | **UPGRADE Phase 1.1:** Enabled SQLite WAL mode + busy_timeout in `memory.py` — prevents "database is locked" errors from concurrent indexer/LLM access |
| 2026-08-04 | Antigravity | **UPGRADE Phase 1.2:** Added circuit breakers to `tools.py` — path validation (empty, null bytes, protected system dirs), path normalization (`realpath`), and 30-second timeout wrapper via `concurrent.futures` |
| 2026-08-04 | Antigravity | Minor: Added `TypeError` catch in `brain.py` function calling handler for malformed LLM arguments |
| 2026-08-04 | Antigravity | **UPGRADE Phase 2:** Refactored Ollama fallback in `brain.py` — dedicated `_ollama_chat()` function, `_check_ollama_available()` health check, httpx client (replaced urllib), Ollama `/api/chat` with proper message roles |
| 2026-08-04 | Antigravity | **UPGRADE Phase 2:** Added configurable Ollama settings to `config.py` (`OLLAMA_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`) and documented them in `.env.example` |
| 2026-08-04 | Antigravity | **UPGRADE Phase 3.4:** Created `heuristics.py` — pure-function engine mapping 15+ folder patterns and 20+ extension rules to semantic category tags |
| 2026-08-04 | Antigravity | **UPGRADE Phase 3.4:** Schema migration in `memory.py` — added `category` column, `delete_file_by_path()` function, updated upsert/search queries |
| 2026-08-04 | Antigravity | **UPGRADE Phase 3.4:** Created `watcher.py` — `watchdog`-based real-time file watcher with 1s debouncing, EXCLUDED_DIRS filtering, auto SQLite updates |
| 2026-08-04 | Antigravity | **UPGRADE Phase 3.4:** Updated `indexer.py` to apply heuristic category tags during `walk_and_index()` |
| 2026-08-04 | Antigravity | **UPGRADE Phase 3.4:** Updated `server.py` startup — runs initial index then starts file watcher |
| 2026-08-04 | Antigravity | **UPGRADE Phase 3.5:** Updated `brain.py` — `search_files` tool now shows `[category]` tags in results |
| 2026-08-06 | Antigravity | **Documentation Audit:** Full sync of INDEX.md, FEATURES.md, and ARCHITECTURE.md — added UPGRADE Phase statuses, updated file manifest, added running instructions, expanded architecture notes, defined suggested next directions |
| 2026-08-07 | Antigravity | **HUD Redesign — Backend:** Added `GET /api/status` endpoint to `server.py`, `get_file_count_by_directory()` to `memory.py`, exposed `last_event_time` in `watcher.py` — all read-only, feeds the new HUD panels |
| 2026-08-07 | Antigravity | **HUD Redesign — Preload/Types:** Added `litheAPI.getStatus()` to preload API and `StatusResponse` to `env.d.ts` |
| 2026-08-07 | Antigravity | **HUD Redesign — CSS:** Full replacement of `index.css` — amber accent, near-black palette, JetBrains Mono monospace stack, 0-2px radii, hairline borders, three-pane HUD grid layout |
| 2026-08-07 | Antigravity | **HUD Redesign — Components:** Rebuilt `App.tsx` as three-pane HUD orchestrator, created `IndexPanel.tsx` and `SystemPanel.tsx`, restyled `ChatWindow.tsx` (boot screen + cursor indicator), `MessageBubble.tsx` (terminal prefixes), `ChatInput.tsx` (command-line style) |
| 2026-08-07 | Antigravity | **HUD Redesign — Electron:** Updated `main/index.ts` — `backgroundColor: #08080a`, enabled resizing (min 900×600), default 1100×720 |
| 2026-08-07 | Antigravity | **HUD Redesign — Font:** Swapped `index.html` from Inter to JetBrains Mono Google Font |
| 2026-08-07 | Antigravity | **UI Fixes — Whitelist Picker:** Replaced blind full-drive indexing with a dynamic whitelist picker in `IndexPanel.tsx`, added `+ INDEX` and text input, exposed via `dialog.showOpenDialog` in main, updated `watcher.py` and `indexer.py` to handle dynamic watch/index adding. |
| 2026-08-07 | Antigravity | **UI Fixes — Unified Tool Confirmation UX:** Intercepted mutating LLM tool calls (`write_file`, `delete_file`, `rename_file`) in `brain.py` to pause execution and send a `tool_proposal` to the frontend. Implemented `ToolProposalCard.tsx` with diffs and ACCEPT/REJECT buttons. |
| 2026-08-07 | Antigravity | **UI Fixes — Semantic Colors:** Fixed `--success` drift in chat, re-colored `lithe>` prefix to `--text-dim`. |
| 2026-08-07 | Antigravity | **UI Fixes — System Panel:** Added `[03] SYSTEM` header to match conventions, extracted live LLM token counts in `brain.py`, and piped to `SystemPanel.tsx` via `/api/status`. |
| 2026-08-07 | Antigravity | **Live Watcher Log Console:** Created `broadcaster.py` to stream indexing/removal events. Exposed `/ws/watcher-log` WebSocket in `server.py` with 100ms batching and a 500-event history ring buffer. Built an expandable `system-log-drawer` in `SystemPanel.tsx` with autoscroll, filtering, and 1000-line DOM cap. |
| 2026-08-07 | Antigravity | **UI Fixes — Themed Title Bar:** Added `titleBarStyle: 'hidden'` and `titleBarOverlay` to `index.ts`. Replaced default header with draggable custom title bar in `App.tsx` and `index.css`. Upgraded brand logo with `lithe-mark-hero.svg` and `icon.ico`. Fixed `[01] INDEX`'s `last event` missing updates by lifting WebSocket to `App.tsx`. Fixed port binding conflict by pinging server health before spawning `pythonProcess`. |
| 2026-08-08 | Antigravity | **Bugfix:** Injected strict tool execution rules into `system_prompt.py` to prevent text-based confirmation loops. Fixed context-dropping issue by implementing a global `_chat_history` list in `brain.py` to maintain standard conversational context across API requests. |
| 2026-08-09 | Antigravity | **Feature 1:** Added `src/backend/changelog.py` script and a startup hook in `server.py` to auto-generate `CHANGELOG.md` at the project root based on this index file. |
| 2026-08-09 | Antigravity | **Feature 2:** Added UI toggle in `SystemPanel.tsx` for a global session override safeword mode. Added `/api/config/safeword` endpoint in `server.py` and state in `brain.py` to track and enforce it without requiring the phrase per-message. |
| 2026-08-09 | Antigravity | **Feature 3:** Added search input to `IndexPanel.tsx` calling `search_files_by_name()` from `memory.py` via a new `/api/search` endpoint in `server.py` to render file paths inline directly. |
| 2026-08-09 | Antigravity | **Bugfix:** Fixed `NameError: name 'brain' is not defined` in `GET /api/status` — replaced individual-name import (`from src.backend.brain import ...`) with module import (`import src.backend.brain as brain`) to match the pattern used by `toggle_safeword`. |
| 2026-08-09 | Antigravity | **Feature 1 (Tier 2):** Added token budget indicator. Configured `TOKEN_BUDGET_WARNING` in `config.py` (default 1.5M), exposed it via `/api/status`, and styled the `tokens` readout in `SystemPanel.tsx` to turn amber (`system-stat__value--accent`) when the budget is exceeded. |
