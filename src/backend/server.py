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

import asyncio
import uvicorn
from fastapi import FastAPI, BackgroundTasks, WebSocket, WebSocketDisconnect
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

class IndexRequest(BaseModel):
    path: str

class ExtensionRequest(BaseModel):
    ext: str

class ChatResponse(BaseModel):
    response: str
    tool_proposal: dict | None = None

class ToolResponseRequest(BaseModel):
    accept: bool

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health_check():
    """Readiness probe for the Electron main process."""
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Primary chat endpoint: passes user message to Lithe's brain."""
    from src.backend.brain import chat
    result = chat(request.message)
    if isinstance(result, dict):
        return ChatResponse(response="", tool_proposal=result.get("tool_proposal"))
    return ChatResponse(response=result)

@app.post("/api/chat/tool_response", response_model=ChatResponse)
async def tool_response_endpoint(request: ToolResponseRequest):
    """Endpoint for user to accept or reject a pending tool proposal."""
    from src.backend.brain import handle_tool_response
    result = handle_tool_response(request.accept)
    if isinstance(result, dict):
        return ChatResponse(response="", tool_proposal=result.get("tool_proposal"))
    return ChatResponse(response=result)


@app.post("/api/index")
async def index_endpoint(background_tasks: BackgroundTasks):
    """Trigger the local directory indexer in the background."""
    background_tasks.add_task(walk_and_index)
    return {"status": "indexing_started"}

@app.post("/api/index/add")
async def add_index_endpoint(request: IndexRequest, background_tasks: BackgroundTasks):
    """Adds a new directory to the whitelist, indexes it, and starts watching it."""
    from src.backend.config import update_whitelist
    from src.backend.watcher import add_watch
    from src.backend.indexer import walk_and_index_path
    
    update_whitelist(request.path)
    add_watch(request.path)
    background_tasks.add_task(walk_and_index_path, request.path)
    return {"status": "added", "path": request.path}

@app.delete("/api/index/remove")
async def remove_index_endpoint(request: IndexRequest):
    """Removes a directory from the whitelist, stops watching it, and deletes its files from DB."""
    from src.backend.config import update_whitelist
    from src.backend.watcher import remove_watch
    from src.backend.memory import delete_files_by_root_directory
    
    update_whitelist(request.path, remove=True)
    remove_watch(request.path)
    delete_files_by_root_directory(request.path)
    return {"status": "removed", "path": request.path}


@app.post("/api/extensions/add")
async def add_extension_endpoint(request: ExtensionRequest, background_tasks: BackgroundTasks):
    """Adds a new extension to the excluded list and removes matching files from DB."""
    from src.backend.config import update_excluded_extensions
    from src.backend.memory import delete_files_by_extension
    
    update_excluded_extensions(request.ext)
    background_tasks.add_task(delete_files_by_extension, request.ext)
    return {"status": "added", "ext": request.ext}

@app.delete("/api/extensions/remove")
async def remove_extension_endpoint(request: ExtensionRequest, background_tasks: BackgroundTasks):
    """Removes an extension from the excluded list and triggers a background re-index."""
    from src.backend.config import update_excluded_extensions
    
    update_excluded_extensions(request.ext, remove=True)
    background_tasks.add_task(walk_and_index)
    return {"status": "removed", "ext": request.ext}


@app.get("/api/status")
async def status_endpoint():
    """Returns background indexer status for the frontend HUD."""
    from src.backend.watcher import last_event_time, _observer
    from src.backend.config import INDEX_WHITELIST, EXCLUDED_EXTENSIONS
    from src.backend.memory import get_file_count_by_directory
    from src.backend.brain import last_token_counts, active_engine

    watcher_active = _observer is not None and _observer.is_alive()

    return {
        "watcher_active": watcher_active,
        "watched_dirs": get_file_count_by_directory(INDEX_WHITELIST),
        "excluded_extensions": EXCLUDED_EXTENSIONS,
        "last_event_time": last_event_time,
        "tokens": last_token_counts,
        "active_engine": active_engine,
    }


@app.websocket("/ws/watcher-log")
async def websocket_watcher_log(websocket: WebSocket):
    """Streams file system events to the frontend UI."""
    await websocket.accept()
    
    from src.backend.broadcaster import get_history, subscribe, unsubscribe
    
    # Send historical events immediately
    history = get_history()
    if history:
        await websocket.send_json({"events": history})
        
    loop = asyncio.get_running_loop()
    q = subscribe(loop)
    
    try:
        while True:
            # Batching rapid-fire events
            batch = []
            # Wait for at least one event
            event = await q.get()
            batch.append(event)
            
            # Grab any other events currently in the queue without waiting
            while not q.empty():
                batch.append(q.get_nowait())
            
            # Send the batch
            if batch:
                await websocket.send_json({"events": batch})
                
            # Throttle to max 10 messages per second to avoid flooding
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WebSocket] Error: {e}")
    finally:
        unsubscribe(q)

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
