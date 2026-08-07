# docs/TASK_INDEX_UI_AND_FIXES.md — Indexer UI + Design Review Fixes

> **Status:** Active task spec
> **Read first:** `docs/agent-logs/INDEX.md`, `.agents/AGENTS.md`, `docs/DESIGN_SYSTEM.md` (this is a UI + backend task, both docs apply)

---

## 0. Context
A design review of the current build (`[01] INDEX` / `[02] CHAT` / `[03] SYSTEM` layout) surfaced 5 issues. This spec covers all of them. Work top-to-bottom — #1 and #2 are backend/architecture, #3–#5 are frontend polish.

---

## 1. Replace blind full-drive indexing with a UI-driven whitelist picker

**Problem:** The indexer is currently scanning all of `D:\` (219,071 files) — this violates `AGENT_PLAYBOOK.md` §2 ("never execute recursive wildcard searches across the entire root directory") and `ARCHITECTURE.md` §4 ("user configures specific roots"). There's currently no way to set the whitelist except manually editing config in an external editor.

**Fix — Indexer picker in `[01] INDEX`:**
- Add a **`+ INDEX`** button at the top of the `[01] INDEX` panel.
- Clicking it opens the native OS folder/file picker (Electron `dialog.showOpenDialog`, `properties: ['openDirectory', 'openFile', 'multiSelections']`) via IPC from renderer → main process.
- Selected paths are sent to the Python backend and appended to the whitelist (new SQLite table or `.env`/config entry — whichever `config.py` already uses for persisted settings; extend it rather than inventing a second config mechanism).
- Each indexed root gets its own row in `[01] INDEX` with: path, live file count, and a small `×` remove button (removing a root deletes its indexed rows from SQLite and stops the watcher for that path).
- **Bottom text input fallback:** below the root list, a monospace command-line-style input (`> add path...`, consistent with the `[02] CHAT` input styling) lets the user type/paste a path to whitelist instead of using the dialog — for scripting, remote sessions, or paths the picker UI is awkward for.
- **Always-on exclusions**, regardless of what's whitelisted: `node_modules`, `.git`, `AppData`, `$Recycle.Bin`, `System Volume Information`, common Windows/Program Files system directories. These are hard-coded exclusions in `indexer.py`, not user-configurable — this was already the intent in `FEATURES.md` F-03 acceptance criteria, just not fully enforced.
- If a user explicitly whitelists a full drive root (e.g. `D:\`) anyway, that's allowed, but:
  - Indexing must run in the background in **chunks**, not a single blocking pass — surface progress in `[01] INDEX` (e.g. `scanning... 42,000 / ~est files`) rather than freezing until done.
  - The root's row in `[01] INDEX` gets a visible marker (e.g. small amber `FULL DRIVE` tag) so it's an obvious, deliberate state rather than something that happened silently.

**Do not** silently default to indexing a drive root when no whitelist is configured — if the whitelist is empty, `[01] INDEX` should show an empty state prompting the user to add a root via `+ INDEX`, not fall back to scanning everything.

---

## 2. Add a file-write/append tool (F-05 gap)

**Problem:** Lithe currently has `rename_file` and `delete_file` (per `tools.py`) but no way to edit or append to file contents — so a request like "add this text to that file" hits a dead end, even though F-05's acceptance criteria implies general task execution.

**Fix:**
- Add a new tool, e.g. `write_file(path, content, mode)` where `mode` is `"append"` or `"overwrite"`, registered via LLM function calling alongside the existing tools in `tools.py`.
- Apply the same safety pattern already used for `rename_file`/`delete_file`: path validation (empty/null-byte checks, protected-directory checks), `realpath` normalization, and the 30-second circuit-breaker timeout.
- Update `docs/FEATURES.md` F-05 acceptance criteria to explicitly list file writing once this lands.

**Confirmation UX — unified "proposed change" card (Antigravity-style accept/reject), not a plain confirm dialog:**
- Every file-mutating tool call (`write_file` in either mode, `rename_file`, `delete_file`) stops before executing and renders a **proposed-change card** inline in `[02] CHAT`, styled as a monospace diff block:
  - `write_file` (`append`): show only the new lines being added, prefixed `+`, `--success` green.
  - `write_file` (`overwrite`): show a real before/after diff — removed lines prefixed `-` in `--danger` red, added lines prefixed `+` in `--success` green, matching standard diff convention.
  - `rename_file`: show `- old/path` (red) → `+ new/path` (green).
  - `delete_file`: show the full file path being removed, `-` prefixed, red — no "after" side.
- Below the diff block: two buttons, `ACCEPT` and `REJECT`, styled consistent with the rest of the UI (bracketed/bordered, not native browser buttons) — e.g. `[Y] ACCEPT` / `[N] REJECT`, matching the keyboard-driven feel used elsewhere.
- Nothing executes on disk until `ACCEPT` is clicked. `REJECT` cancels the tool call and tells the model it was declined, so it can respond accordingly rather than silently failing.
- This replaces mode-based confirmation logic entirely — there's no "skip confirmation for append" special case anymore. One component, one flow, for all three tools. Applying this consistently is actually less code than the old destructive/non-destructive branching, not more.

---

## 3. Fix semantic color drift in `[02] CHAT`

**Problem:** Per `DESIGN_SYSTEM.md` §1, `--success` (green) is reserved for completed/successful actions specifically so it carries meaning. Currently every `lithe>` line is rendered green by default, including plain conversational replies with no action or success involved — this erases the signal.

**Fix:**
- Default assistant text color → `--text` (plain), not `--success`.
- Reserve `--success` specifically for confirmed successful outcomes: a tool call that completed, a file found, an index update finishing, etc. — i.e., attach the color to the *event*, not to the speaker.
- The `lithe>` / `user>` prefix labels can keep their current distinguishing color (that's a speaker label, not a status) — only the color of the response *body* text should follow the semantic rule.

---

## 4. Fix `[03] SYSTEM` panel header convention

**Problem:** `[01] INDEX` and `[02] CHAT` both use the bracketed `[NN] LABEL` header convention from `DESIGN_SYSTEM.md` §3. The bottom status strip currently has no header at all — just inline `SERVER: ... | MODE: ... | SAFEWORD: ... | TOKENS: ...` text, breaking the one repeating visual pattern the design leans on.

**Fix:** Add a `[03] SYSTEM` header row to the bottom strip, consistent with the other two panels, even though the panel itself stays thin (per `DESIGN_SYSTEM.md` §4, ~15% height full-width strip). The inline status readouts stay below the header row as-is.

---

## 5. Wire up live telemetry

**Problem:** `[01] INDEX`'s `last event` and `[03] SYSTEM`'s `TOKENS` are currently placeholder (`--:--:--`, `--`) — the panels are styled correctly but not connected to real data.

**Fix:**
- `last event` in `[01] INDEX` should update from `watcher.py`'s real file-system events (already exists per `INDEX.md` — this is a wiring task, not new backend logic).
- `TOKENS` in `[03] SYSTEM` should reflect the running prompt/output token counts from the current or most recent `brain.py` call.

---

## Definition of Done (in addition to `AGENT_PLAYBOOK.md` §4)
- [ ] Whitelist is empty by default on a fresh install; no drive is scanned without explicit user action.
- [ ] Hard-coded exclusions apply even to full-drive whitelist entries.
- [ ] `write_file` tool has the same circuit-breaker protections as `rename_file`/`delete_file`.
- [ ] All three file-mutating tools (`write_file`, `rename_file`, `delete_file`) route through the same proposed-change diff card — no tool executes without an explicit `ACCEPT` click, and no mode-based confirmation-skipping logic remains.
- [ ] No `lithe>` conversational reply renders in `--success` green unless it reflects a completed action.
- [ ] `[03] SYSTEM` visually matches the `[NN] LABEL` header pattern used elsewhere.
- [ ] Update `docs/agent-logs/INDEX.md` and `docs/FEATURES.md` per the standard logging rules in `.agents/AGENTS.md`.
