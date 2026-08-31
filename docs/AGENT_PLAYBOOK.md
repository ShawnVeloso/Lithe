# docs/AGENT_PLAYBOOK.md — Lithe AI Agent Behavioral Playbook

> **Strict Behavioral Rules & Operating Boundaries for AI Agents.**
> Consult [ARCHITECTURE.md](file:///d:/Lithe/docs/ARCHITECTURE.md) for system architecture and tech stack details.
> Consult [.agents/AGENTS.md](file:///d:/Lithe/.agents/AGENTS.md) for context acquisition and logging rules.

---

## 1. Scope & Permissions

| You CAN | You CANNOT |
| :--- | :--- |
| Write Python scripts for local file manipulation within whitelisted directories. | Blindly scan `C:\` or `D:\` without using the SQLite indexer. |
| Write TypeScript/React code for the Electron UI. | Install heavy dependencies without explicit user request. |
| Use SQLite for local memory and vector/keyword storage. | Hardcode API keys, tokens, or credentials into any file. |
| Ask for clarification if a feature is ambiguous. | Guess at system-level file paths; always locate dynamically. |
| Read and analyze whitelisted files. | Spawn autonomous browser agents to create/submit PRs on GitHub. |

---

## 2. File System Safety (Strict Invariants)

- **Indexing First:** All file discovery must go through the local `SQLite` memory index. No recursive root traversals.
- **Read-Only by Default:** Unless explicitly requested by the user, treat all system files as Read-Only.
- **Path Sanitization:** Normalize paths using `os.path.realpath()`, never allow null bytes, and strictly protect system directories.
- **Ignore Build/Cache Artifacts:** Directory scanners must ignore `node_modules`, `.git`, `__pycache__`, and heavy dependency caches.

---

## 3. Definition of Done

Before declaring a task complete:
- [ ] No `console.log` or generic `print()` debug statements left in production code.
- [ ] Boundaries between Electron frontend and Python backend are intact.
- [ ] Any new environment variables are documented in `.env.example`.
- [ ] Code verified on Windows environment.
- [ ] `docs/agent-logs/INDEX.md` updated per `.agents/AGENTS.md` §2.

---

## 4. Git & Branching Protocol

- **One feature, one branch:** Branch off fresh `main` (e.g., `feature/...`, `fix/...`, `chore/...`).
- **Conventional commits:** `<type>: <short description>` format.
- **Test before merging:** Verify app functionality before branch integration.
- **Solo PR protocol:** Push branch, provide the GitHub PR creation URL, and stop. Never automate PR creation via browser unless explicitly instructed.
- **Zero secrets:** Keep `.env`, keys, and SQLite database gitignored.
