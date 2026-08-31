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
- **Update Current Focus:** Update the "Current Focus" block at the top of `docs/agent-logs/INDEX.md`. It should always reflect current reality, not be left stale.
- **Sync Features & Architecture:** If the user introduces a new feature, changes a requirement, or alters the architecture, you must immediately update `docs/FEATURES.md` and/or `docs/ARCHITECTURE.md` to reflect the new state.

**Do not wait for the user to ask you to update the docs. It is your responsibility to keep them continuously synced as a living record.**

## 3. Scope and Unrelated Bugs

When working on a specific branch or feature, if you hit an unrelated bug mid-branch (even if it is small or blocking your tests), **flag it and ask the user before fixing it**. 
Do not fold unrelated fixes into your current branch and explain them after the fact. Maintain strict scope discipline.

Pull main before branching. Every new branch starts from a freshly pulled main — never off a stale local copy. This is the #1 cause of silent divergence.
Code changes first, INDEX.md update last, same commit or the very next one. AG doesn't get to update INDEX.md mid-task and then keep coding — the doc update is the closing move of a task, not a running log.
INDEX.md updates are part of the feature's diff, not a separate one. One PR = one feature = one INDEX.md log entry, included in that same PR. Never a standalone "docs sync" commit that lands separately from the code it describes.
Merge to main happens before the next branch starts. No stacking a new branch on top of an unmerged one. If Shawn hasn't reviewed/merged yet, AG waits or works on something explicitly unrelated — it does not start a second parallel branch that will also need to touch INDEX.md.
On merge conflict in INDEX.md specifically: the log table entries always get appended, never overwritten — if git shows a conflict there, that's a signal something violated rule 4, not something to resolve by picking one side.