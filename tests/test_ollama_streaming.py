"""Streaming the Ollama fallback, and the guard that keeps it out of `chat()`.

The fallback used to arrive as one dump: the user watched a spinner for the
whole generation and then the entire answer appeared at once. Streaming fixes
that, but the tool loop reads `resp.json()["message"]` and so does
`OllamaRecorder._harvest` in the evaluation harness -- hand either an NDJSON
body and both raise, which would silently zero every tool case in the suite.

So streaming is confined to `chat_stream`. The most important test in this file
is the one asserting `chat()` still posts `stream: False`; the rest describe
what the streaming path owes the user.
"""

import httpx
import pytest

from src.backend import brain
from tests.support.fake_ollama import (
    ScriptedOllama,
    StreamingOllama,
    force_gemini_outage,
    stream_chunks,
    stream_tool_call,
    text_message,
    tool_call_message,
)


@pytest.fixture
def fallback(isolated_db, monkeypatch):
    """Gemini unreachable, conversation state isolated -- a real outage's shape."""
    monkeypatch.setattr(brain, "OLLAMA_MODEL", "llama3.2")
    monkeypatch.setattr(brain, "_current_conversation_id", "stream-conv")
    monkeypatch.setattr(brain, "_context_blocks", [])
    monkeypatch.setattr(brain, "_chat_history", [])
    force_gemini_outage(monkeypatch, brain)
    return monkeypatch


def drain(events):
    """Split a chat_stream run into its token texts and every other event."""
    tokens, others = [], []
    for event in events:
        if event["type"] == "token":
            tokens.append(event["content"])
        else:
            others.append(event)
    return tokens, others


# ---------------------------------------------------------------------------
# The eval guard
# ---------------------------------------------------------------------------

def test_chat_still_posts_a_blocking_request(fallback, monkeypatch):
    """`chat()` is what the evaluation scores. It must not learn to stream."""
    def no_streaming(*args, **kwargs):
        raise AssertionError("chat() must never open a streaming request")

    monkeypatch.setattr(httpx, "stream", no_streaming)
    scripted = ScriptedOllama([text_message("plain answer")]).install(monkeypatch)

    assert brain.chat("hello") == "plain answer"
    assert scripted.requests[0]["stream"] is False


def test_the_blocking_transport_is_unchanged_by_the_callback_parameter(fallback, monkeypatch):
    """`_ollama_post` with no callback is the old code path, byte for byte."""
    scripted = ScriptedOllama([text_message("hi")]).install(monkeypatch)

    message = brain._ollama_post({"model": "llama3.2", "messages": [], "stream": False})

    assert message == {"role": "assistant", "content": "hi"}
    assert scripted.requests[0]["stream"] is False


# ---------------------------------------------------------------------------
# chat_stream
# ---------------------------------------------------------------------------

def test_the_fallback_arrives_progressively(fallback, monkeypatch):
    """Five chunks reach the user as more than one event, not one dump."""
    StreamingOllama([stream_chunks("The ", "answer ", "is ", "forty", "-two.")]).install(monkeypatch)

    tokens, others = drain(brain.chat_stream("what is it"))

    assert len(tokens) > 1, "the whole answer arrived as a single chunk"
    assert "".join(tokens) == "The answer is forty-two."
    assert others[-1]["type"] == "done"


def test_the_streaming_request_asks_for_a_stream(fallback, monkeypatch):
    server = StreamingOllama([stream_chunks("ok")]).install(monkeypatch)

    list(brain.chat_stream("hello"))

    assert server.requests[0]["stream"] is True
    assert server.requests[0]["model"] == "llama3.2"


def test_a_tool_call_emits_no_tokens_before_its_card(fallback, monkeypatch):
    """A turn that turns out to be a mutation must not type half a sentence first."""
    StreamingOllama([
        stream_tool_call(
            [("delete_file", {"path": "notes.txt"})],
            trailing_text="Sure, deleting that",
        ),
    ]).install(monkeypatch)

    tokens, others = drain(brain.chat_stream("delete notes.txt"))

    assert tokens == [], f"leaked text before the confirmation card: {tokens}"
    assert [e["type"] for e in others] == ["tool_proposal"]
    assert others[0]["proposal"]["name"] == "delete_file"


def test_a_truncated_final_line_keeps_what_arrived(fallback, monkeypatch):
    """A dropped connection truncates the answer; it must not crash the turn."""
    body = stream_chunks("Partial ", "ans", done=False)
    body.append('{"message": {"content": "wer"')  # the connection died here
    StreamingOllama([body]).install(monkeypatch)

    tokens, others = drain(brain.chat_stream("go"))

    assert "".join(tokens) == "Partial ans"
    assert others[-1]["type"] == "done"


def test_streamed_text_is_not_delivered_twice(fallback, monkeypatch):
    """The old code yielded the whole answer at the end. Both would double it."""
    StreamingOllama([stream_chunks("one ", "two ", "three")]).install(monkeypatch)

    tokens, _ = drain(brain.chat_stream("count"))

    assert "".join(tokens) == "one two three"


def test_a_streamed_turn_is_recorded_once_in_the_transcript(fallback, monkeypatch):
    """Streaming must leave the same history a blocking turn would."""
    StreamingOllama([stream_chunks("hello ", "there")]).install(monkeypatch)

    list(brain.chat_stream("hi"))

    model_turns = [c for c in brain._chat_history if c.role == "model"]
    assert len(model_turns) == 1
    assert model_turns[0].parts[0].text == "hello there"


def test_an_unreachable_ollama_still_reports_the_outage(fallback, monkeypatch):
    """With nothing streamed, the error string still has to reach the user."""
    monkeypatch.setattr(brain, "_ollama_models", lambda: None)

    tokens, others = drain(brain.chat_stream("hello"))

    assert "Ollama is not running" in "".join(tokens)
    assert others[-1]["type"] == "done"


def test_a_streamed_tool_result_still_drives_the_next_round(fallback, monkeypatch):
    """Chaining is the whole point of the loop; streaming must not break it."""
    def search_files(keyword: str) -> str:
        return f"found {keyword}.md"

    monkeypatch.setattr(brain, "_build_tool_functions", lambda *a, **k: [search_files])
    server = StreamingOllama([
        stream_tool_call([("search_files", {"keyword": "budget"})]),
        stream_chunks("I found ", "budget.md"),
    ]).install(monkeypatch)

    tokens, _ = drain(brain.chat_stream("find budget"))

    assert "".join(tokens) == "I found budget.md"
    assert len(server.requests) == 2
    assert server.requests[1]["messages"][-1]["content"] == "found budget.md"


# ---------------------------------------------------------------------------
# The live timeout
# ---------------------------------------------------------------------------

def test_a_new_timeout_reaches_the_next_request(fallback, monkeypatch, tmp_path):
    """The setting is worthless unless the *request* carries it, not just a global.

    `brain` imports OLLAMA_TIMEOUT by value, but every read of it is inside a
    function body -- so rebinding `brain.OLLAMA_TIMEOUT` is enough, and this is
    the test that says so. Asserting the global moved would pass even if the
    request kept using the stale one.
    """
    from fastapi.testclient import TestClient
    from src.backend import config
    from src.backend.server import app

    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(config, "_ACTIVE_ENV_PATH", env_file)
    monkeypatch.setattr(config, "OLLAMA_TIMEOUT", 60)
    monkeypatch.setattr(brain, "OLLAMA_TIMEOUT", 60)
    # The endpoint rebinds every Ollama global from config, so config's model
    # has to match the fixture's or the turn ends in "not pulled" before it
    # ever reaches a request.
    monkeypatch.setattr(config, "OLLAMA_MODEL", "llama3.2")

    seen = []

    def capture(url, *args, **kwargs):
        seen.append(kwargs.get("timeout"))
        return _ok_response()

    with TestClient(app) as client:
        res = client.post("/api/config/llm", json={"ollama_timeout": 150}).json()

    assert res["ollama_timeout"] == 150
    assert "OLLAMA_TIMEOUT" in env_file.read_text()   # survives a restart too

    monkeypatch.setattr(httpx, "post", capture)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _tags_response())
    answer = brain.chat("hello")

    assert seen == [150], f"the request still used the old timeout: {answer}"


def test_the_timeout_is_clamped_rather_than_rejected(monkeypatch, tmp_path):
    """The setting exists to rescue a slow machine; a typo must leave it working."""
    from src.backend import config

    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(config, "_ACTIVE_ENV_PATH", env_file)

    monkeypatch.setattr(config, "OLLAMA_TIMEOUT", 60)
    config.update_llm_config(ollama_timeout=1)
    assert config.OLLAMA_TIMEOUT == config.OLLAMA_TIMEOUT_MIN

    config.update_llm_config(ollama_timeout=99999)
    assert config.OLLAMA_TIMEOUT == config.OLLAMA_TIMEOUT_MAX

    config.update_llm_config(ollama_timeout=0)   # blank means leave unchanged
    assert config.OLLAMA_TIMEOUT == config.OLLAMA_TIMEOUT_MAX


class _ok_response:
    status_code = 200

    def json(self):
        return {"message": {"role": "assistant", "content": "ok"}}

    def raise_for_status(self):
        pass


class _tags_response(_ok_response):
    def json(self):
        return {"models": [{"name": "llama3.2:latest"}]}
