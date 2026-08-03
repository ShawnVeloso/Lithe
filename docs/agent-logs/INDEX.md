# Lithe — Agent Log Index

> **Purpose:** Persistent state-tracking for AI agents and the lead developer.
> **Last Updated:** 2026-08-03T22:52 (PHT)

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
| [requirements.txt](file:///d:/Lithe/requirements.txt) | `google-genai`, `python-dotenv`, `fastapi`, `uvicorn[standard]` |

### Python Backend (`src/backend/`)

| File | Feature | Purpose |
|------|---------|---------|
| [\_\_init\_\_.py](file:///d:/Lithe/src/__init__.py) | — | Root package init |
| [backend/\_\_init\_\_.py](file:///d:/Lithe/src/backend/__init__.py) | — | Backend package init |
| [config.py](file:///d:/Lithe/src/backend/config.py) | F-01 | Loads `GEMINI_API_KEY` from `.env`, fails fast if missing; exposes `GEMINI_MODEL` |
| [brain.py](file:///d:/Lithe/src/backend/brain.py) | F-01 + F-06 | `chat(user_message) → str` — Gemini client, safeword detection, persona toggle |
| [server.py](file:///d:/Lithe/src/backend/server.py) | F-02+F-03 | FastAPI on `localhost:8321` — `POST /api/chat`, `GET /api/health`, `POST /api/index` |
| [memory.py](file:///d:/Lithe/src/backend/memory.py) | F-03 | SQLite database initialization and schema, `upsert_files()` |
| [indexer.py](file:///d:/Lithe/src/backend/indexer.py) | F-03 | `walk_and_index()` using `os.walk` with strict directory exclusions |
| [retrieval.py](file:///d:/Lithe/src/backend/retrieval.py) | F-04 | Extracts file mentions, resolves via SQLite, and reads local file content |
| [tools.py](file:///d:/Lithe/src/backend/tools.py) | F-05 | System-level functions (`rename_file`, `delete_file`) with safeword checking |
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
| `GEMINI_MODEL` | `config.py` | `gemini-2.5-flash` |
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

**Next Step:** Verify the installer works across different Windows environments and consider setting up an auto-updater.

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

