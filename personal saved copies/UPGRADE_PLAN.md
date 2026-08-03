# docs/UPGRADE_PLAN.md — Lithe Architecture Enhancements

**Status:** Active Implementation
**Audience:** AntiGravity AI Agent, Lead Developer
**Objective:** Execute a series of robust, fail-safe, and efficiency upgrades to Lithe's core architecture. Implement sequentially by priority.

---

## Phase 1: Foundation & Safety (High Priority)
*These upgrades must be completed first to prevent system crashes and ensure the database can handle concurrent read/write operations.*

### 1. SQLite Write-Ahead Logging (WAL)
* [cite_start]**Concept:** Enable WAL mode in the SQLite configuration[cite: 294].
* [cite_start]**Rationale:** Because Lithe has a background indexer writing to the database and an LLM actively reading from it, the system will eventually hit a "database is locked" error[cite: 293]. [cite_start]WAL allows simultaneous readers and writers[cite: 295].
* **Implementation Steps:** * Modify the database initialization script to execute `PRAGMA journal_mode=WAL;`.
    * Ensure the SQLite connection handles concurrent connections gracefully.

### 2. "Circuit Breakers" for Tool Execution
* [cite_start]**Concept:** Add strict technical boundaries for when Lithe executes Python scripts[cite: 302].
* [cite_start]**Rationale:** Prevents a poorly generated script from getting stuck in an infinite loop and melting the CPU[cite: 304].
* **Implementation Steps:**
    * [cite_start]Wrap all LLM function calls in a strict `try/except` block using Python's `subprocess` module with a hard timeout limit (e.g., 30 seconds)[cite: 303].
    * [cite_start]Implement strict type-checking and validation on the arguments the LLM attempts to pass before the code ever executes[cite: 305].

---

## Phase 2: Reliability (Medium Priority)
*Ensuring Lithe remains completely functional and self-reliant, even when cloud services fail.*

### 3. The "Fallback" Pattern
* **Concept:** Implement an automatic routing system between cloud APIs and local LLMs.
* [cite_start]**Rationale:** Cloud models are highly capable but are at the mercy of rate limits and internet connections[cite: 285].
* **Implementation Steps:**
    * [cite_start]If the primary cloud model (Gemini) encounters a network drop or API error, the code must catch that error and instantly route the prompt to a local model via Ollama[cite: 287].
    * [cite_start]This guarantees Lithe works offline and never crashes just because an API failed[cite: 288].

---

## Phase 3: Efficiency & Context (Next-Gen Features)
*Optimizing how Lithe understands, maps, and indexes local files without slowing down the host machine.*

### 4. Event-Driven Memory
* **Concept:** Replace the full-directory startup scan with real-time file watching.
* [cite_start]**Rationale:** As data science datasets and repositories grow, full directory scans on startup will cause massive boot delays[cite: 290].
* **Implementation Steps:**
    * [cite_start]Implement an OS-level file watcher (using Python's `watchdog` library) scoped only to the whitelisted directories[cite: 291].
    * [cite_start]Configure Lithe to silently update the SQLite database in the background only when a file is actually created, modified, or deleted in real-time[cite: 292].

### 5. The Heuristic Graph
* **Concept:** Build a relational map of the local files based on names and folder structures to enhance contextual intelligence.
* [cite_start]**Rationale:** Pure vector search (RAG) is great for PDFs but struggles to understand how local code files relate to one another[cite: 296].
* **Implementation Steps:**
    * [cite_start]Write hardcoded logic to "guess" how the codebase works based on file locations[cite: 298].
    * [cite_start]For example, if a file is detected inside a `/src/cli/` folder, automatically tag it in the database with a concept like "CLI Orchestration"[cite: 299].
    * [cite_start]This builds a relational map instantly, giving the AI massive context about project structures before the user even asks a question[cite: 300].