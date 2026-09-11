"""Live capability evaluation — opt-in, runs a real model.

    LITHE_EVAL=1 python -m pytest -m eval

The engine is Ollama unless LITHE_EVAL_ENGINE says otherwise; see
tests/eval/conftest.py for why. How a run is judged lives in scoring.py.

Each case runs several times because model output is not deterministic. A case
passes on a majority of repeats, is reported flaky on a minority, and fails on
none. Per-case verdicts feed the scorecard printed at the end of the run (see
conftest.pytest_terminal_summary).
"""

import os

import pytest

from tests.eval import trace
from tests.eval.cases import CASES
from tests.eval.conftest import ENGINE, EVAL_SEED, _configured_model
from tests.eval.scorecard import RESULTS
from tests.eval.scoring import evaluate

REPEATS = int(os.getenv("LITHE_EVAL_REPEATS", "3"))


@pytest.mark.eval
@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_capability(case, harness):
    failures = []
    # cases.py has documented a {corpus} placeholder since it was written and
    # nothing ever substituted it, so a case that used one would have sent the
    # literal braces to the model. Replaced rather than str.format()'d: a
    # prompt containing an ordinary brace must not raise.
    prompt = case["prompt"].replace("{corpus}", str(harness.corpus))
    # The trace records the prompt that was *sent*, not the template. The
    # first run with a {corpus} case logged the literal placeholder, so the
    # one record meant to explain a verdict could not say what the model saw.
    sent = {**case, "prompt": prompt}
    for repeat in range(REPEATS):
        try:
            outcome = harness.ask(prompt, repeat=repeat)
        except Exception as exc:  # a crash is a failed run, not a failed suite
            reason = f"raised {type(exc).__name__}: {exc}"
            failures.append(reason)
            _trace(sent, None, repeat, reason)
            continue
        reason = evaluate(case, outcome, ENGINE)
        if reason:
            failures.append(reason)
        # After scoring, and given the same reason the scorecard will show, so
        # the trace can never disagree with the verdict it explains.
        _trace(sent, outcome, repeat, reason)

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


def _trace(case, outcome, repeat, reason):
    """Write this repeat to the diagnostic trace, when one was asked for."""
    trace.record(
        case,
        outcome,
        repeat,
        reason=reason,
        engine=ENGINE,
        model=_configured_model(),
        # The seed the harness actually pinned for this repeat; Ollama only,
        # since the Gemini path sets no options.
        seed=EVAL_SEED + repeat if ENGINE == "ollama" else None,
    )
