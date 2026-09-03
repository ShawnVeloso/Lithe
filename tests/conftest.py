"""Shared fixtures for the Lithe test suite.

Two of these are autouse and exist for safety rather than convenience:

`reset_brain_state` — brain.py keeps the whole session in module globals
(_chat_history, _pending_session, ...). Without a reset between tests, a test
that leaves a pending tool proposal behind changes the outcome of the next one.

`no_real_network` — blocks httpx so a unit test cannot quietly succeed by
talking to an Ollama instance that happens to be running on the dev machine.

Note also that importing src.backend.brain runs _load_history() at module
scope, which reads DB_PATH. Tests must therefore patch DB_PATH before that
import is triggered, which is why isolated_db patches both memory.DB_PATH and
config.DB_PATH.
"""

import pytest

from src.backend import config, memory


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Point every DB consumer at a throwaway SQLite file and initialise it.

    The existing suite patched DB_PATH three inconsistent ways (patch() with a
    Path, monkeypatch with a str, memory-only vs memory+config). This unifies
    on: both modules, str, initialised.
    """
    db_file = str(tmp_path / "lithe_test.db")
    monkeypatch.setattr(memory, "DB_PATH", db_file)
    monkeypatch.setattr(config, "DB_PATH", db_file)
    memory.init_db()
    return db_file


# Module globals in brain.py that carry state between requests. Anything added
# here is saved before a test and restored after it.
_BRAIN_GLOBALS = (
    "_chat_history",
    "_current_conversation_id",
    "_pending_session",
    "_pending_tool_calls",
    "_pending_config",
    "_pending_tool_map",
    "_pending_ollama_messages",
    "_pending_ollama_tool_calls",
    "_pending_ollama_tool_map",
    "session_safeword_active",
    "active_engine",
    "last_token_counts",
    "_client",
)


@pytest.fixture(autouse=True)
def reset_brain_state():
    """Snapshot brain's module globals and put them back after each test."""
    try:
        from src.backend import brain
    except Exception:
        # brain imports the Gemini SDK and touches the DB at import time; if it
        # cannot load, tests that don't need it should still run.
        yield
        return

    saved = {name: getattr(brain, name, None) for name in _BRAIN_GLOBALS}
    # Start each test from a clean session rather than whatever the real DB
    # happened to load at import time.
    brain._chat_history = []
    brain._pending_session = None
    brain._pending_tool_calls = None
    brain._pending_config = None
    brain._pending_tool_map = None
    brain.session_safeword_active = False
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(brain, name, value)


@pytest.fixture(autouse=True)
def no_real_network(request, monkeypatch):
    """Fail loudly if a non-live test tries to make an HTTP call.

    Opted out of by the `live` and `eval` markers.
    """
    if request.node.get_closest_marker("live") or request.node.get_closest_marker("eval"):
        yield
        return

    import httpx

    def _blocked(*args, **kwargs):
        raise AssertionError(
            "This test attempted a real network call. Mark it @pytest.mark.live "
            "if that is intended, otherwise stub the client."
        )

    monkeypatch.setattr(httpx, "post", _blocked)
    monkeypatch.setattr(httpx, "get", _blocked)
    yield


@pytest.fixture
def scripted_gemini(monkeypatch):
    """Install a ScriptedGeminiClient as brain's LLM client.

    Returns a factory so a test can queue the exact conversation it wants:

        client = scripted_gemini([function_call_response("search_files", {...}),
                                  text_response("here you go")])
    """
    from src.backend import brain
    from tests.support.fake_gemini import ScriptedGeminiClient

    def _install(responses=None, default="Done."):
        client = ScriptedGeminiClient(responses, default=default)
        monkeypatch.setattr(brain, "_client", client)
        return client

    return _install


class Workspace:
    """A small on-disk corpus whose files are registered in the file index."""

    def __init__(self, root):
        self.root = root

    def add(self, relative_path: str, content, binary: bool = False):
        """Write a file and index it the way the real indexer would."""
        target = self.root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if binary:
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")
        stat = target.stat()
        memory.upsert_files([{
            "path": str(target),
            "name": target.name,
            "extension": target.suffix,
            "size_bytes": stat.st_size,
            "modified_at": stat.st_mtime,
            "indexed_at": stat.st_mtime,
            "category": "",
        }])
        return target


@pytest.fixture
def indexed_workspace(tmp_path, isolated_db):
    """Files are inserted through memory.upsert_files, so retrieval behaves
    exactly as it does in production."""
    root = tmp_path / "workspace"
    root.mkdir()
    return Workspace(root)
