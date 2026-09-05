"""Translation between Lithe's transcript and Ollama's chat format.

Lithe stores the conversation as `google.genai.types.Content` because Gemini is
the primary engine. The Ollama fallback speaks `/api/chat`, whose messages are
plain dicts with a different shape for tool traffic:

    Gemini                                    Ollama
    ------                                    ------
    role="user",  Part.text                   {"role": "user",      "content": ...}
    role="model", Part.text                   {"role": "assistant", "content": ...}
    role="model", Part.function_call          {"role": "assistant", "tool_calls": [...]}
    role="user",  Part.function_response      {"role": "tool",      "content": ...}

Note the last row: a tool *result* is a `user` turn to Gemini and a `tool` turn
to Ollama, so the roles cannot simply be renamed.

This exists because `_ollama_chat` used to send `[system, user]` and nothing
else — the fallback engine had no memory of the conversation whatsoever. Every
turn started from scratch, so "summarize budget.csv" followed by "now list its
columns" left the second turn with no idea what "its" referred to. That was
invisible for as long as the fallback was broken; it is not any more.
"""


def _result_text(response) -> str:
    """Flatten a function_response payload into the string Ollama expects.

    Lithe wraps every tool result as {"result": ...}, so unwrap that when it is
    present rather than sending the model a stringified dict to read through.
    """
    if isinstance(response, dict) and set(response) == {"result"}:
        return str(response["result"])
    return str(response)


def to_ollama_messages(history) -> list[dict]:
    """Convert a slice of Lithe's transcript into Ollama chat messages.

    `history` is expected to be budget-trimmed already: this only reshapes, it
    does not decide how much to send.
    """
    messages: list[dict] = []

    for content in history or []:
        texts = []
        tool_calls = []
        tool_results = []

        for part in (content.parts or []):
            if getattr(part, "text", None):
                texts.append(part.text)
            call = getattr(part, "function_call", None)
            if call is not None:
                tool_calls.append({
                    "function": {
                        "name": call.name,
                        "arguments": dict(call.args or {}),
                    }
                })
            result = getattr(part, "function_response", None)
            if result is not None:
                tool_results.append((result.name, _result_text(result.response)))

        # A tool turn carries results and nothing else, and each result is its
        # own message to Ollama rather than one turn with several parts.
        if tool_results:
            for name, text in tool_results:
                messages.append({"role": "tool", "name": name, "content": text})
            continue

        if getattr(content, "role", None) == "model":
            message = {"role": "assistant", "content": "\n".join(texts)}
            if tool_calls:
                message["tool_calls"] = tool_calls
            messages.append(message)
        elif texts:
            messages.append({"role": "user", "content": "\n".join(texts)})

    return messages


def call_name_and_args(call):
    """Name and arguments of a tool call from either engine.

    Gemini hands back objects with `.name` / `.args`; Ollama nests them under
    `{"function": {"name": ..., "arguments": ...}}`. Normalising here is what
    lets the confirmation gate and the diff builder be written once.
    """
    if isinstance(call, dict):
        function = call.get("function", {})
        return function.get("name", ""), dict(function.get("arguments") or {})
    return call.name, dict(call.args or {})
