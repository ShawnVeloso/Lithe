# Lithe Workspace Agent Rules

These rules apply to all AI coding agents working in the Lithe repository. You must adhere to them strictly on every invocation.

## 1. Context Acquisition
Before writing any code or making technical decisions, you MUST:
- Read `docs/AGENT_PLAYBOOK.md` to understand your operational boundaries.
- Read `docs/ARCHITECTURE.md` and `docs/FEATURES.md` to understand the system design and current scope.
- Read `docs/agent-logs/INDEX.md` to understand the latest state of the project and recent changes.

## 2. Mandatory Documentation Updates
Every time you make code changes, complete a task, or when the user communicates a change of plan, vision, or architecture, you MUST:
- **Update the Log:** Append a new row to the "Log Entries" table in `docs/agent-logs/INDEX.md` containing the date, your agent name, and a summary of what you did.
- **Update the Timestamp:** Update the "Last Updated" timestamp at the top of `docs/agent-logs/INDEX.md`.
- **Sync Features & Architecture:** If the user introduces a new feature, changes a requirement, or alters the architecture, you must immediately update `docs/FEATURES.md` and/or `docs/ARCHITECTURE.md` to reflect the new state.

**Do not wait for the user to ask you to update the docs. It is your responsibility to keep them continuously synced as a living record.**
