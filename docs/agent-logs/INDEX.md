# Lithe — Agent Log Index

> **Purpose:** Persistent state-tracking for AI agents and the lead developer.
> **Last Updated:** 2026-08-31T20:10 (PHT)

---

## Current Focus
- **Working on:** Markdown rendering fix + ack_auto_summaries newline bugfix
- **Next up:** TBD
- **Then:** TBD
- **Blocked on:** nothing

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
| **Watch-and-Summarize** — Segment 1 (Storage) | ✅ Complete | `watch_rules` table + 3 LLM tools (create/list/delete) |
| **Watch-and-Summarize** — Segment 2 (Logic) | ✅ Complete | Background summarization trigger, glob matching |
| **Watch-and-Summarize** — Segment 3 (Chat) | ✅ Complete | Auto-summary delivery via WebSocket, UI injection |
| **System Tray & Global Hotkey** | ✅ Complete | Windows tray icon and Ctrl+Shift+L hotkey |

---

## Key Configuration

| Variable | Source | Value |
|----------|--------|-------|
| `GEMINI_API_KEY` | `.env` file | User-provided |
| `GEMINI_MODEL` | `config.py` | `gemini-3.6-flash` |
| `OLLAMA_URL` | `.env` / default | `http://localhost:11434` |
| `OLLAMA_MODEL` | `.env` / default | `llama3.1` |
| `OLLAMA_TIMEOUT` | `.env` / default | `60` seconds |
| `INDEX_WHITELIST` | `.env` | Comma-separated directories (e.g. `D:\`) |
| `SAFEWORD` | `system_prompt.py` | `"Override Lithe"` |
| Python server port | `server.py` | `8321` |
| Electron window | `main/index.ts` | 1100×720, resizable (min 900×600) |
| SQLite DB (dev) | `config.py` | `<project_root>/.lithe/lithe_memory.db` |
| SQLite DB (prod) | `config.py` | `%APPDATA%/Lithe/lithe_memory.db` |

---

## Log Entries

> Older logs archived in [ARCHIVE_LOGS.md](file:///d:/Lithe/docs/ARCHIVE_LOGS.md).

| Date | Agent | Action |
|------|-------|--------|
| 2026-08-15 | Antigravity | **Watch-and-Summarize Segment 2:** Added `auto_summaries` table to `memory.py`. Wired `watch_rules` into `watcher.py` event loop on file creation with glob pattern matching. Implemented background summarization task using `summarize_file_for_watch_rule` in `brain.py` with 30s timeout circuit breaker. Added tests in `test_watch_trigger.py`. Branch: `feature/watch-rules-trigger`. |
| 2026-08-15 | Antigravity | **Bugfix:** Prevented failed watch-summaries from saving to DB. Modified `summarize_file_for_watch_rule` in `brain.py` to intercept generation failures and bypass `auto_summaries` insertion while still logging to `action_history`. Added explicit mock failure test to `test_watch_trigger.py`. Branch: `fix/watch-summary-failure-handling`. |
| 2026-08-15 | Antigravity | **Watch-and-Summarize Segment 3:** Wired auto-summaries into Chat UI. Added `GET /api/watch-summaries/pending` and `POST /api/watch-summaries/ack` endpoints. Updated `broadcaster.py` and `brain.py` to live-broadcast new summaries via WebSocket. Updated `App.tsx` and `preload` to fetch pending summaries on startup, deduplicate live summaries, immediately ACK to DB, and render using a custom `message-prefix--auto-summary` class in `MessageBubble.tsx`. Added `tests/test_watch_trigger.py` pending/ack test. Branch: `feature/watch-summary-delivery`. |
| 2026-08-16 | Antigravity | **System Tray & Global Hotkey (Windows-only):** Added `Tray` with `icon.ico`, left-click to show/focus, right-click context menu (Show Lithe / Quit). Registered `Ctrl+Shift+L` global shortcut to summon the window. Tray created on `ready-to-show`, destroyed on `will-quit`. Shortcuts unregistered on `will-quit`. No backend changes. Branch: `feature/tray-and-hotkey`. |
| 2026-08-17 | Antigravity | **Branch Cleanup:** Synced `main`, merged unpushed `CHANGELOG.md` commit from `feature/tray-and-hotkey`, and deleted obsolete `feature/tray-and-hotkey` and `feature/watch-summary-delivery` branches locally and on origin. |
| 2026-08-31 | Antigravity | **Doc Pruning & Ponytail Ultra:** Archived historical log entries and changelog to `docs/ARCHIVE_LOGS.md`. Pruned INDEX.md to active focus and recent entries. Reduced FEATURES.md to dense checklist. Removed dead task specs. Consolidated playbook rules and architecture specs. |
| 2026-08-31 | Antigravity | **Bugfix: Literal `\n\n`** in `ack_auto_summaries` (`memory.py:582`). Double-escaped backslashes wrote literal text instead of newlines. **Fix: Markdown rendering** — `MessageBubble.tsx` wrapped `<ReactMarkdown>` in a `<span>`, causing browsers to flatten block-level output (`<p>`, `<pre>`, `<table>`) into raw text. Changed to `<div>`. Branch: `chore/prune-docs-ponytail`. |
