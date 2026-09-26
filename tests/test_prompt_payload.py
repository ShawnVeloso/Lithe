"""The exact payload Lithe sends to Ollama, pinned against a golden file.

This is a measurement guard, not a correctness test. The capability evaluation
scores a model on one specific input: the system prompt plus the tool schema.
Change either and the score before the change stops being comparable to the
score after it -- which was learned expensively. Lengthening one tool
description moved the score 80% -> 69% and tool selection 4/6 -> 2/6, because
llama3.2 began emitting tool calls as plain text instead of native calls.

Two failures had already slipped through by being invisible:

  * `search_files` gained content search, and the system prompt kept telling the
    model it "matches FILENAMES only -- it cannot see inside files". The tool
    and the instructions contradicted each other, and nothing failed.
  * The tool descriptions were rewritten mid-session with no record of what the
    previous text had been, so the regression could only be found by re-running
    an eleven-minute evaluation and guessing.

So the payload is checked in. A diff of `tests/support/golden_ollama_payload.json`
is the review signal that a change is eval-affecting, and updating it requires a
fresh evaluation run and a recorded score. See docs/TESTING.md.
"""

import json
from pathlib import Path

import httpx
import pytest

from src.backend import brain

GOLDEN_PATH = Path(__file__).parent / "support" / "golden_ollama_payload.json"


class _FakeOllamaResponse:
    status_code = 200

    def json(self):
        return {"message": {"role": "assistant", "content": "ok"}}

    def raise_for_status(self):
        pass


class _UnavailableGemini:
    """Forces brain.chat() down the real outage path, as the eval harness does."""

    @property
    def models(self):
        return self

    def generate_content(self, **kwargs):
        raise httpx.ConnectError("pinned to ollama")

    def generate_content_stream(self, **kwargs):
        raise httpx.ConnectError("pinned to ollama")


@pytest.fixture
def sent_payload(isolated_db, monkeypatch):
    """The /api/chat body produced by one ordinary turn."""
    captured = {}

    def capture(url, *args, **kwargs):
        assert "/api/chat" in str(url), f"unexpected POST to {url}"
        captured.update(kwargs.get("json") or {})
        return _FakeOllamaResponse()

    monkeypatch.setattr(httpx, "post", capture)
    monkeypatch.setattr(brain, "_client", _UnavailableGemini())
    # Pre-flight only has to believe the configured model is present. Both
    # spellings, because OLLAMA_MODEL may already carry a tag -- an .env naming
    # `qwen2.5:latest` produced `qwen2.5:latest:latest` here, and the guard on
    # the eval payload silently errored out on that machine instead of running.
    monkeypatch.setattr(
        brain, "_ollama_models",
        lambda: [brain.OLLAMA_MODEL, f"{brain.OLLAMA_MODEL}:latest"],
    )

    brain.chat("hello")
    assert captured, "no /api/chat request was made"
    return captured


def load_golden():
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def test_the_system_prompt_matches_the_golden(sent_payload):
    """A prompt edit must show up as a reviewable diff, not as a score change."""
    expected = load_golden()["system"]
    actual = sent_payload["messages"][0]["content"]
    assert sent_payload["messages"][0]["role"] == "system"
    assert actual == expected, (
        "The system prompt changed. This resamples the capability evaluation: "
        "the current score is no longer comparable to the recorded one. Re-run "
        "`LITHE_EVAL=1 python -m pytest -m eval`, record the new number, and "
        "update tests/support/golden_ollama_payload.json in the same commit."
    )


def test_the_tool_schema_matches_the_golden(sent_payload):
    """Names, descriptions and parameters are all model input."""
    expected = load_golden()["tools"]
    assert sent_payload["tools"] == expected, (
        "The Ollama tool schema changed. A tool description is part of the "
        "payload the evaluation measures -- lengthening one cost 11 points "
        "once. Re-run the evaluation, record the number, and update the golden."
    )


def test_the_transport_shape_is_unchanged(sent_payload):
    """Streaming or sampling options would change what the model produces.

    `stream: False` is load-bearing beyond the payload: the tool loop reads
    `resp.json()["message"]`, and so does OllamaRecorder in the eval harness.
    NDJSON would make both raise, silently zeroing every tool case.
    """
    assert sent_payload["stream"] is False
    # brain.OLLAMA_OPTIONS is empty in production; the evaluation sets a seed.
    # A shipped default here would change every answer.
    assert "options" not in sent_payload


def test_the_golden_actually_fails_when_the_prompt_changes(sent_payload, monkeypatch):
    """Without this the comparison above could be vacuous.

    A golden test that passes no matter what is worse than none, because it
    reads as protection. This proves the assertion has teeth.
    """
    tampered = dict(sent_payload)
    tampered["messages"] = [
        {"role": "system", "content": "you are a helpful assistant"},
        *sent_payload["messages"][1:],
    ]
    with pytest.raises(AssertionError):
        assert tampered["messages"][0]["content"] == load_golden()["system"]


def test_the_golden_fails_when_a_tool_is_added(sent_payload):
    """The same teeth, for the half of the payload that is the tool schema."""
    tampered = list(sent_payload["tools"]) + [
        {"type": "function", "function": {"name": "rm_rf", "description": "no"}}
    ]
    assert tampered != load_golden()["tools"]


def test_every_declared_tool_is_dispatchable(sent_payload):
    """The golden pins the text; this pins that the text describes real tools.

    A schema entry naming a tool that cannot be dispatched is the exact defect
    that left 5 of 9 tools unreachable on Gemini, and every affected eval case
    scored it as the model choosing badly.
    """
    declared = {t["function"]["name"] for t in sent_payload["tools"]}
    dispatchable = {fn.__name__ for fn in brain._build_tool_functions()}
    assert declared == dispatchable
