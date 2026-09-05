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

from tests.eval.cases import CASES
from tests.eval.conftest import ENGINE
from tests.eval.scorecard import RESULTS
from tests.eval.scoring import evaluate

REPEATS = int(os.getenv("LITHE_EVAL_REPEATS", "3"))


@pytest.mark.eval
@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_capability(case, harness):
    failures = []
    for repeat in range(REPEATS):
        try:
            outcome = harness.ask(case["prompt"], repeat=repeat)
        except Exception as exc:  # a crash is a failed run, not a failed suite
            failures.append(f"raised {type(exc).__name__}: {exc}")
            continue
        reason = evaluate(case, outcome, ENGINE)
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
