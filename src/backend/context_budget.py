"""Bounds on how much text Lithe sends the model on any one request.

Two things used to grow without any limit at all:

  * **The transcript.** ``brain._chat_history`` was appended to forever and
    reloaded in full at startup, so every request carried the entire
    conversation back to the first message.
  * **Injected file content.** F-04 appends up to ``MAX_FILE_SIZE_BYTES``
    (100KB) of a named file onto the user's message, and that enlarged message
    was persisted as the user turn -- so naming three files welded ~300KB onto
    every later request permanently, surviving restarts.

Sizes here are counted in characters rather than tokens on purpose: a real
tokenizer would mean shipping one per provider (Gemini's differs from
llama3.1's) to enforce a limit that only needs to be roughly right. Four
characters per token is the usual rule of thumb, so the defaults below are
about 12k tokens of transcript and 15k of file context.
"""

import os


def _env_chars(name: str, default: int) -> int:
    """Read a character budget from the environment, ignoring junk values."""
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    # A budget below one turn would trim to nothing on every request.
    return max(2_000, value)


MAX_HISTORY_CHARS = _env_chars("LITHE_MAX_HISTORY_CHARS", 48_000)
MAX_CONTEXT_CHARS = _env_chars("LITHE_MAX_CONTEXT_CHARS", 60_000)

# How many messages to reload from SQLite when a conversation is opened. The
# per-request budget would trim most of a long transcript away anyway, so
# reading thousands of rows and rebuilding Content objects for them is wasted
# work at startup.
MAX_HISTORY_MESSAGES = 200


def content_size(content) -> int:
    """Approximate the character cost of one ``types.Content``.

    Function calls and responses are counted via ``str()`` of their payload,
    which is close enough: the point is to stop a 100KB tool result from being
    treated as free, not to predict a bill to the character.
    """
    total = 0
    for part in (content.parts or []):
        if getattr(part, "text", None):
            total += len(part.text)
        call = getattr(part, "function_call", None)
        if call is not None:
            total += len(str(call.name or "")) + len(str(call.args or ""))
        result = getattr(part, "function_response", None)
        if result is not None:
            total += len(str(result.response or ""))
    return total


def is_turn_start(content) -> bool:
    """True if a request payload may legally begin at this ``Content``.

    Gemini rejects a ``function_response`` that has no matching
    ``function_call`` earlier in the payload, so a window cut in the middle of
    a tool exchange produces a 400 rather than a shorter conversation. Only a
    plain user turn is a safe place to cut.
    """
    if getattr(content, "role", None) != "user":
        return False
    return not any(
        getattr(part, "function_response", None) is not None
        for part in (content.parts or [])
    )


def drop_orphan_prefix(history) -> list:
    """Discard leading turns until the list begins where a request may begin.

    Needed after a bounded reload from SQLite: slicing the newest N messages
    can cut into the middle of a tool exchange, leaving a ``function_response``
    whose ``function_call`` was left behind. ``trim_history`` will not fix that
    on its own, because a history that already fits the budget is returned
    untouched.
    """
    for i, content in enumerate(history):
        if is_turn_start(content):
            return list(history[i:])
    # Everything left is orphaned tool traffic; none of it can legally be sent.
    return []


def trim_history(history, max_chars: int | None = None) -> list:
    """Return the newest slice of ``history`` that fits the budget.

    Returns the list unchanged when it already fits. When nothing can be cut
    without orphaning a tool response, the history is returned whole: being
    over budget costs tokens, whereas an invalid payload costs the whole turn.
    """
    budget = MAX_HISTORY_CHARS if max_chars is None else max_chars
    if not history:
        return []

    sizes = [content_size(c) for c in history]
    if sum(sizes) <= budget:
        return list(history)

    # Suffix sums, so each candidate window is measured in constant time.
    suffix = [0] * (len(history) + 1)
    for i in range(len(history) - 1, -1, -1):
        suffix[i] = suffix[i + 1] + sizes[i]

    starts = [i for i, c in enumerate(history) if is_turn_start(c)]
    if not starts:
        return list(history)

    # starts is ascending and suffix[] decreasing, so the first legal start
    # that fits is also the largest window that fits.
    for start in starts:
        if suffix[start] <= budget:
            return history[start:]

    # Even the final turn is over budget on its own -- keep it regardless,
    # since dropping the message being answered would be worse.
    return history[starts[-1]:]


def trim_blocks(blocks, max_chars: int | None = None) -> list:
    """Keep the most recent ``(key, text)`` blocks that fit the budget.

    ``blocks`` is ordered oldest-first; eviction is from the front, so the file
    a user just named survives and one mentioned twenty turns ago does not.
    """
    budget = MAX_CONTEXT_CHARS if max_chars is None else max_chars
    kept: list = []
    used = 0
    for key, text in reversed(blocks):
        cost = len(text)
        if kept and used + cost > budget:
            break
        kept.append((key, text))
        used += cost
    kept.reverse()
    return kept
