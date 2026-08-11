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
| | Spawn browser automation agents or any autonomous browser session to interact with GitHub (creating PRs, filling forms, clicking merge, etc.) without my explicit request first. |

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

## 5. Git & Version Control

* **One feature, one branch.** Before starting a task, create a branch off `main`
  (e.g. `feature/undo-stack`, `fix/status-endpoint-brain-import`). Never commit
  directly to `main`.
* **One feature, one commit (or a tight series of small commits).** Do not bundle
  unrelated changes into a single commit. Commit message format:
  `<type>: <short description>` — e.g. `feat: add token budget indicator to SystemPanel`,
  `fix: resolve NameError in /api/status endpoint`.
* **Test before merging.** Confirm the app launches and the specific feature/fix
  works before merging the branch into `main`.
* **Open a PR, even solo.** Push the branch, open a pull request into `main` with a
  short description of what changed and why. This creates a review checkpoint and a
  searchable history, even with a single reviewer (you).
  After pushing a branch, stop. Print the PR creation link from git's output
  and let the user open, review, and create the PR themselves. Do not create,
  fill out, or submit the PR yourself, by browser automation or any other
  method, unless explicitly asked.
* **Never commit secrets.** `.env`, API keys, and the SQLite DB must stay gitignored.
  If a secret is ever accidentally committed and pushed, treat it as compromised —
  rotate it immediately, don't just delete the commit.
* **Log entries still apply.** Updating `docs/agent-logs/INDEX.md` per §2 is required
  regardless of branch/PR status — it's a separate, parallel record.
