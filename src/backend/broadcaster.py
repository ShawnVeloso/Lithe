"""
Lithe — Event Broadcaster

Maintains a ring buffer of recent indexing events and broadcasts
new events to connected WebSocket clients via a batched queue.
"""

import time
import asyncio
from collections import deque
from typing import Dict, Any, List

# In-memory history buffer for clients that connect mid-session
MAX_HISTORY = 500
_history_buffer: deque = deque(maxlen=MAX_HISTORY)

# List of active queues for connected WebSocket clients
_subscribers: List[asyncio.Queue] = []

def broadcast_event(event_type: str, path: str):
    """
    Called from synchronous threads (watcher or indexer) to push a new event.
    """
    event = {
        "type": event_type,
        "path": path,
        "timestamp": time.time()
    }
    
    _history_buffer.append(event)
    
    # Push to all active subscribers
    for q in _subscribers:
        # Since this might be called from a non-asyncio thread (e.g. watchdog),
        # we use put_nowait which is safe if the queue is unbounded.
        # However, to be thread-safe with asyncio, we should use call_soon_threadsafe
        # if the queue belongs to an event loop.
        
        # To avoid complex loop management here, we can assume the queue has a loop reference
        # but asyncio.Queue.put_nowait is not thread-safe.
        # We will attach the loop to the queue when we create it.
        try:
            loop = getattr(q, "_lithe_loop", None)
            if loop and loop.is_running():
                loop.call_soon_threadsafe(q.put_nowait, event)
            else:
                q.put_nowait(event)
        except Exception:
            pass

def get_history() -> List[Dict[str, Any]]:
    """Returns the last N events."""
    return list(_history_buffer)

def subscribe(loop: asyncio.AbstractEventLoop) -> asyncio.Queue:
    """Creates a new queue for a WebSocket client to listen to."""
    q = asyncio.Queue()
    setattr(q, "_lithe_loop", loop)
    _subscribers.append(q)
    return q

def unsubscribe(q: asyncio.Queue):
    """Removes a client's queue."""
    if q in _subscribers:
        _subscribers.remove(q)
