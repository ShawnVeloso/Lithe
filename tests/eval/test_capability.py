"""Live capability evaluation — opt-in, hits the real Gemini API.

    LITHE_EVAL=1 python -m pytest -m eval

Each case runs several times because model output is not deterministic. A case
passes on a majority of repeats, is reported flaky on a minority, and fails on
none. Per-case verdicts feed the scorecard printed at the end of the run (see
conftest.pytest_terminal_summary).
"""

import os

import pytest

from tests.eval.cases import CASES
from tests.eval.conftest import ENGINE
from tests.eval.scorecard import RESULTS

REPEATS = int(os.getenv("LITHE_EVAL_REPEATS", "3"))


def _evaluate(case, outcome):
    """Return None if this run satisfied the case, else a reason string."""
    text = (outcome["text"] or "").lower()
    tool_names = outcome["tool_names"]

    # An unintended engine switch would score a harness problem as a model
    # failure. Which engine counts as correct depends on what is being scored.
    if outcome["engine"] != ENGINE:
        return f"ran on {outcome['engine']}, not {ENGINE} (check the logs)"

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

    for needle in case.get("must_contain", []):
        if needle.lower() not in text:
            return f"answer missing {needle!r}"

    for needle in case.get("must_not_contain", []):
        if needle.lower() in text:
            return f"answer contained forbidden {needle!r}"

    return None


@pytest.mark.eval
@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_capability(case, harness):
    failures = []
    for _ in range(REPEATS):
        try:
            outcome = harness.ask(case["prompt"])
        except Exception as exc:  # a crash is a failed run, not a failed suite
            failures.append(f"raised {type(exc).__name__}: {exc}")
            continue
        reason = _evaluate(case, outcome)
        if reason:
            failures.append(reason)

    passed = REPEATS - len(failures)
    if passed == REPEATS:
        verdict = "pass"
    elif passed > REPEATS / 2:
        verdict = "pass"
    elif passed > 0:
        verdict = "flaky"
    else:
        verdict = "fail"

    RESULTS.append({
        "id": case["id"],
        "category": case["category"],
        "known_gap": bool(case.get("known_gap")),
        "verdict": verdict,
        "detail": failures[0] if failures else "",
        "passed": passed,
        "repeats": REPEATS,
    })

    if case.get("known_gap"):
        # Reported in the scorecard's "known gaps" section rather than failing
        # the run: these are documented limitations, not regressions.
        return

    assert verdict == "pass", (
        f"{case['id']} scored {passed}/{REPEATS}: " + "; ".join(failures[:2])
    )
