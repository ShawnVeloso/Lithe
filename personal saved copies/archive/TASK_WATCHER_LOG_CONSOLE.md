# docs/TASK_WATCHER_LOG_CONSOLE.md — Live Watcher Log Console

> **Status:** Active task spec
> **Read first:** `docs/agent-logs/INDEX.md`, `.agents/AGENTS.md`, `docs/DESIGN_SYSTEM.md`, `docs/TASK_INDEX_UI_AND_FIXES.md` (this builds directly on the `[01] INDEX` / `[03] SYSTEM` work from that spec — read it for the exclusion-list fix, which this task will make visibly obvious once shipped)

---

## 0. Context
`watcher.py` already logs every index/removal event (`[Lithe Watcher] Indexed: ...` / `Removed: ...`) — but only to the raw Python terminal. The user has no visibility into this from the Lithe UI itself. Expose it as a live, expandable console.

**Bonus effect:** once this ships, you'll likely see `$I`-prefixed Recycle Bin metadata files showing up as "indexed" (visible in the current terminal output already) — that's a symptom of the exclusion-list gap covered in `TASK_INDEX_UI_AND_FIXES.md` §1. Fixing that exclusion list should make this log visibly cleaner; treat a noisy log full of `$I*`/system files post-launch as a signal that fix isn't fully in place yet.

---

## 1. Backend: stream watcher events instead of only printing them

- `watcher.py` currently only prints. Add a broadcaster (in-memory queue or simple pub/sub) that each index/removal event gets pushed to, in addition to the existing print statements — don't remove the print, some workflows may still run headless via terminal.
- `server.py`: add a WebSocket endpoint (e.g. `/ws/watcher-log`) that streams each event to connected clients as JSON: `{"type": "indexed" | "removed", "path": "...", "timestamp": "..."}`.
- Keep an in-memory ring buffer of the last ~500 events server-side, so a client connecting mid-session can request recent history on connect, not just events from that point forward.
- Given the scale seen in testing (219k+ files during a full-drive index), the backend must not flood the socket unthrottled — batch rapid-fire events (e.g. flush every 100ms) rather than sending one WebSocket message per file.

---

## 2. Frontend: expandable console anchored to `[03] SYSTEM`

**Placement:** the console lives in the `[03] SYSTEM` panel, since indexing is a background system process — not a new top-level panel, and not a right-side column (would eat into `[02] CHAT` width for no benefit).

**Default state:** expanded on launch, per user preference — the console drawer is visible immediately, not something the user has to discover.

**Structure:**
- `[03] SYSTEM` header row gains a collapse/expand toggle (e.g. `[03] SYSTEM   [COLLAPSE LOG]` / `[EXPAND LOG]` when collapsed) — keep the existing `[NN] LABEL` convention, just add the toggle as a right-aligned control in that same header row, consistent with how `[01] INDEX` already has its `+ INDEX` button in-header.
- When expanded, a scrolling log drawer grows **upward** from the `[03] SYSTEM` strip, above the existing `SERVER: ... | MODE: ... | SAFEWORD: ... | TOKENS: ...` status line (that line stays put at the very bottom regardless of expand state). Default expanded height: roughly 30–35% of the window, reducing `[01] INDEX` / `[02] CHAT` visible height accordingly — a fixed height is fine for v1, a drag-to-resize handle is a nice-to-have, not required.
- Collapsing hides the drawer entirely, leaving just the thin `[03] SYSTEM` status strip as it is today.
- **Log line format**, monospace, one event per line:
  - `+ Indexed   <path>` — color `--info` (blue). This is background system activity, not a user-triggered success, so it should NOT use `--success` green (per the semantic-color rule already fixed in `TASK_INDEX_UI_AND_FIXES.md` §3 — don't reintroduce the same drift here for a different panel).
  - `- Removed   <path>` — color `--text-dim`, since a removal is routine watcher bookkeeping, not an error (`--danger` stays reserved for actual failures).
- **Autoscroll:** new lines push the view down automatically, but pause autoscroll if the user manually scrolls up to read history — resume when they scroll back to the bottom (standard console/devtools behavior).
- **Filter input:** a small monospace text input at the bottom of the drawer (`> filter log...`), consistent with the `add path...` input already in `[01] INDEX` and the command input in `[02] CHAT` — filters visible lines by substring match on path, client-side.
- **Client-side cap:** keep at most ~1,000 rendered lines in the DOM (virtualized list or simple truncation of the oldest entries) — this will see high volume on a full-drive index, don't let it degrade UI performance.

---

## Definition of Done (in addition to `AGENT_PLAYBOOK.md` §4)
- [ ] Watcher events are visible live in the Lithe UI, not just the terminal.
- [ ] Console defaults to expanded on launch; collapse/expand toggle works and lives in the `[03] SYSTEM` header.
- [ ] `Indexed` events render in `--info`, not `--success` — confirm this doesn't drift the same way the chat panel did.
- [ ] Backend batches/throttles WebSocket messages; no unthrottled per-file flood during a large scan.
- [ ] Frontend caps rendered log lines and doesn't degrade with sustained high-volume indexing.
- [ ] Update `docs/agent-logs/INDEX.md` and `docs/FEATURES.md` per `.agents/AGENTS.md`.
