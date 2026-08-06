# docs/UPGRADE_PLAN.md — Lithe Architecture Enhancements

**Status:** ✅ ALL PHASES COMPLETE (as of 2026-08-04)
**Audience:** AntiGravity AI Agent, Lead Developer
**Objective:** Execute a series of robust, fail-safe, and efficiency upgrades to Lithe's core architecture. Implement sequentially by priority.

---

## Phase 1: Foundation & Safety (High Priority) — ✅ COMPLETE

### 1. SQLite Write-Ahead Logging (WAL) — ✅ Done
* **Implementation:** `memory.py` — `PRAGMA journal_mode=WAL;` + `PRAGMA busy_timeout=5000;`
* **Files Modified:** `src/backend/memory.py`

### 2. "Circuit Breakers" for Tool Execution — ✅ Done
* **Implementation:** `tools.py` — path validation (empty, null bytes, protected system dirs), `os.path.realpath()` normalization, 30-second timeout via `concurrent.futures.ThreadPoolExecutor`
* **Files Modified:** `src/backend/tools.py`, `src/backend/brain.py` (TypeError catch)

---

## Phase 2: Reliability (Medium Priority) — ✅ COMPLETE

### 3. The "Fallback" Pattern — ✅ Done
* **Implementation:** `brain.py` — dedicated `_ollama_chat()` with proper `/api/chat` message roles, `_check_ollama_available()` health check, `httpx` HTTP client, configurable via `.env`
* **Files Modified:** `src/backend/brain.py`, `src/backend/config.py`, `.env.example`

---

## Phase 3: Efficiency & Context (Next-Gen Features) — ✅ COMPLETE

### 4. Event-Driven Memory — ✅ Done
* **Implementation:** `watcher.py` — `watchdog` Observer with 1s debouncing, EXCLUDED_DIRS filtering, auto SQLite upsert/delete
* **Files Created:** `src/backend/watcher.py`
* **Files Modified:** `src/backend/server.py` (startup: index → watch)

### 5. The Heuristic Graph — ✅ Done
* **Implementation:** `heuristics.py` — pure-function engine with 15+ folder rules and 20+ extension rules; category column in SQLite schema
* **Files Created:** `src/backend/heuristics.py`
* **Files Modified:** `src/backend/memory.py` (schema migration), `src/backend/indexer.py` (apply tags), `src/backend/brain.py` (display tags in search_files)