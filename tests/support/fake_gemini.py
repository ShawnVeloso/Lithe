"""A scripted stand-in for `google.genai.Client`, for driving brain.chat().

Why this exists rather than a MagicMock:

`response.function_calls` and `response.text` are *computed properties* over
`candidates[0].content.parts`. A MagicMock would happily return whatever the
test told it to, which means a test could pass while the real SDK plumbing was
broken. Building genuine `types.*` objects makes the fake exercise the same
accessors production does.

The client also records the `config` it was handed on every call. That is what
lets a test compare the tool names Lithe *declares* to the model against the
names it can actually *dispatch*, with no network involved.
"""

from google.genai import types


def text_response(text: str) -> types.GenerateContentResponse:
    """A plain model turn with no tool calls."""
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=[types.Part.from_text(text=text)])
            )
        ]
    )


def function_call_response(name: str, args: dict) -> types.GenerateContentResponse:
    """A model turn requesting a single tool call."""
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(
                    role="model",
                    parts=[types.Part.from_function_call(name=name, args=args)],
                )
            )
        ]
    )


class _Models:
    def __init__(self, owner: "ScriptedGeminiClient"):
        self._owner = owner

    def generate_content(self, *, model, contents, config):
        return self._owner._next(model, contents, config)

    def generate_content_stream(self, *, model, contents, config):
        # brain.chat_stream() iterates the return value; each chunk is shaped
        # like a full response, which matches how the real SDK streams.
        response = self._owner._next(model, contents, config)
        return iter([response])


class ScriptedGeminiClient:
    """Returns queued responses in order and records every call it received.

    Args:
        responses: queued `GenerateContentResponse` objects, consumed in order.
            When exhausted, `default` is returned instead of raising, so a loop
            that runs longer than expected fails on an assertion rather than a
            StopIteration surfacing as "Gemini connection failed".
        default: response handed back once the queue empties.
    """

    def __init__(self, responses=None, default: str = "Done."):
        self._queue = list(responses or [])
        self._default = text_response(default)
        self.calls = []  # one entry per model call: {"model", "contents", "config"}

    @property
    def models(self):
        return _Models(self)

    def _next(self, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self._queue:
            return self._queue.pop(0)
        return self._default

    # -- helpers for assertions -------------------------------------------

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def declared_tool_names(self, call_index: int = 0) -> set:
        """Tool names as the Gemini SDK would send them.

        The SDK derives a FunctionDeclaration's name from `callable.__name__`,
        so this mirrors exactly what the model is told the tools are called.
        """
        config = self.calls[call_index]["config"]
        return {fn.__name__ for fn in (config.tools or [])}

    def system_instruction(self, call_index: int = 0) -> str:
        return self.calls[call_index]["config"].system_instruction

    def function_response_texts(self, call_index: int) -> list:
        """The tool results Lithe fed back to the model on a given call."""
        out = []
        for content in self.calls[call_index]["contents"]:
            for part in (content.parts or []):
                if part.function_response is not None:
                    out.append(str(part.function_response.response))
        return out
