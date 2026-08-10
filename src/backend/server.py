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
        from src.backend.changelog import generate_changelog
        generate_changelog()
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
    from src.backend.config import NEEDS_ONBOARDING
    return {"status": "ok", "needs_onboarding": NEEDS_ONBOARDING}

class OnboardingRequest(BaseModel):
    api_key: str

@app.post("/api/onboarding")
async def onboarding_endpoint(request: OnboardingRequest):
    """Saves the API key to .env and restarts the server."""
    from src.backend.config import _ACTIVE_ENV_PATH, _APPDATA_ENV
    import sys
    import os
    import platform
    
    env_path = _ACTIVE_ENV_PATH or _APPDATA_ENV
    
    # Ensure directory exists
    env_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write to .env
    with open(env_path, "a", encoding="utf-8") as f:
        f.write(f"\nGEMINI_API_KEY={request.api_key}\n")
        
    return {"status": "ok", "message": "Key saved. Restarting..."}


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Primary chat endpoint: passes user message to Lithe's brain."""
    from src.backend.brain import chat
    result = chat(request.message)
    if isinstance(result, dict):
        return ChatResponse(response="", tool_proposal=result.get("tool_proposal"))
    return ChatResponse(response=result)


@app.get("/api/chat/stream")
async def chat_stream_endpoint(message: str):
    """SSE streaming endpoint: streams tokens from Lithe's brain as they're generated.

    Sends Server-Sent Events with JSON payloads:
        data: {"type": "token", "content": "..."}
        data: {"type": "tool_proposal", "proposal": {...}}
        data: {"type": "done", "tokens": {...}}
    """
    import json as _json
    from starlette.responses import StreamingResponse
    from src.backend.brain import chat_stream

    def event_generator():
        for event in chat_stream(message):
            yield f"data: {_json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/api/chat/tool_response", response_model=ChatResponse)
async def tool_response_endpoint(request: ToolResponseRequest):
    """Endpoint for user to accept or reject a pending tool proposal."""
    from src.backend.brain import handle_tool_response
    result = handle_tool_response(request.accept)
    if isinstance(result, dict):
        return ChatResponse(response="", tool_proposal=result.get("tool_proposal"))
    return ChatResponse(response=result)

@app.get("/api/chat/history")
async def chat_history_endpoint():
    """Returns the persistent chat history."""
    from src.backend.memory import get_chat_history
    import json
    
    history = get_chat_history()
    formatted = []
    for row in history:
        msg = {
            "id": row["id"],
            "role": row["role"],
            "content": row["content"]
        }
        if row["tool_proposal_json"]:
            proposal = json.loads(row["tool_proposal_json"])
            msg["tool_proposal"] = proposal
        if row["tool_resolution"]:
            msg["tool_resolution"] = json.loads(row["tool_resolution"])
            
        formatted.append(msg)
        
    return {"history": formatted}


class SafewordToggleRequest(BaseModel):
    active: bool

@app.post("/api/config/safeword")
async def toggle_safeword(request: SafewordToggleRequest):
    import src.backend.brain as brain
    brain.session_safeword_active = request.active
    return {"status": "ok", "session_safeword_active": brain.session_safeword_active}


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


@app.get("/api/search")
async def search_endpoint(q: str):
    """Direct search against the file index."""
    from src.backend.memory import search_files_by_name
    results = search_files_by_name(q)
    return {"results": results}

# ---------------------------------------------------------------------------
# Undo Stack Endpoints (Feature 3)
# ---------------------------------------------------------------------------

@app.get("/api/undo/history")
async def undo_history_endpoint():
    """Returns recent reversible actions."""
    from src.backend.memory import get_action_history
    return {"history": get_action_history()}

from pydantic import BaseModel
class UndoRequest(BaseModel):
    action_id: int

@app.post("/api/undo")
async def undo_endpoint(request: UndoRequest):
    """Reverts a specific action."""
    from src.backend.memory import get_action_by_id, delete_action
    import json
    import os
    
    action = get_action_by_id(request.action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
        
    if not action["reversible"]:
        raise HTTPException(status_code=400, detail="Action is not reversible")
        
    details = json.loads(action["details_json"])
    tool_name = action["tool_name"]
    
    try:
        if tool_name == "rename_file":
            os.rename(details["destination"], details["source"])
        elif tool_name == "delete_file":
            # Recreate file with old content
            os.makedirs(os.path.dirname(os.path.abspath(details["path"])), exist_ok=True)
            with open(details["path"], "w", encoding="utf-8") as f:
                f.write(details["content"])
        elif tool_name == "write_file":
            if details["is_new"]:
                if os.path.exists(details["path"]):
                    os.remove(details["path"])
            else:
                with open(details["path"], "w", encoding="utf-8") as f:
                    f.write(details["old_content"])
                    
        delete_action(request.action_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/api/status")
async def status_endpoint():
    """Returns background indexer status for the frontend HUD."""
    from src.backend.watcher import last_event_time, _observer
    from src.backend.config import INDEX_WHITELIST, EXCLUDED_EXTENSIONS, TOKEN_BUDGET_WARNING
    from src.backend.memory import get_file_count_by_directory
    import src.backend.brain as brain

    watcher_active = _observer is not None and _observer.is_alive()

    return {
        "watcher_active": watcher_active,
        "watched_dirs": get_file_count_by_directory(INDEX_WHITELIST),
        "excluded_extensions": EXCLUDED_EXTENSIONS,
        "last_event_time": last_event_time,
        "tokens": brain.last_token_counts,
        "token_budget_warning": TOKEN_BUDGET_WARNING,
        "active_engine": brain.active_engine,
        "session_safeword_active": brain.session_safeword_active,
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
