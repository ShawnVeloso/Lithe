# docs/AGENT_PLAYBOOK.md — Lithe(Jarvis-Lite) AI Agent Instructions

> **This is the primary instruction file for all AI coding agents working on this repository.** > Read this file completely before writing any code. Failure to follow these rules will produce incorrect, inconsistent, or unsafe output.

---

## 0. Before You Write Any Code
1. **Read `docs/ARCHITECTURE.md`:** Understand the tech stack and the hybrid Electron/Python design.
2. **Read `docs/FEATURES.md` (When created):** Ensure you understand the specific acceptance criteria for the feature you are building.
3. **Plan First:** Always outline your proposed changes in a comment or a brief plan before modifying core files.

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