# Lithe — Agent Log Index

> **Purpose:** Persistent state-tracking for AI agents and the lead developer.
> **Last Updated:** 2026-08-04T14:28 (PHT)

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

---

## Generated Boilerplate — File Manifest

### Project Root

| File | Purpose |
|------|---------|
| [.gitignore](file:///d:/Lithe/.gitignore) | Python, Node, Electron, `.env`, SQLite, OS artifact exclusions |
| [.env.example](file:///d:/Lithe/.env.example) | Template documenting `GEMINI_API_KEY` |
| [requirements.txt](file:///d:/Lithe/requirements.txt) | `google-genai`, `python-dotenv`, `fastapi`, `uvicorn[standard]`, `watchdog` |

### Python Backend (`src/backend/`)

| File | Feature | Purpose |
|------|---------|---------|
| [\_\_init\_\_.py](file:///d:/Lithe/src/__init__.py) | — | Root package init |
| [backend/\_\_init\_\_.py](file:///d:/Lithe/src/backend/__init__.py) | — | Backend package init |
| [config.py](file:///d:/Lithe/src/backend/config.py) | F-01 | Loads `GEMINI_API_KEY` from `.env`, fails fast if missing; exposes `GEMINI_MODEL`, Ollama fallback config |
| [brain.py](file:///d:/Lithe/src/backend/brain.py) | F-01 + F-06 | `chat(user_message) → str` — Gemini client, Ollama fallback, safeword detection, persona toggle |
| [server.py](file:///d:/Lithe/src/backend/server.py) | F-02+F-03 | FastAPI on `localhost:8321` — `POST /api/chat`, `GET /api/health`, `POST /api/index`; starts watcher on boot |
| [memory.py](file:///d:/Lithe/src/backend/memory.py) | F-03 | SQLite database initialization, schema with `category` column, `upsert_files()`, `delete_file_by_path()` |
| [indexer.py](file:///d:/Lithe/src/backend/indexer.py) | F-03 | `walk_and_index()` using `os.walk` with strict exclusions and heuristic category tagging |
| [heuristics.py](file:///d:/Lithe/src/backend/heuristics.py) | Phase 3 | `categorize_path()` — maps folder patterns + extensions to semantic category tags |
| [watcher.py](file:///d:/Lithe/src/backend/watcher.py) | Phase 3 | Real-time file system watcher via `watchdog`; debounced events, auto-updates SQLite |
| [retrieval.py](file:///d:/Lithe/src/backend/retrieval.py) | F-04 | Extracts file mentions, resolves via SQLite, and reads local file content |
| [tools.py](file:///d:/Lithe/src/backend/tools.py) | F-05 | System-level functions (`rename_file`, `delete_file`) with circuit breakers and safeword checking |
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
| [src/main/index.ts](file:///d:/Lithe/src/frontend/src/main/index.ts) | Electron main process — fixed 1000×700 window, spawns/kills Python server |
| [src/preload/index.ts](file:///d:/Lithe/src/frontend/src/preload/index.ts) | `litheAPI.chat()` + `litheAPI.healthCheck()` via contextBridge |
| [src/renderer/index.html](file:///d:/Lithe/src/frontend/src/renderer/index.html) | HTML shell, Inter font, React mount point |
| [src/renderer/src/main.tsx](file:///d:/Lithe/src/frontend/src/renderer/src/main.tsx) | React entry point |
| [src/renderer/src/App.tsx](file:///d:/Lithe/src/frontend/src/renderer/src/App.tsx) | Chat shell — message state, health polling, error handling |
| [src/renderer/src/env.d.ts](file:///d:/Lithe/src/frontend/src/renderer/src/env.d.ts) | TypeScript declarations for `window.litheAPI` |
| [src/renderer/src/index.css](file:///d:/Lithe/src/frontend/src/renderer/src/index.css) | Design system — dark navy, glassmorphism, gradients, animations |
| [src/renderer/src/components/ChatWindow.tsx](file:///d:/Lithe/src/frontend/src/renderer/src/components/ChatWindow.tsx) | Scrollable message feed, welcome screen, typing indicator |
| [src/renderer/src/components/MessageBubble.tsx](file:///d:/Lithe/src/frontend/src/renderer/src/components/MessageBubble.tsx) | Role-based message cards (user gradient / assistant glass) |
| [src/renderer/src/components/ChatInput.tsx](file:///d:/Lithe/src/frontend/src/renderer/src/components/ChatInput.tsx) | Auto-resizing textarea, Enter to send, disabled during loading |

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

---

## Key Configuration

| Variable | Source | Value |
|----------|--------|-------|
| `GEMINI_API_KEY` | `.env` file | User-provided |
| `GEMINI_MODEL` | `config.py` | `gemini-3.6-flash` |
| `OLLAMA_URL` | `.env` / default | `http://localhost:11434` |
| `OLLAMA_MODEL` | `.env` / default | `llama3` |
| `OLLAMA_TIMEOUT` | `.env` / default | `60` seconds |
| `SAFEWORD` | `system_prompt.py` | `"Override Lithe"` |
| Python server port | `server.py` | `8321` |
| Electron window | `main/index.ts` | 1000×700, non-resizable |

---

## Immediate Next Steps

### Milestone Achieved
All F-01 through F-06 roadmap features have been successfully implemented. 

Lithe is now a fully functional, permissioned local desktop assistant capable of:
1. Responding via the Gemini LLM (F-01).
2. Interacting through a premium Electron+React Chat UI (F-02).
3. Maintaining an SQLite index of whitelisted local directories (F-03).
4. Reading local files on demand using regex-based extraction (F-04).
5. Executing system tasks (rename, delete) via function calling (F-05).
6. Enforcing a candid persona and strict safeword-gated permission protocols (F-06).

**Next Step:** All UPGRADE_PLAN phases (1-3) are complete. Consider packaging the updated backend with PyInstaller and verifying the installer.

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

