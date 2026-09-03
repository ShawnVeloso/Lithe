# Changelog

> Full historical changelog archived in [`docs/ARCHIVE_LOGS.md`](file:///d:/Lithe/docs/ARCHIVE_LOGS.md). Auto-generated recent entries from [`docs/agent-logs/INDEX.md`](file:///d:/Lithe/docs/agent-logs/INDEX.md).

## 2026-09-03
- **Backend repackaging.** Reconstructed the lost `lithe-server.spec` (gitignored by `*.spec`, so it was in neither origin nor any transcript) from `server_entry.py` and the shipped bundle. The packaged backend was found to be from Aug 3 — eight days older than `data_tools.py` — so it had never contained pandas/matplotlib at all. Rebuilt: 43MB → 121MB bundle, GUI toolkits excluded since matplotlib is pinned to Agg. Added `openpyxl` as a hidden import because pandas resolves its Excel engine by name at call time, which would have failed `profile_data` on `.xlsx` at runtime. Verified the packaged exe serves the recovered endpoints, then rebuilt the installer (130MB).

## 2026-09-02
- **Working-tree recovery.** An interrupted folder move left directories in place but stripped their files, emptying `src/backend/`, `docs/`, `scripts/`, `resources/`, `locales/` and `.git/` itself (271 dirs, 0 files — git was unreadable). Restored `.git` from origin and checked out 239 deleted tracked files. Three features had a surviving frontend but a backend that was never committed, so origin could not restore them; rebuilt `memory.get_conversations`/`delete_conversation`, `brain.switch_conversation`, `config.update_llm_config`, and the `/api/chat/conversations`, `/api/chat/switch` and `/api/config/llm` endpoints, verified against the surviving `tests/test_memory.py` and `env.d.ts` response shapes. Fixed `/api/chat/history` binding `_current_conversation_id` by value at import, so it never saw a switch. Merged the original `package.json` build config back over the Sep-1 reconstruction. Tests 33→36 passing.

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
