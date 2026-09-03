# docs/FEATURES.md — Lithe Feature Checklist

> Dense checklist of implemented features and capabilities. Historical logs in [`docs/ARCHIVE_LOGS.md`](file:///d:/Lithe/docs/ARCHIVE_LOGS.md).

---

## Core Features (F-01 to F-07)
- [x] **F-01: Core LLM Connection** — Gemini API client (`google-genai`), secure `.env` key loading, system prompts.
- [x] **F-02: Chat Interface** — Three-pane HUD desktop UI (Electron 36 + React 19 + TypeScript).
- [x] **F-03: Local Directory Indexer** — SQLite database mapping whitelisted folders, exclusion lists (`node_modules`, `.git`, binaries).
- [x] **F-04: File Context Injection** — Regex detection of `name.ext` tokens in the prompt, exact-basename SQLite lookup, whole-file injection (100KB head-truncated). Note: this is filename-triggered injection, not retrieval — there is no content index, so a query that does not name a file retrieves nothing. Content search is tracked as a future upgrade.
- [x] **F-05: Task Execution & Safety** — LLM function calling with interactive UI proposal cards (`ToolProposalCard`) and execution diffs.
- [x] **F-06: Candid Persona & Safeword** — Dual system prompts (critical candor vs. compliant override via `"Override Lithe"`).
- [x] **F-07: Desktop Packaging** — PyInstaller bundled backend + electron-builder NSIS standalone Windows installer.

---

## Upgrades & Advanced Capabilities (U-01 to U-15)
- [x] **U-01: SQLite WAL Mode** — `PRAGMA journal_mode=WAL` + `busy_timeout=5000` for safe concurrent indexer/LLM access.
- [x] **U-02: Circuit Breakers** — 30s hard timeouts via `concurrent.futures`, path sanitization (normalized `realpath`, protected system dir guards).
- [x] **U-03: Ollama Fallback** — Automatic offline failover to local models (`llama3.1`) with health check and native tool-calling.
- [x] **U-04: Event-Driven Memory** — `watchdog` file watcher with 1s debouncing for real-time filesystem change detection.
- [x] **U-05: Heuristic Tagging** — Pure-function categorization engine (`heuristics.py`) adding semantic domain tags to indexed files.
- [x] **U-06: HUD Redesign** — Monospace technical UI (amber `#ffb020` on near-black `#08080a`, hairline borders, three-pane layout).
- [x] **U-07: UX & UI Controls** — Dynamic folder whitelist picker, live watcher log console with WebSocket broadcaster ring buffer.
- [x] **U-08: Indexing Efficiency** — Startup modification reconciliation to eliminate redundant scans; smart binary extension filtering.
- [x] **U-09: Fast-Fail Fallback** — 5s connection timeout for instantaneous failover to local compute; live active engine badge.
- [x] **U-10: Audit Log Export** — Complete decision, tool proposal, and execution history exportable via JSON/CSV.
- [x] **U-11: Data Science Tools** — LLM tools for dataset profiling (`profile_data`) and chart rendering (`inline_chart` via matplotlib SSE). *Non-functional on the Gemini path until 2026-09-03: the SDK named them after the wrapper closures, so dispatch never resolved them.*
- [x] **U-12: Watch Rules Storage** — Persistent automation rules table (`watch_rules`) and LLM management tools (`create_watch_rule`, `list_watch_rules`, `delete_watch_rule`). *Same wrapper-naming defect as U-11; fixed 2026-09-03.*
- [x] **U-13: Watch-and-Summarize Trigger** — Automatic background summarization dispatch on matching file creation events.
- [x] **U-14: Watch-and-Summarize UI Delivery** — Live WebSocket streaming and pending summary catch-up rendered with `watch>` prefix.
- [x] **U-15: System Tray & Global Hotkey** — Native Windows tray icon with restore/quit menu and `Ctrl+Shift+L` global summon hotkey.
- [x] **U-16: Evaluation Harness** — Scripted-LLM contract tests over the agent loop (`tests/test_tool_contract.py`), retrieval and safeword coverage, plus an opt-in live capability evaluation (`tests/eval/`) that scores tool selection, argument correctness, retrieval sufficiency, refusal and hallucination against a synthetic corpus. See `docs/TESTING.md`.