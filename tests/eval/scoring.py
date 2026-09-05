"""How a single evaluation run is judged.

Kept out of `test_capability.py` so these rules can be exercised by the normal
suite (`tests/test_eval_scoring.py`) rather than only by a live model run. They
needed to be: the scorecard has twice reported a **pass** over a real defect,
and both times the fault was here rather than in Lithe.

The two misses share a shape. A case asserted that a tool was *called* and
stopped there, so everything that happens after the tool returns — the guard
that replaced a correct answer with an ERROR, the chart that was generated and
then dropped on the floor — was invisible to the instrument. Calling a tool is
not the capability; the user receiving its result is. So the checks below come
in three layers:

1. **Invariants**, applied to every case whether it asks for them or not. A
   failure Lithe itself produced is never a passing run, and nobody should have
   to remember to annotate each new case with that.
2. **Call-level** assertions — which tool, with which arguments.
3. **Result-level** assertions — what the tool returned, and whether it
   survived into what the user was handed.
"""

# Text Lithe emits when a turn fails. Reaching the user, this *is* the answer,
# so a run ending in one has failed regardless of what the case asked for.
#
#   "the llm generated a narrative"  brain._check_hallucination(). Ran
#       unconditionally on the Ollama path, where it keys on words like "found"
#       and "successfully" -- exactly how a model reports a search that really
#       happened. Correct answers were replaced by this ERROR for as long as
#       the fallback worked, and every eval case scored it as a pass.
#   "internal error in lithe"        brain.chat()'s defect branch.
#   "ollama returned an empty response"  the fallback's own empty-reply guard.
#
# Compared case-insensitively against the final answer.
LITHE_FAILURE_TEXT = (
    "the llm generated a narrative",
    "internal error in lithe",
    "ollama returned an empty response",
)


def _dispatch_miss(result: str) -> bool:
    """True if this tool result is Lithe failing to dispatch a call it declared.

    `Error: Tool {name} not recognized.` is what the model gets back when the
    name it was handed in the schema is not a key in `tool_map`. That is the
    exact shape of the September defect in which 5 of 9 tools were declared as
    `profile_data_wrapper` and dispatched as `profile_data` -- and because the
    evaluation could not see tool results, every affected case was scored as
    the model choosing badly.
    """
    lowered = result.lower()
    return lowered.startswith("error: tool ") and "not recognized" in lowered


def evaluate(case, outcome, expected_engine):
    """Return None if this run satisfied the case, else a reason string.

    `outcome` is what EvalHarness.ask() reports: the final text, the tool calls
    Lithe executed, what those calls returned, and any chart handed back.
    """
    text = (outcome.get("text") or "").lower()
    tool_names = outcome.get("tool_names") or []
    tool_results = outcome.get("tool_results") or []

    # -- Invariants ------------------------------------------------------
    # An unintended engine switch would score a harness problem as a model
    # failure. Which engine counts as correct depends on what is being scored.
    if outcome.get("engine") != expected_engine:
        return f"ran on {outcome.get('engine')}, not {expected_engine} (check the logs)"

    for name, result in tool_results:
        if _dispatch_miss(result):
            return (
                f"Lithe could not dispatch {name or 'a tool'} it had declared: "
                f"{result.strip()!r}"
            )

    for marker in LITHE_FAILURE_TEXT:
        if marker in text:
            # Says what happened without guessing why: the guard also fires
            # legitimately when a model claims a search it never made. Either
            # way this run failed, and naming the guard lets a reader tell the
            # two apart from the transcript.
            return f"answer was replaced by Lithe's own failure text ({marker!r})"

    # -- Call-level ------------------------------------------------------
    expected_tool = case.get("expect_tool")
    if expected_tool:
        if expected_tool not in tool_names:
            return f"expected tool {expected_tool}, got {tool_names or 'none'}"
        predicate = case.get("args_predicate")
        if predicate:
            args = next(a for n, a in outcome["tool_calls"] if n == expected_tool)
            if not predicate(args):
                return f"{expected_tool} called with unusable args: {args}"

    missing = [t for t in case.get("expect_all_tools", []) if t not in tool_names]
    if missing:
        detail = f"executed {tool_names or 'nothing'}"
        requested = outcome.get("requested_names") or []
        if requested != tool_names:
            detail += f" (model asked for {requested})"
        return f"never ran {', '.join(missing)}; {detail}"

    if case.get("expect_no_tool") and tool_names:
        return f"expected no tool call, got {tool_names}"

    # -- Result-level ----------------------------------------------------
    # A chart is not text, so no substring assertion can see it. inline_chart
    # was called, returned a real data URI, and had it thrown away on the
    # Ollama path -- while the model truthfully relayed a delivery that never
    # happened. `expect_tool` passed throughout.
    if case.get("expect_chart"):
        chart = outcome.get("chart")
        if not (isinstance(chart, str) and chart.startswith("data:image")):
            called = "inline_chart was called" if "inline_chart" in tool_names \
                else "inline_chart was never called"
            return f"no chart reached the caller ({called})"

    required = case.get("result_must_contain")
    if required:
        joined = "\n".join(r for _, r in tool_results).lower()
        for needle in required:
            if needle.lower() not in joined:
                # Separating this from must_contain is the point: it says the
                # *tool* failed, rather than the answer having dropped a result
                # that was fine.
                return f"no tool returned {needle!r} (results: {_summarise(tool_results)})"

    for needle in case.get("must_contain", []):
        if needle.lower() not in text:
            return f"answer missing {needle!r}"

    for needle in case.get("must_not_contain", []):
        if needle.lower() in text:
            return f"answer contained forbidden {needle!r}"

    return None


def _summarise(tool_results, width=60):
    """One short line per tool result, for a failure detail that fits a table."""
    if not tool_results:
        return "none"
    parts = []
    for name, result in tool_results:
        flat = " ".join(result.split())
        if len(flat) > width:
            flat = flat[:width] + "..."
        parts.append(f"{name}={flat!r}")
    return "; ".join(parts)
