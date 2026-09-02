# Changelog

> Full historical changelog archived in [`docs/ARCHIVE_LOGS.md`](file:///d:/Lithe/docs/ARCHIVE_LOGS.md). Auto-generated recent entries from [`docs/agent-logs/INDEX.md`](file:///d:/Lithe/docs/agent-logs/INDEX.md).

## 2026-09-03
- **Backend Repackaging:** Reconstructed the missing `lithe-server.spec` and rebuilt the PyInstaller bundle. The shipped backend had been stale since Aug 3 and predated `data_tools.py` entirely, so the packaged app never had pandas/matplotlib. Added `openpyxl` as a hidden import (pandas picks its Excel engine by name at runtime, which static analysis cannot see). Excluded GUI toolkits since matplotlib is pinned to the Agg backend. Rebuilt the NSIS installer with the upgrade-hang fix confirmed compiled in.

## 2026-09-02
- **Working-Tree Recovery:** An interrupted folder move stripped files while leaving directories, emptying `src/backend/`, `docs/`, `scripts/`, `resources/`, `locales/` and `.git/`. Restored git from origin plus 239 deleted tracked files. Rebuilt three features whose backend had never been committed — conversation list/switch/delete and the LLM settings endpoints — verifying them against the surviving tests and preload type definitions. Fixed `/api/chat/history` reading a stale import-time copy of the active conversation id. Force-tracked `installer.nsh` and `lithe-server.spec`, which `.gitignore` had been silently excluding.

## 2026-08-31
- **Doc Pruning & Ponytail Ultra:** Archived historical log entries and changelog to `docs/ARCHIVE_LOGS.md`. Pruned INDEX.md to active focus and recent entries. Reduced FEATURES.md to dense checklist. Removed dead task specs. Consolidated playbook rules and architecture specs.
- **Bugfix: Literal `\n\n`** in `ack_auto_summaries` (`memory.py:582`). Double-escaped backslashes wrote literal text instead of newlines. **Fix: Markdown rendering** — `MessageBubble.tsx` wrapped `<ReactMarkdown>` in a `<span>`, causing browsers to flatten block-level output (`<p>`, `<pre>`, `<table>`) into raw text. Changed to `<div>`. Branch: `chore/prune-docs-ponytail`.

## 2026-08-17
- **Branch Cleanup:** Synced `main`, merged unpushed `CHANGELOG.md` commit from `feature/tray-and-hotkey`, and deleted obsolete `feature/tray-and-hotkey` and `feature/watch-summary-delivery` branches locally and on origin.

## 2026-08-16
- **System Tray & Global Hotkey (Windows-only):** Added `Tray` with `icon.ico`, left-click to show/focus, right-click context menu (Show Lithe / Quit). Registered `Ctrl+Shift+L` global shortcut to summon the window. Tray created on `ready-to-show`, destroyed on `will-quit`. Shortcuts unregistered on `will-quit`. No backend changes. Branch: `feature/tray-and-hotkey`.

## 2026-08-15
- **Watch-and-Summarize Segment 2:** Added `auto_summaries` table to `memory.py`. Wired `watch_rules` into `watcher.py` event loop on file creation with glob pattern matching. Implemented background summarization task using `summarize_file_for_watch_rule` in `brain.py` with 30s timeout circuit breaker. Added tests in `test_watch_trigger.py`. Branch: `feature/watch-rules-trigger`.
- **Bugfix:** Prevented failed watch-summaries from saving to DB. Modified `summarize_file_for_watch_rule` in `brain.py` to intercept generation failures and bypass `auto_summaries` insertion while still logging to `action_history`. Added explicit mock failure test to `test_watch_trigger.py`. Branch: `fix/watch-summary-failure-handling`.
- **Watch-and-Summarize Segment 3:** Wired auto-summaries into Chat UI. Added `GET /api/watch-summaries/pending` and `POST /api/watch-summaries/ack` endpoints. Updated `broadcaster.py` and `brain.py` to live-broadcast new summaries via WebSocket. Updated `App.tsx` and `preload` to fetch pending summaries on startup, deduplicate live summaries, immediately ACK to DB, and render using a custom `message-prefix--auto-summary` class in `MessageBubble.tsx`. Added `tests/test_watch_trigger.py` pending/ack test. Branch: `feature/watch-summary-delivery`.
