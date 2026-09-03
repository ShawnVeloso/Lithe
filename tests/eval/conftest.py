"""Fixtures and scorecard reporting for the live capability evaluation.

Nothing here runs unless the suite is invoked with `-m eval` AND LITHE_EVAL=1
AND a Gemini key is configured. See docs/TESTING.md.

The evaluation deliberately runs against a small synthetic corpus rather than
the user's real drive: scores are only meaningful if the inputs are identical
between runs and between machines.
"""

import os
import time

import pytest

def pytest_collection_modifyitems(config, items):
    """Skip the whole eval suite unless it was explicitly asked for."""
    if os.getenv("LITHE_EVAL") != "1":
        skip = pytest.mark.skip(reason="set LITHE_EVAL=1 to run the capability evaluation")
        for item in items:
            if "eval" in item.keywords:
                item.add_marker(skip)
        return

    from src.backend import config as lithe_config
    if not lithe_config.GEMINI_API_KEY:
        skip = pytest.mark.skip(reason="no GEMINI_API_KEY configured")
        for item in items:
            if "eval" in item.keywords:
                item.add_marker(skip)


class RecordingClient:
    """Delegates to the real Gemini client while recording tool calls.

    brain.chat() returns only the final text, so without this there is no way
    to tell which tool the model chose — which is most of what we want to
    measure.
    """

    def __init__(self, inner):
        self._inner = inner
        self.tool_calls = []  # list of (name, args)

    @property
    def models(self):
        return _RecordingModels(self)


class _RecordingModels:
    def __init__(self, owner):
        self._owner = owner

    def generate_content(self, **kwargs):
        response = self._owner._inner.models.generate_content(**kwargs)
        for call in (response.function_calls or []):
            self._owner.tool_calls.append((call.name, dict(call.args or {})))
        return response

    def generate_content_stream(self, **kwargs):
        return self._owner._inner.models.generate_content_stream(**kwargs)


class EvalHarness:
    def __init__(self, corpus_dir):
        self.corpus = corpus_dir

    def ask(self, prompt: str, transport_retries: int = 3) -> dict:
        """Run one turn and report what Lithe did as well as what it said.

        Gemini returns 503 "high demand" often enough to distort a score, and
        brain.chat() swallows it into a silent Ollama fallback. Detect that via
        active_engine and retry, so transport noise is not counted as a
        capability failure.
        """
        for attempt in range(transport_retries):
            outcome = self._ask_once(prompt)
            if outcome["engine"] == "gemini":
                return outcome
            if attempt < transport_retries - 1:
                time.sleep(5 * (attempt + 1))
        return outcome

    def _ask_once(self, prompt: str) -> dict:
        from src.backend import brain

        real_client = brain._client
        recorder = RecordingClient(real_client)
        brain._client = recorder
        brain._chat_history = []
        brain._pending_session = None
        brain._pending_tool_calls = None
        try:
            answer = brain.chat(prompt)
        finally:
            brain._client = real_client

        # A tool proposal short-circuits before any text is produced.
        if isinstance(answer, dict):
            text = answer.get("text", "") or ""
        else:
            text = answer or ""

        return {
            "text": text,
            "tool_calls": recorder.tool_calls,
            "tool_names": [name for name, _ in recorder.tool_calls],
            "engine": brain.active_engine,
        }


@pytest.fixture(scope="session")
def corpus(tmp_path_factory):
    """Build the fixed evaluation corpus on disk."""
    root = tmp_path_factory.mktemp("lithe_eval_corpus")

    rows = ["month,region,revenue,units"]
    for i in range(1, 13):
        rows.append(f"2026-{i:02d},north,{1000 + i * 37},{20 + i}")
    (root / "sales_q3.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")

    (root / "notes_meeting.md").write_text(
        "# Planning meeting\n\n"
        "Attendees discussed the rollout timeline.\n"
        "The agreed internal code word is ZEPHYR-441.\n"
        "Next review is scheduled for the following quarter.\n",
        encoding="utf-8",
    )

    # Larger than retrieval's 100KB cap, with a marker only in the tail — so a
    # model claiming to know the last line is fabricating.
    filler = ("lorem ipsum dolor sit amet " * 40 + "\n") * 110
    (root / "bigfile.txt").write_text(filler + "TAIL_MARKER_OMEGA\n", encoding="utf-8")

    (root / "readme.md").write_text("# Readme\n\nA sample project.\n", encoding="utf-8")
    (root / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\xff\xfe\xfd" * 64)

    return root


@pytest.fixture(scope="session")
def harness(corpus, tmp_path_factory):
    """Point Lithe at a throwaway DB and the corpus, then index it."""
    from src.backend import config as lithe_config
    from src.backend import indexer, memory

    db_file = str(tmp_path_factory.mktemp("lithe_eval_db") / "eval.db")
    original_db = memory.DB_PATH
    original_whitelist = list(lithe_config.INDEX_WHITELIST)

    memory.DB_PATH = db_file
    lithe_config.DB_PATH = db_file
    lithe_config.INDEX_WHITELIST.clear()
    lithe_config.INDEX_WHITELIST.append(str(corpus))
    memory.init_db()
    indexer.walk_and_index()

    yield EvalHarness(corpus)

    memory.DB_PATH = original_db
    lithe_config.DB_PATH = original_db
    lithe_config.INDEX_WHITELIST.clear()
    lithe_config.INDEX_WHITELIST.extend(original_whitelist)


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    from tests.eval import scorecard
    scorecard.render(terminalreporter.write_line)
