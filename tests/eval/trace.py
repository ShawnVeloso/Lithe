"""Opt-in diagnostic trace for the capability evaluation.

The harness assembles the whole picture of a turn -- every tool call, what each
call returned, whether a chart arrived, the final text -- and the scorecard then
keeps `failures[0]` and throws the rest away. That is the right amount of detail
for a score and far too little for a diagnosis: "still failing" tells you a
chain broke, not where.

So the outcome can be written out verbatim, as JSON lines, one record per
repeat. Off unless asked for, and it never touches a verdict -- this is a
diagnostic, not an assertion. A trace that could change a score would be one
more thing to distrust when the score moves.

    LITHE_EVAL_TRACE=1              write to ./eval-trace.jsonl
    LITHE_EVAL_TRACE=some/path.jsonl   write there instead

The file is truncated by the first write of a session and appended to
thereafter, so a run always stands alone rather than being read on top of
yesterday's. Each record is flushed as it is written, because the runs worth
tracing are the ones that abort.
"""

import json
import os
import time

DEFAULT_PATH = "eval-trace.jsonl"

# Long fields are cut so one read_file case cannot bury the rest of the run.
# Generous enough to hold a tool result's shape and its first real content.
MAX_FIELD_CHARS = 2000

_started = False


def path():
    """Where this run traces to, or None when tracing is off."""
    value = (os.getenv("LITHE_EVAL_TRACE") or "").strip()
    if value in ("", "0", "false", "no"):
        return None
    return DEFAULT_PATH if value in ("1", "true", "yes") else value


def _clip(text):
    text = "" if text is None else str(text)
    if len(text) <= MAX_FIELD_CHARS:
        return text
    return text[:MAX_FIELD_CHARS] + f"... [+{len(text) - MAX_FIELD_CHARS} chars]"


def record(case, outcome, repeat, reason=None, engine=None, model=None, seed=None):
    """Append one repeat's outcome. Returns the file written, or None.

    Never raises: a broken trace must not fail a case that the model actually
    passed, which would invert the meaning of the run it was added to explain.
    """
    target = path()
    if not target:
        return None

    chart = (outcome or {}).get("chart")
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "id": case.get("id"),
        "category": case.get("category"),
        "repeat": repeat,
        "engine": engine,
        "model": model,
        "seed": seed,
        # The verdict this repeat earned. None means it passed -- recording the
        # scorer's own reason keeps the trace and the scorecard from disagreeing.
        "reason": reason,
        "prompt": _clip(case.get("prompt")),
        "text": _clip((outcome or {}).get("text")),
        "tool_names": (outcome or {}).get("tool_names"),
        "requested_names": (outcome or {}).get("requested_names"),
        "proposed_names": (outcome or {}).get("proposed_names"),
        "tool_calls": [
            [name, args] for name, args in (outcome or {}).get("tool_calls") or []
        ],
        "tool_results": [
            [name, _clip(result)]
            for name, result in (outcome or {}).get("tool_results") or []
        ],
        # The image itself is a multi-megabyte data URI. Whether one arrived is
        # the diagnostic question; the pixels are not.
        "chart_present": bool(chart),
        "chart_chars": len(chart) if isinstance(chart, str) else 0,
        "engine_used": (outcome or {}).get("engine"),
        "error": _clip((outcome or {}).get("error")) or None,
    }

    global _started
    try:
        with open(target, "a" if _started else "w", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, default=str) + "\n")
            handle.flush()
        _started = True
        return target
    except OSError:
        return None
