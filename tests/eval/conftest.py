"""Fixtures and scorecard reporting for the live capability evaluation.

Nothing here runs unless the suite is invoked with `-m eval` AND LITHE_EVAL=1.
See docs/TESTING.md.

**Which engine gets scored.** `LITHE_EVAL_ENGINE` selects it, defaulting to
`ollama`. Gemini's free tier allows 20 generate_content requests per day per
model, and one pass of this suite needs roughly 80-100 (cases x repeats, and a
tool case costs several calls) -- so a Gemini run cannot complete on a free key
no matter how long you wait for a reset. Three attempts proved that the
expensive way, the last of them grinding for 67 minutes to report a score made
entirely of fallbacks. Ollama is local, free and repeatable, and the scorecard
was always about the delta between branches rather than the absolute number.

Scoring Ollama also measures something that was never measured at all: with a
free Gemini key exhausted after 20 requests, the fallback path is where real
users spend much of their time.

The evaluation deliberately runs against a small synthetic corpus rather than
the user's real drive: scores are only meaningful if the inputs are identical
between runs and between machines.
"""

import os
import time

import pytest

ENGINE = os.getenv("LITHE_EVAL_ENGINE", "ollama").strip().lower()

# Base seed for Ollama sampling; each repeat uses EVAL_SEED + n. Change it to
# resample the whole suite deliberately rather than by accident.
EVAL_SEED = int(os.getenv("LITHE_EVAL_SEED", "20260905"))

# Set when the run hits something that makes further cases meaningless (a
# Gemini quota wall, an Ollama that stopped answering). Remaining cases skip
# rather than scoring zero for a reason that has nothing to do with Lithe.
ABORT = {"reason": None}


def pytest_collection_modifyitems(config, items):
    """Skip the whole eval suite unless it was explicitly asked for."""
    def skip_all(reason):
        marker = pytest.mark.skip(reason=reason)
        for item in items:
            if "eval" in item.keywords:
                item.add_marker(marker)

    if os.getenv("LITHE_EVAL") != "1":
        skip_all("set LITHE_EVAL=1 to run the capability evaluation")
        return

    if ENGINE not in ("ollama", "gemini"):
        skip_all(f"LITHE_EVAL_ENGINE={ENGINE!r} is not one of: ollama, gemini")
        return

    reason = _ollama_unusable_reason() if ENGINE == "ollama" else _gemini_unusable_reason()
    if reason:
        skip_all(reason)


def _ollama_unusable_reason():
    """Returns a human-readable reason if Ollama cannot serve the eval."""
    from src.backend import brain

    available = brain._ollama_models()
    if available is None:
        return (
            f"Ollama is not reachable at {brain.OLLAMA_URL}. Start it with "
            "`ollama serve` to run the evaluation."
        )
    if not brain._model_is_pulled(brain.OLLAMA_MODEL, available):
        installed = ", ".join(sorted(available)) or "none"
        return (
            f"Ollama does not have the configured model {brain.OLLAMA_MODEL!r} "
            f"(installed: {installed}). Pull it, or set OLLAMA_MODEL to one of "
            "those."
        )
    return None


def _gemini_unusable_reason():
    """Returns a human-readable reason if Gemini cannot serve the eval.

    One cheap call, because the alternative is grinding through every case
    (each retrying three times with backoff) to report a 0% that says nothing
    about Lithe. Note that passing this check is not a promise the run will
    finish: it proves one request is allowed, not the ~80-100 a full pass
    needs. is_quota_error() aborts the run if the wall arrives mid-suite.
    """
    from src.backend.config import GEMINI_API_KEY, GEMINI_MODEL
    from google import genai

    if not GEMINI_API_KEY:
        return "no GEMINI_API_KEY configured"

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        client.models.generate_content(model=GEMINI_MODEL, contents="ok")
        return None
    except Exception as e:
        text = str(e)
        if is_quota_error(text):
            return (
                "Gemini quota is exhausted (429) — the evaluation would score 0% "
                "for reasons that have nothing to do with Lithe. The free tier "
                "allows 20 requests/day per model and a full pass needs ~80-100, "
                "so consider LITHE_EVAL_ENGINE=ollama instead."
            )
        if "UNAVAILABLE" in text or "503" in text:
            return "Gemini is returning 503 (high demand); results would be noise."
        return f"Gemini pre-flight failed ({type(e).__name__}): {text[:120]}"


def is_quota_error(text: str) -> bool:
    return "RESOURCE_EXHAUSTED" in text or "429" in text


@pytest.fixture(autouse=True)
def stop_after_abort():
    """Skip any case queued behind a run-ending failure."""
    if ABORT["reason"]:
        pytest.skip(ABORT["reason"])
    yield


class RecordingClient:
    """Delegates to the real Gemini client while recording tool traffic.

    brain.chat() returns only the final text, so without this there is no way
    to tell which tool the model chose — which is most of what we want to
    measure. It records what tools *returned* as well, because knowing a tool
    was called says nothing about whether it worked: a call Lithe could not
    dispatch and a call that succeeded look identical from the outside.
    """

    def __init__(self, inner):
        self._inner = inner
        self.tool_calls = []    # list of (name, args)
        self.tool_results = []  # list of (name, result text)
        self.error = None

    @property
    def models(self):
        return _RecordingModels(self)


class _RecordingModels:
    def __init__(self, owner):
        self._owner = owner

    def generate_content(self, **kwargs):
        # Results of the calls executed so far ride out in *this* request, as
        # the function_response parts _execute_tool_calls appended to contents.
        self._harvest_results(kwargs.get("contents"))
        try:
            response = self._owner._inner.models.generate_content(**kwargs)
        except Exception as e:
            # brain turns a 429 into a silent Ollama fallback, so the harness
            # would otherwise see only "the engine changed" and keep retrying.
            self._owner.error = str(e)
            raise
        for call in (response.function_calls or []):
            self._owner.tool_calls.append((call.name, dict(call.args or {})))
        return response

    def _harvest_results(self, contents):
        """Pull function_response parts out of an outgoing request.

        Contents only grow within a turn, so anything past what has already
        been recorded is new — counting rather than de-duplicating by value, so
        that two identical searches are still two results.
        """
        found = []
        for content in contents or []:
            for part in getattr(content, "parts", None) or []:
                response = getattr(part, "function_response", None)
                if response is None:
                    continue
                payload = getattr(response, "response", None) or {}
                found.append((response.name or "", str(payload.get("result", ""))))
        self._owner.tool_results.extend(found[len(self._owner.tool_results):])

    def generate_content_stream(self, **kwargs):
        return self._owner._inner.models.generate_content_stream(**kwargs)


class UnavailableClient:
    """A Gemini client that always fails the way an unreachable one does.

    Used for LITHE_EVAL_ENGINE=ollama. Rather than calling _ollama_chat
    directly, this drives brain.chat() down the exact path a user gets when
    Gemini is down, so the fallback is scored as it actually behaves --
    including its lack of an agent loop.
    """

    @property
    def models(self):
        return self

    def generate_content(self, **kwargs):
        import httpx
        raise httpx.ConnectError("evaluation pinned to Ollama")

    def generate_content_stream(self, **kwargs):
        import httpx
        raise httpx.ConnectError("evaluation pinned to Ollama")


class OllamaRecorder:
    """Captures tool calls out of Ollama's /api/chat responses.

    The Gemini recorder wraps a client object; Ollama is spoken to with a bare
    httpx.post, so this wraps that instead. Production code is untouched either
    way -- an eval that needed brain.py to cooperate would be measuring
    something other than what ships.
    """

    def __init__(self):
        self.tool_calls = []   # what Lithe actually executed
        self.requested = []    # what the model asked for
        self.tool_results = []  # what those calls returned
        self._real_post = None

    def __enter__(self):
        import httpx
        self._real_post = httpx.post

        def recording_post(url, *args, **kwargs):
            if "/api/chat" in str(url):
                self._harvest_results(kwargs.get("json"))
            response = self._real_post(url, *args, **kwargs)
            if "/api/chat" in str(url):
                self._harvest(response)
            return response

        httpx.post = recording_post
        return self

    def __exit__(self, *exc):
        import httpx
        httpx.post = self._real_post
        return False

    def _harvest(self, response):
        """Separate what the model asked for from what Lithe ran.

        _ollama_chat takes `message["tool_calls"][0]` and stops -- there is no
        agent loop on this path. Recording every requested call as though it
        ran made multistep-profile-then-chart report "now passing" when the
        model had merely *named* both tools and Lithe executed one. A
        multi-step case has to be scored on execution or it measures nothing.
        """
        try:
            message = response.json().get("message", {})
        except Exception:
            return
        calls = message.get("tool_calls") or []
        for index, call in enumerate(calls):
            function = call.get("function", {})
            entry = (function.get("name", ""), dict(function.get("arguments") or {}))
            self.requested.append(entry)
            if index == 0:
                self.tool_calls.append(entry)

    def _harvest_results(self, payload):
        """Read what tools returned out of the *outgoing* request.

        Ollama gets a tool result as a `role: "tool"` message on the next
        request, and _ollama_drive_tool_rounds always loops back to post again
        after executing, so every result passes through here. Reading the
        request rather than asking brain.py keeps production code unaware it is
        being measured.

        Messages only grow within a turn, so anything past what has already
        been recorded is new.
        """
        messages = (payload or {}).get("messages") or []
        results = [
            (m.get("name", ""), str(m.get("content", "")))
            for m in messages
            if m.get("role") == "tool"
        ]
        self.tool_results.extend(results[len(self.tool_results):])


class EvalHarness:
    def __init__(self, corpus_dir, engine=ENGINE):
        self.corpus = corpus_dir
        self.engine = engine

    def ask(self, prompt: str, transport_retries: int = 3, repeat: int = 0) -> dict:
        """Run one turn and report what Lithe did as well as what it said.

        Gemini returns 503 "high demand" often enough to distort a score, and
        brain.chat() swallows it into a silent Ollama fallback. Detect that via
        active_engine and retry, so transport noise is not counted as a
        capability failure. A 429 is not retried: the quota is gone for the
        day, so the run is aborted instead.
        """
        for attempt in range(transport_retries):
            outcome = self._ask_once(prompt, repeat)
            if outcome.get("error") and is_quota_error(outcome["error"]):
                ABORT["reason"] = (
                    "Gemini quota exhausted mid-run (429). The free tier allows "
                    "20 requests/day per model and a full pass needs ~80-100; "
                    "the remaining cases would score 0% for reasons unrelated to "
                    "Lithe. Re-run with LITHE_EVAL_ENGINE=ollama."
                )
                pytest.skip(ABORT["reason"])
            if outcome["engine"] == self.engine:
                return outcome
            if attempt < transport_retries - 1:
                time.sleep(5 * (attempt + 1))
        return outcome

    def _ask_once(self, prompt: str, repeat: int = 0) -> dict:
        from src.backend import brain

        real_client = brain._client
        if self.engine == "ollama":
            brain._client = UnavailableClient()
            recorder = OllamaRecorder()
        else:
            recorder = RecordingClient(real_client)
            brain._client = recorder

        # Pin Ollama's sampling. The same payload with the same seed gives the
        # same output, so two runs of the suite are comparable; the seed varies
        # per repeat so the repeats still sample different outputs rather than
        # producing three copies of one answer. Without this the score swung
        # 86 -> 64 -> 86 on requests proved byte-identical, which makes noise
        # indistinguishable from a regression -- the one thing a measuring
        # instrument must never do.
        brain.OLLAMA_OPTIONS = (
            {"seed": EVAL_SEED + repeat} if self.engine == "ollama" else {}
        )

        brain._chat_history = []
        brain._context_blocks = []
        brain._pending_session = None
        brain._pending_tool_calls = None
        brain._pending_ollama_messages = None
        brain._pending_ollama_tool_calls = None
        try:
            if self.engine == "ollama":
                with recorder:
                    answer = brain.chat(prompt)
            else:
                answer = brain.chat(prompt)
        finally:
            brain._client = real_client
            brain.OLLAMA_OPTIONS = {}

        # A tool proposal short-circuits before any text is produced.
        chart = None
        if isinstance(answer, dict):
            text = answer.get("text", "") or ""
            # brain.chat() returns {"chart", "text"} when an image was produced.
            # Dropping it here is what let a real defect score as a pass: the
            # Ollama path generated a chart, swapped it for an acknowledgement
            # in the transcript, and returned only the acknowledgement -- so the
            # model truthfully relayed a delivery that never happened, while
            # `expect_tool: inline_chart` went on passing.
            chart = answer.get("chart")
            proposal = answer.get("tool_proposal")
            name = proposal.get("name", "") if proposal else ""
            if name and name not in [n for n, _ in recorder.tool_calls]:
                # A mutating tool pauses before its result comes back. On the
                # Gemini path the recorder never sees it at all; on the Ollama
                # path it is already in the /api/chat response, so record it
                # only if it is missing -- otherwise a single proposed delete
                # is reported as two calls.
                recorder.tool_calls.append(
                    (name, dict(proposal.get("args") or {}))
                )
        else:
            text = answer or ""

        requested = getattr(recorder, "requested", recorder.tool_calls)
        return {
            "text": text,
            "chart": chart,
            "tool_calls": recorder.tool_calls,
            "tool_names": [name for name, _ in recorder.tool_calls],
            # What each executed tool returned, so a case can tell "the tool
            # failed" apart from "the tool worked and the answer dropped it".
            "tool_results": list(recorder.tool_results),
            # Only differs on the Ollama path, which executes the first call
            # and drops the rest. Scored cases use tool_names (executed);
            # this is here so a failure detail can say what was asked for.
            "requested_names": [name for name, _ in requested],
            "engine": brain.active_engine,
            "error": getattr(recorder, "error", None),
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
    scorecard.render(terminalreporter.write_line, engine=ENGINE, aborted=ABORT["reason"])
