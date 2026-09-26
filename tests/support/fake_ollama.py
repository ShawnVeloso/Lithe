"""A scripted stand-in for a local Ollama server.

`_ollama_chat` talks to `/api/chat` with a bare `httpx.post`, so this patches
that rather than wrapping a client object. It records every request body, which
is what lets a test assert on the *messages* Lithe sent — the conversation
history the fallback used to omit entirely.

`/api/tags` is answered too, because the readiness check runs before any chat
request and would otherwise report the model as missing.
"""

import json


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"fake ollama returned {self.status_code}")


def text_message(content: str) -> dict:
    return {"message": {"role": "assistant", "content": content}}


def tool_call_message(calls) -> dict:
    """`calls` is a list of (name, args) the model wants to run."""
    return {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": name, "arguments": args}} for name, args in calls
            ],
        }
    }


class ScriptedOllama:
    """Serves queued /api/chat responses and records what it was sent.

    When the queue empties it falls back to `default`, so a loop that runs
    longer than a test expected fails on an assertion rather than surfacing as
    a connection error that the production code would then report as an outage.
    """

    def __init__(self, responses=None, default="Done.", model="llama3.2"):
        self._queue = list(responses or [])
        self._default = text_message(default)
        self._model = model
        self.requests = []  # one decoded request body per /api/chat call

    def install(self, monkeypatch):
        import httpx

        def fake_post(url, *args, **kwargs):
            assert "/api/chat" in str(url), url
            body = kwargs.get("json") or json.loads(kwargs.get("content", "{}"))
            self.requests.append(body)
            if self._queue:
                return FakeResponse(self._queue.pop(0))
            return FakeResponse(self._default)

        def fake_get(url, *args, **kwargs):
            assert "/api/tags" in str(url), url
            return FakeResponse({"models": [{"name": f"{self._model}:latest"}]})

        monkeypatch.setattr(httpx, "post", fake_post)
        monkeypatch.setattr(httpx, "get", fake_get)
        return self

    # -- helpers for assertions -------------------------------------------

    @property
    def call_count(self) -> int:
        return len(self.requests)

    def messages(self, index: int = 0) -> list:
        return self.requests[index]["messages"]

    def tools_offered(self, index: int = 0) -> list:
        return self.requests[index].get("tools") or []

    def roles(self, index: int = 0) -> list:
        return [m["role"] for m in self.messages(index)]

    def texts(self, index: int = 0) -> list:
        return [m.get("content", "") for m in self.messages(index)]


def force_gemini_outage(monkeypatch, brain):
    """Make brain.chat() take the fallback path the way a real outage does."""
    import httpx

    class Unreachable:
        @property
        def models(self):
            return self

        def generate_content(self, **kwargs):
            raise httpx.ConnectError("scripted outage")

        def generate_content_stream(self, **kwargs):
            raise httpx.ConnectError("scripted outage")

    monkeypatch.setattr(brain, "_client", Unreachable())


class _FakeStreamResponse:
    """The NDJSON body Ollama returns when `stream: true`.

    `iter_lines()` is what production reads, so the fake yields the same thing
    a real response does: one JSON object per line, decoded str, no trailing
    newline.
    """

    status_code = 200

    def __init__(self, lines):
        self._lines = lines

    def iter_lines(self):
        for line in self._lines:
            yield line

    def raise_for_status(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def stream_chunks(*contents, done=True):
    """One NDJSON line per text chunk, as `httpx.stream` would hand them over."""
    lines = [
        json.dumps({"message": {"role": "assistant", "content": c}, "done": False})
        for c in contents
    ]
    if done:
        lines.append(
            json.dumps({"message": {"role": "assistant", "content": ""}, "done": True})
        )
    return lines


def stream_tool_call(calls, *, trailing_text=""):
    """A streamed turn that opens with tool_calls, as Ollama actually sends it."""
    first = {
        "message": {
            "role": "assistant",
            "content": trailing_text,
            "tool_calls": [
                {"function": {"name": name, "arguments": args}} for name, args in calls
            ],
        },
        "done": False,
    }
    return [json.dumps(first), json.dumps({"message": {"content": ""}, "done": True})]


class StreamingOllama:
    """Serves queued NDJSON bodies to `httpx.stream`, and JSON to `httpx.post`.

    Both transports are installed because one turn can mix them: the streaming
    caller streams, while anything still on the blocking path must keep
    working unchanged.
    """

    def __init__(self, bodies=None, post_responses=None, model="llama3.2"):
        self._bodies = list(bodies or [])
        self._post_queue = list(post_responses or [])
        self._model = model
        self.requests = []       # decoded bodies sent to httpx.stream
        self.post_requests = []  # decoded bodies sent to httpx.post

    def install(self, monkeypatch):
        import httpx

        def fake_stream(method, url, *args, **kwargs):
            assert method == "POST", method
            assert "/api/chat" in str(url), url
            self.requests.append(kwargs.get("json") or {})
            if not self._bodies:
                raise AssertionError("StreamingOllama ran out of scripted bodies")
            return _FakeStreamResponse(self._bodies.pop(0))

        def fake_post(url, *args, **kwargs):
            assert "/api/chat" in str(url), url
            self.post_requests.append(kwargs.get("json") or {})
            if self._post_queue:
                return FakeResponse(self._post_queue.pop(0))
            return FakeResponse(text_message("Done."))

        def fake_get(url, *args, **kwargs):
            assert "/api/tags" in str(url), url
            return FakeResponse({"models": [{"name": f"{self._model}:latest"}]})

        monkeypatch.setattr(httpx, "stream", fake_stream)
        monkeypatch.setattr(httpx, "post", fake_post)
        monkeypatch.setattr(httpx, "get", fake_get)
        return self
