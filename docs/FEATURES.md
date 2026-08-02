# docs/FEATURES.md — Lithe(Jarvis-Lite) Feature Specification

> **Status:** Living document — update as features are added or completed.
> **Audience:** AI coding agents, lead developer.
> **Format:** Each feature has a user story, acceptance criteria, and scope notes.

---

## Feature Index

| ID | Feature | Category | Status |
|---|---|---|---|
| F-01 | Core LLM Connection (The Brain) | Backend | ✅ Complete |
| F-02 | Minimal Chat Interface (The Face) | Frontend | ✅ Complete |
| F-03 | Local Directory Indexer (The Memory) | Backend | ✅ Complete |
| F-04 | RAG & File Context (Second Brain) | Backend | ✅ Complete |
| F-05 | Basic Task Execution (The Hands) | Tooling | ✅ Complete |
| F-06 | Candid Persona & Safeword | Backend | ✅ Complete |

---

## F-01 — Core LLM Connection (The Brain)
**User Story:** As a developer, I want a Python script that can securely connect to the Gemini API so that my assistant can process text and return intelligent responses.
**Acceptance Criteria:**
- [ ] Python script uses the official SDK to send a prompt and receive a response.
- [ ] API keys are loaded securely from a `.env` file (never hardcoded).
- [ ] Includes a predefined "System Prompt" (e.g., "You are Lithe, a Data Science assistant").

## F-02 — Minimal Chat Interface (The Face)
**User Story:** As a user, I want a clean desktop window where I can type messages to the AI and read its responses, so I don't have to use a terminal.
**Acceptance Criteria:**
- [ ] Electron wrapper spawns a secure, fixed-size desktop window.
- [ ] React/TypeScript frontend renders a chat feed and a text input box.
- [ ] Frontend communicates with the Python backend to send/receive messages.

## F-03 — Local Directory Indexer (The Memory)
**User Story:** As a user, I want the AI to map specific folders on my C: and D: drives so it knows where my files are without scanning my whole computer.
**Acceptance Criteria:**
- [ ] A Python script takes a list of allowed directories (e.g., `D:\Projects`).
- [ ] Script walks the directories and saves file paths and metadata to a local SQLite database.
- [ ] Excludes `node_modules`, `.git`, and hidden system files to save compute.

## F-04 — RAG & File Context (Second Brain)
**User Story:** As a Data Science student, I want to ask questions about my local datasets or PDFs, and have the AI read them to give me an answer.
**Acceptance Criteria:**
- [ ] When the user asks about a file, the AI queries the SQLite index (F-03) to find the file path.
- [ ] The Python backend opens the file, reads the content, and appends it to the LLM prompt.
- [ ] The AI generates an answer based *only* on the local file content.

## F-05 — Basic Task Execution (The Hands)
**User Story:** As a developer, I want to ask the AI to perform a simple task (like renaming a file or summarizing a CSV) and have it actually execute the code on my machine.
**Acceptance Criteria:**
- [ ] Python backend registers basic tools using LLM Function Calling.
- [ ] AI can decide to trigger a Python function based on the user's chat input.
- [ ] User is asked for confirmation before any destructive action (like deleting or moving a file) occurs.

## F-06 — Candid Persona & Safeword Override
**User Story:** As a user, I want my AI to challenge my bad ideas and offer critical feedback rather than acting like a people-pleaser. However, I want a specific "safeword" that overrides this behavior when I need strict compliance.
**Acceptance Criteria:**
- [ ] The Python backend's core system prompt strictly instructs the LLM to prioritize factual accuracy and critical feedback over politeness.
- [ ] The AI must explicitly point out logic flaws or inefficiencies in the user's requests.
- [ ] The system recognizes a hardcoded safeword (e.g., "Override Lithe").
- [ ] When the safeword is present in the user's input, the AI drops all critical pushback, bypasses debate, and strictly executes the user's exact instructions.