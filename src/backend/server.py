"""
Lithe — HTTP Server (F-02: Backend Communication Bridge)

A lightweight FastAPI server that exposes the brain.chat() function
over HTTP so the Electron renderer can communicate with the Python
backend.

Endpoints:
    GET  /api/health  — Returns {"status": "ok"} for readiness checks.
    POST /api/chat    — Accepts {"message": "..."}, returns {"response": "..."}.

Run:
    python -m src.backend.server
"""

import threading

import uvicorn
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.backend.brain import chat
from src.backend.indexer import walk_and_index
from src.backend.watcher import start_watcher

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="Lithe Backend", version="0.1.0")


@app.on_event("startup")
def auto_index_and_watch():
    """Index whitelisted directories on boot, then start the file watcher."""
    def _index_then_watch():
        walk_and_index()
        start_watcher()

    print("[Lithe] Auto-indexing whitelisted directories in the background...")
    thread = threading.Thread(target=_index_then_watch, daemon=True)
    thread.start()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:5174",   # Vite fallback port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health_check():
    """Readiness probe for the Electron main process."""
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Send a message to Lithe and receive a response.

    The brain module handles safeword detection (F-06) and
    LLM provider selection automatically.
    """
    result = chat(request.message)
    return ChatResponse(response=result)


@app.post("/api/index")
async def index_endpoint(background_tasks: BackgroundTasks):
    """Trigger the local directory indexer in the background."""
    background_tasks.add_task(walk_and_index)
    return {"status": "indexing_started"}


@app.get("/api/status")
async def status_endpoint():
    """Returns live system status for the HUD panels.

    Feeds:
      - [01] INDEX panel: watched dirs, file counts, watcher status
      - [03] SYSTEM panel: server mode, safeword state
    """
    from src.backend.config import INDEX_WHITELIST
    from src.backend.memory import get_file_count_by_directory
    from src.backend import watcher as watcher_module

    watched_dirs = get_file_count_by_directory(INDEX_WHITELIST)
    evt_time = watcher_module.last_event_time

    return {
        "watcher_active": evt_time is not None or len(INDEX_WHITELIST) > 0,
        "watched_dirs": watched_dirs,
        "last_event_time": evt_time,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(
        "src.backend.server:app",
        host="127.0.0.1",
        port=8321,
        reload=False,
        log_level="info",
    )
