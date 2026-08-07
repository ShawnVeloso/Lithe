# Lithe Workspace Agent Rules

These rules apply to all AI coding agents working in the Lithe repository. You must adhere to them strictly on every invocation.

## 1. Context Acquisition

**Always read, every session, regardless of task size:**
- `docs/agent-logs/INDEX.md` — current project state, read this FIRST, it tells you what else is relevant.
- `docs/AGENT_PLAYBOOK.md` — your operational boundaries (scope, safety, coding standards).

**Read only when the task touches that area — don't pay the full cascade for a small fix:**

| If your task involves... | Also read |
|---|---|
| New features, changed requirements, or unclear scope | `docs/ARCHITECTURE.md` + `docs/FEATURES.md` |
| UI, styling, layout, or any frontend visual work | `docs/DESIGN_SYSTEM.md` (and `docs/DESIGN_BRIEF.md` for the underlying rationale) |
| A single, well-scoped bug fix in one known file | None of the above — INDEX.md + AGENT_PLAYBOOK.md is enough |

If you're unsure whether a task needs the wider context, err on the side of reading `ARCHITECTURE.md` + `FEATURES.md` — but don't default to reading everything for trivial changes.

## 2. Mandatory Documentation Updates
Every time you make code changes, complete a task, or when the user communicates a change of plan, vision, or architecture, you MUST:
- **Update the Log:** Append a new row to the "Log Entries" table in `docs/agent-logs/INDEX.md` containing the date, your agent name, and a summary of what you did.
- **Update the Timestamp:** Update the "Last Updated" timestamp at the top of `docs/agent-logs/INDEX.md`.
- **Sync Features & Architecture:** If the user introduces a new feature, changes a requirement, or alters the architecture, you must immediately update `docs/FEATURES.md` and/or `docs/ARCHITECTURE.md` to reflect the new state.

**Do not wait for the user to ask you to update the docs. It is your responsibility to keep them continuously synced as a living record.**
