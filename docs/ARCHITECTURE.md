# docs/ARCHITECTURE.md — Lithe(Jarvis-Lite) System Design

> **Status:** Current (v2 — post-UPGRADE_PLAN)
> **Audience:** AI coding agents, lead developer.
> **Project Goal:** A local, permissioned AI desktop assistant optimized for Data Science, research, and daily developer workflows.

## 1. Project Overview
Lithe is a hybrid desktop application. It acts as an always-on, permissioned local actor that lives on the desktop. It bridges a modern web-based UI with a powerful Python backend capable of exploring local file systems (C: and D: drives), executing data science scripts, and automating daily workflows.

## 2. Technology Stack

| Layer | Technology | Rationale |
| :--- | :--- | :--- |
| **Frontend UI** | Electron + React (TypeScript) | Provides a polished, OS-native desktop window (borrowing the architectural style from the *Winnow* reference). |
| **Backend Engine** | Python + FastAPI | The core orchestrator. Ideal for a Data Science student. Handles file system access, data manipulation, AI tool execution, and serves a REST API on `localhost:8321`. |
| **Memory & Indexing** | SQLite (WAL mode) | A lightweight, local-first database to index whitelisted directories. Uses WAL for concurrent read/write access. Allows the AI to instantly search files using keyword search without rescanning the hard drive every time. |
| **The Brain (LLM)** | Gemini API / Ollama | A fallback pattern. Uses the Gemini API (`gemini-3.6-flash`) for complex, high-speed reasoning, with automatic fallback to local Ollama models when Gemini is unreachable (network failure, rate limit, API error). Both engines share one transcript and run the same bounded tool loop, so a mid-conversation fallback keeps its memory and its ability to chain tools. Readiness means the configured model is actually pulled, not merely that the Ollama server answers. |
| **File Watching** | `watchdog` library | Real-time, event-driven monitoring of whitelisted directories. Replaces the need for full re-scans on every startup after the initial index. |

## 3. Architecture Style: The "Permissioned Local Actor"
Unlike cloud-only chatbots, Lithe operates directly on the host machine.
1. **The UI** sends a request (e.g., "Summarize the dataset I downloaded yesterday").
2. **The Python Backend** intercepts the request via FastAPI (`POST /api/chat`).
3. **The Memory Engine (SQLite)** instantly queries the indexed map of whitelisted directories to find the exact file path of the dataset.
4. **The Tool Executer** runs a Python function to read the CSV/PDF (with 30-second timeout and path validation circuit breakers).
5. **The Brain** processes the data and returns the answer back to the UI.
6. **Fallback**: If Gemini is unreachable, the request is automatically routed to a local Ollama model.

## 4. Data Flow

```
User → ChatInput → App.tsx state → window.litheAPI.chat()
       → preload (contextBridge) → POST localhost:8321/api/chat
       → FastAPI server.py → brain.chat() → Gemini API (or Ollama fallback)
       → response bubbles back through the same chain
```

Within one turn, `brain.chat()` runs a bounded tool loop rather than a single
round trip:

```
  model call ─┬─> text answer ──────────────────> return
              │
              ├─> read-only tool ─> execute ─> feed result back ─┐
              │        ^                                         │
              │        └──── up to MAX_TOOL_ROUNDS (5) ──────────┘
              │
              └─> mutating tool ─> pause, return diff to the UI
                                    └─> user confirms ─> execute ─> resume loop
                                                                    with the
                                                                    remaining
                                                                    budget
```

On exhausting the budget the model is called once more with tools removed, so
it must answer in text instead of emitting a call that would be discarded.

### Security Boundaries
- **Renderer** has zero access to `electron` or `node` — all backend calls go through `contextBridge`.
- **Electron main** spawns the Python server as a child process and polls `/api/health` before showing the window.
- **Safeword** (`"Override Lithe"`, case-insensitive) toggles the system prompt per-message.
- **Circuit Breakers** prevent tool execution on protected system paths and enforce hard timeouts.

## 5. Drive Exploration & Indexing Strategy
To prevent system crashes and endless scanning, Lithe uses a multi-tier indexing strategy:

### Initial Index (Startup)
* **Whitelisted Directories:** The user configures specific roots in `.env` via `INDEX_WHITELIST` (e.g., `D:\`).
* **Background Crawler:** On server startup, `indexer.py` walks these directories and indexes file metadata into SQLite in batches of 500.
* **Smart Exclusions:** `node_modules`, `.git`, `__pycache__`, `venv`, `.venv`, `env`, `.idea`, `.vscode`, and hidden directories are never traversed.

### Real-Time Watching (Post-Startup)
* **Event-Driven:** After the initial index, `watcher.py` starts a `watchdog` Observer on all whitelisted directories.
* **Debouncing:** File events are debounced with a 1-second delay to handle rapid IDE saves without hammering the database.
* **Automatic Sync:** Create, modify, delete, and move events update the SQLite database in real-time.

### Heuristic Tagging
* **`heuristics.py`** categorizes every indexed file with a semantic tag (e.g., "Backend Logic", "Data / Datasets", "Notebooks") based on folder patterns and file extensions.
* Tags are stored in the `category` column and displayed in `search_files` tool results, giving the AI instant contextual awareness.

## 6. Packaging & Distribution
Lithe is packaged as a standalone Windows application (`.exe`) using a two-step build process:
1. **PyInstaller**: Compiles the Python backend and all dependencies (including FastAPI, Google GenAI, watchdog, httpx) into a self-contained executable folder.
2. **electron-builder**: Packages the Electron frontend, embeds the PyInstaller backend as `extraResources`, and generates an NSIS installer.

In production, the Electron main process spawns the bundled PyInstaller backend (`lithe-server.exe`) instead of relying on a system Python installation. Configuration variables (`.env` and the SQLite database) are loaded from the user's AppData directory (`%APPDATA%\Lithe`) to ensure persistence and proper permissions without requiring admin rights.

## 7. Error Handling & Logging
Lithe uses a unified crash logging architecture across all processes. All log files are stored in `%APPDATA%/Lithe/logs` (production) or `.lithe/logs` (development).

- **Backend Engine**: Uses `logging.handlers.RotatingFileHandler` combined with a custom `SecretsMasker` to redact `GEMINI_API_KEY`. Exceptions are caught globally by FastAPI (`@app.exception_handler`) and inside unhandled startup threads (like the file indexer). Logs are written to `backend.log`.
- **Electron Main**: Captures native `uncaughtException`, `unhandledRejection`, and IPC invocation errors. Writes to `electron.log` using a lightweight, native `fs` file rotation (max 5MB, 1 backup). It also captures the Python backend's raw stdout/stderr streams into a separate `child.log`.
- **Renderer UI**: Uses a React `ErrorBoundary` and global `window.onerror` to capture component crashes and unhandled UI exceptions. These errors are bridged via IPC to the main process and written to `electron.log`. A `[VIEW LOGS]` button in the System Panel opens the log folder natively.

## 8. Testing & Evaluation

Two layers, kept deliberately separate (full detail in `docs/TESTING.md`):

- **Unit + contract suite** (`python -m pytest`) — offline and deterministic.
  Network is blocked by an autouse fixture. `tests/test_tool_contract.py`
  drives the real `brain.chat()` with a scripted LLM client that returns
  genuine `google.genai.types` objects, which is what makes it able to detect
  a mismatch between the tool names declared to the model and the names the
  dispatch map can resolve.
- **Capability evaluation** (`LITHE_EVAL=1 python -m pytest -m eval`) — opt-in,
  drives a real LLM against a synthetic corpus and prints a scorecard.
  Excluded from normal runs via `addopts = -m "not eval"`. It scores Ollama by
  default: Gemini's free tier allows 20 requests/day per model and one pass
  needs ~80-100, so a free key can never complete a run. See TESTING.md.

Known defects are recorded as `xfail(strict=True)` tests rather than prose, so
they are listed on every run and cannot be fixed — or forgotten — silently.

`brain.chat()` separates transport failures (which fall back to Ollama) from
defects in Lithe (which are logged with a traceback and reported as internal
errors, without switching engines). The evaluation still asserts which engine
served each case, so a 503 is never scored as the model giving a poor answer.

## 9. Key Dependencies

### Python Backend
| Package | Version | Purpose |
|---------|---------|---------|
| `google-genai` | latest | Official Google GenAI SDK for Gemini |
| `python-dotenv` | latest | `.env` file loading |
| `fastapi` | latest | REST API framework |
| `uvicorn[standard]` | latest | ASGI server |
| `watchdog` | latest | File system event monitoring |
| `httpx` | latest | HTTP client for Ollama fallback |

### Electron Frontend
| Package | Version | Purpose |
|---------|---------|---------|
| `electron` | 36.x | Desktop shell |
| `react` | 19.x | UI framework |
| `typescript` | 5.x | Type safety |
| `electron-vite` | 3.x | Build toolchain |
| `@electron-toolkit/utils` | latest | Electron utilities |