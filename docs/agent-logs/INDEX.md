# Lithe — Agent Log Index

> **Purpose:** Persistent state-tracking for AI agents and the lead developer.
> **Last Updated:** 2026-09-03T02:40 (PHT)

---

## Current Focus
- **Working on:** capability audit — measuring whether the agent loop, tool
  dispatch and retrieval actually work, before changing them
- **Next up:** B2 `fix/gemini-tool-name-mismatch` — restore the 5 tools that are
  dead on the Gemini path
- **Then:** B2b narrow exception handling, B3 bounded agent loop, B4 `read_file`
- **Blocked on:** nothing

> **Verify before shipping:** the install→upgrade cycle has still never been
> exercised end-to-end on a real machine. The fix for the "a Lithe process is
> open" hang is compiled into the current installer (confirmed via the
> `!include` line in `release/builder-debug.yml`) but has not been observed
> working against an actual prior install.

---

## Project Status Overview

| Feature | Status | Notes |
|---------|--------|-------|
| **F-01** — Core LLM Connection | ✅ Complete | Gemini API via `google-genai`, env-var loaded |
| **F-02** — Minimal Chat Interface | ✅ Complete | Electron + React, electron-vite, FastAPI bridge |
| **F-03** — Local Directory Indexer | ✅ Complete | SQLite + whitelisted directory crawling |
| **F-04** — File Context Injection | ✅ Complete | Regex `name.ext` detection, exact-basename SQLite lookup, whole-file injection. Not retrieval: no content index, so a prompt that names no file injects nothing. |
| **F-05** — Basic Task Execution | ✅ Complete | LLM Function Calling with dynamic safeword wrappers |
| **F-06** — Candid Persona & Safeword | ✅ Complete | Dual system prompts, case-insensitive safeword |
| **F-07** — Desktop Packaging | ✅ Complete | PyInstaller backend + electron-builder NSIS installer. `lithe-server.spec` and `src/frontend/build/installer.nsh` are hand-maintained source and are now force-tracked past `.gitignore` — both were previously ignored and unrecoverable. |
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
| 2026-09-02 | Claude Opus 5 | **Working-tree recovery.** An interrupted folder move left directories in place but stripped their files, emptying `src/backend/`, `docs/`, `scripts/`, `resources/`, `locales/` and `.git/` itself (271 dirs, 0 files — git was unreadable). Restored `.git` from origin and checked out 239 deleted tracked files. Three features had a surviving frontend but a backend that was never committed, so origin could not restore them; rebuilt `memory.get_conversations`/`delete_conversation`, `brain.switch_conversation`, `config.update_llm_config`, and the `/api/chat/conversations`, `/api/chat/switch` and `/api/config/llm` endpoints, verified against the surviving `tests/test_memory.py` and `env.d.ts` response shapes. Fixed `/api/chat/history` binding `_current_conversation_id` by value at import, so it never saw a switch. Merged the original `package.json` build config back over the Sep-1 reconstruction. Tests 33→36 passing. |
| 2026-09-03 | Claude Opus 5 | **Backend repackaging.** Reconstructed the lost `lithe-server.spec` (gitignored by `*.spec`, so it was in neither origin nor any transcript) from `server_entry.py` and the shipped bundle. The packaged backend was found to be from Aug 3 — eight days older than `data_tools.py` — so it had never contained pandas/matplotlib at all. Rebuilt: 43MB → 121MB bundle, GUI toolkits excluded since matplotlib is pinned to Agg. Added `openpyxl` as a hidden import because pandas resolves its Excel engine by name at call time, which would have failed `profile_data` on `.xlsx` at runtime. Verified the packaged exe serves the recovered endpoints, then rebuilt the installer (130MB). |
| 2026-09-03 | Claude Opus 5 | **Evaluation harness (U-16).** Added a way to measure Lithe rather than assume it. `pytest.ini` (`pythonpath`, `testpaths`, eval gating) so bare `pytest` works and the root-level live-API script is no longer collected. `tests/conftest.py` with shared DB isolation plus autouse fixtures that reset `brain`'s module globals and block real network calls — necessary because importing `brain` runs `_load_history()` at module scope against the real DB. `tests/support/fake_gemini.py` scripts the LLM with genuine `google.genai.types` objects (a MagicMock would hide the very bug below). New: `test_tool_contract.py` (agent loop + the mutating-tool confirmation handshake, previously untested despite being the real safety gate), `test_retrieval.py`, `test_safeword.py`. Repaired `test_watch_trigger.py`, which carried 121 duplicated lines including a truncated assertion-less test; collection count unchanged at 8, proving the deletion was safe. Added opt-in live evaluation (`tests/eval/`) scoring tool selection, argument correctness, retrieval, refusal, hallucination and safeword against a synthetic corpus. **10 defects recorded as `xfail(strict=True)`** so they are listed on every run and cannot be fixed silently — notably that 5 of 9 tools are unreachable on Gemini because the SDK declares them by `__name__` (`profile_data_wrapper`) while `tool_map` is keyed `profile_data`. Suite 36 → 56 passing + 11 xfailed. No `src/` changes. Branch: `test/eval-harness`. |
