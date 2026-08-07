# docs/AGENT_PLAYBOOK.md — Lithe(Jarvis-Lite) AI Agent Instructions

> **Read `.agents/AGENTS.md` first.** It covers context-acquisition order and documentation-update rules — this file covers everything else: scope, safety, coding standards, and definition of done. Both are required reading, but don't duplicate each other.

---

## 1. Scope and Authority

| You CAN | You CANNOT |
| :--- | :--- |
| Write Python scripts for local file manipulation. | Blindly scan `C:\` or `D:\` without using the SQLite indexer. |
| Write TypeScript/React code for the Electron UI. | Install heavy dependencies (like heavy ML libraries) without asking. |
| Use SQLite for local memory and vector storage. | Hardcode API keys or credentials directly into scripts. |
| Ask for clarification if a feature is ambiguous. | Guess at system-level file paths; always dynamically locate them. |

---

## 2. File System Safety (CRITICAL)
Lithe is designed to have full exploration of the user's C: and D: drives. However, AI agents must **never** write scripts that execute recursive wildcard searches across the entire root directory.
* **Indexing First:** All file discovery must go through the local `SQLite` memory index.
* **Read-Only by Default:** Unless explicitly requested by the user, treat all system files as Read-Only.
* **Avoid `node_modules` and `.git`:** When writing directory scanning scripts, explicitly ignore hidden directories and heavy dependency folders to save compute.

---

## 3. Technology & Coding Standards
* **Backend:** Use **Python**. Favor built-in libraries (`os`, `json`, `sqlite3`) over third-party packages whenever possible to keep the application lightweight.
* **Frontend:** Use **Electron + React (TypeScript)**.
* **The "Brain":** When building LLM calls, default to using the Gemini API for speed, but ensure the architecture supports swapping to a local `Ollama` model easily.

---

## 4. Definition of Done
Before you consider a task complete, verify:
- [ ] No `console.log` or generic `print()` debug statements are left in production code.
- [ ] You have not broken the boundary between the Electron frontend and the Python backend.
- [ ] Any new environment variables are documented.
- [ ] Code runs successfully on a Windows environment (the user's OS).
- [ ] `docs/agent-logs/INDEX.md` has been updated per `.agents/AGENTS.md` §2 — this is not optional, check it before ending your session.
