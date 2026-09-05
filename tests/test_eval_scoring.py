"""Unit tests for how the capability evaluation judges a run.

The scorecard has twice called a real defect a pass, and both times the fault
was in the scoring rules rather than in Lithe. So the rules get tested like any
other code — in the normal suite, with no model involved, where a mistake in
the instrument shows up on every run instead of only when someone opts into a
live evaluation.

Each test below pins one of the misses, or the invariant added to stop the next
one of its kind.
"""

import pytest

from tests.eval.scoring import evaluate


ENGINE = "ollama"


def outcome(**overrides):
    """A run that satisfies every check, so a test can break exactly one."""
    base = {
        "text": "Found 1 file: sales_q3.csv",
        "chart": None,
        "tool_calls": [("search_files", {"keyword": "sales"})],
        "tool_names": ["search_files"],
        "tool_results": [("search_files", "Found 1 file(s): sales_q3.csv")],
        "requested_names": ["search_files"],
        "engine": ENGINE,
        "error": None,
    }
    base.update(overrides)
    return base


def test_clean_run_passes():
    assert evaluate({"id": "x"}, outcome(), ENGINE) is None


def test_engine_switch_is_not_scored_as_a_model_failure():
    reason = evaluate({"id": "x"}, outcome(engine="gemini"), ENGINE)
    assert "ran on gemini" in reason


# -- The two defects that scored as passes --------------------------------

def test_guard_error_fails_the_run_even_when_the_tool_was_called():
    """The hallucination guard replaced correct answers with an ERROR.

    _check_hallucination keys on words like "found" and "successfully", which
    is how a model reports a search that really happened. On the Ollama path it
    ran unconditionally, so a genuine search_files result reached the user as
    an ERROR telling them to rephrase. `select-search` asserted only that the
    tool was called, so this scored as a pass for as long as the fallback
    worked.
    """
    case = {"id": "select-search", "expect_tool": "search_files"}
    destroyed = (
        "ERROR: The LLM generated a narrative claiming to have searched for "
        "files, but failed to actually invoke the system search tool."
    )
    assert evaluate(case, outcome(), ENGINE) is None
    reason = evaluate(case, outcome(text=destroyed), ENGINE)
    assert reason is not None
    assert "failure text" in reason


def test_guard_error_fails_even_a_case_that_asserts_nothing():
    """The invariant does not depend on the case remembering to ask for it.

    This is the point of putting it in the invariant layer: the guard could
    fire on any case, and requiring each one to carry a `must_not_contain` for
    it means the next case someone adds is unprotected.
    """
    reason = evaluate({"id": "bare"}, outcome(text="Internal error in Lithe (KeyError: 'x')."), ENGINE)
    assert reason is not None
    assert "failure text" in reason


def test_chart_case_fails_when_the_image_never_reaches_the_caller():
    """inline_chart ran, returned a data URI, and had it thrown away.

    The result was swapped for "Chart generated and sent to user successfully"
    so a base64 blob would not sit in the transcript, but only that text was
    returned — so the model truthfully relayed a delivery that never happened.
    A text assertion cannot see this; the chart is not text.
    """
    case = {"id": "select-chart", "expect_tool": "inline_chart", "expect_chart": True}
    called = outcome(
        text="Chart generated and sent to user successfully.",
        tool_calls=[("inline_chart", {"chart_type": "bar"})],
        tool_names=["inline_chart"],
        tool_results=[("inline_chart", "Chart generated and sent to user successfully.")],
        requested_names=["inline_chart"],
    )
    reason = evaluate(case, called, ENGINE)
    assert reason is not None
    assert "no chart reached the caller" in reason
    assert "inline_chart was called" in reason  # so the reader knows which half broke

    delivered = dict(called, chart="data:image/png;base64,iVBORw0KGgo=")
    assert evaluate(case, delivered, ENGINE) is None


def test_chart_case_says_so_when_the_tool_was_never_called():
    case = {"id": "select-chart", "expect_chart": True}
    reason = evaluate(case, outcome(), ENGINE)
    assert "inline_chart was never called" in reason


def test_a_non_image_chart_value_does_not_count():
    case = {"id": "select-chart", "expect_chart": True}
    reason = evaluate(case, outcome(chart="Chart generated and sent to user successfully."), ENGINE)
    assert reason is not None


# -- Invariant: a tool Lithe declared but could not dispatch ---------------

def test_dispatch_miss_is_reported_as_lithes_fault():
    """`Error: Tool X not recognized.` is never the model's mistake.

    This is the shape of the defect in which 5 of 9 tools were declared to the
    model as `profile_data_wrapper` and dispatched as `profile_data`. Because
    the evaluation could not see tool results, every affected case looked like
    the model answering badly.
    """
    broken = outcome(
        tool_calls=[("profile_data", {})],
        tool_names=["profile_data"],
        tool_results=[("profile_data", "Error: Tool profile_data_wrapper not recognized.")],
        requested_names=["profile_data"],
    )
    reason = evaluate({"id": "select-profile", "expect_tool": "profile_data"}, broken, ENGINE)
    assert reason is not None
    assert "could not dispatch" in reason


def test_an_ordinary_tool_error_is_not_a_dispatch_miss():
    """A tool that ran and failed is a different finding from one never reached."""
    failed = outcome(
        tool_results=[("profile_data", "ERROR: File 'q4.xlsx' not found in indexed directories.")],
    )
    assert evaluate({"id": "x"}, failed, ENGINE) is None


# -- Result-level assertions ----------------------------------------------

def test_result_must_contain_separates_a_broken_tool_from_a_dropped_result():
    case = {"id": "select-search", "result_must_contain": ["sales_q3.csv"], "must_contain": ["sales_q3"]}

    assert evaluate(case, outcome(), ENGINE) is None

    tool_failed = outcome(
        text="I could not find anything.",
        tool_results=[("search_files", "No files found matching 'sales'.")],
    )
    assert "no tool returned" in evaluate(case, tool_failed, ENGINE)

    answer_dropped_it = outcome(text="I could not find anything.")
    assert "answer missing" in evaluate(case, answer_dropped_it, ENGINE)


def test_result_detail_quotes_what_the_tools_actually_returned():
    """A failure the reader can act on without re-running the suite."""
    case = {"id": "x", "result_must_contain": ["DATA PROFILE"]}
    reason = evaluate(case, outcome(tool_results=[("profile_data", "ERROR: Unsupported file type '.png'.")]), ENGINE)
    assert "profile_data=" in reason
    assert "Unsupported file type" in reason


def test_long_results_are_truncated_in_the_detail():
    case = {"id": "x", "result_must_contain": ["nope"]}
    reason = evaluate(case, outcome(tool_results=[("read_file", "x" * 500)]), ENGINE)
    assert "..." in reason
    assert len(reason) < 300


# -- Behaviour carried over, still pinned ---------------------------------

def test_expect_no_tool_and_substring_checks_still_apply():
    case = {"id": "no-tool-arithmetic", "expect_no_tool": True, "must_contain": ["4"]}
    quiet = outcome(text="4", tool_calls=[], tool_names=[], tool_results=[], requested_names=[])
    assert evaluate(case, quiet, ENGINE) is None
    assert "expected no tool call" in evaluate(case, outcome(text="4"), ENGINE)


def test_expect_all_tools_reports_what_was_asked_for_versus_run():
    case = {"id": "multistep", "expect_all_tools": ["profile_data", "inline_chart"]}
    partial = outcome(
        tool_calls=[("profile_data", {})],
        tool_names=["profile_data"],
        tool_results=[("profile_data", "--- DATA PROFILE: sales_q3.csv ---")],
        requested_names=["profile_data", "inline_chart"],
    )
    reason = evaluate(case, partial, ENGINE)
    assert "never ran inline_chart" in reason
    assert "model asked for" in reason


def test_args_predicate_failure_names_the_args():
    case = {
        "id": "args",
        "expect_tool": "inline_chart",
        "args_predicate": lambda a: a.get("x_column") == "month",
    }
    bad = outcome(
        tool_calls=[("inline_chart", {"x_column": "quarter"})],
        tool_names=["inline_chart"],
        tool_results=[("inline_chart", "Chart generated and sent to user successfully.")],
        requested_names=["inline_chart"],
    )
    assert "unusable args" in evaluate(case, bad, ENGINE)


def test_must_not_contain_still_catches_invented_content():
    case = {"id": "hallucination", "must_not_contain": ["revenue increased"]}
    reason = evaluate(case, outcome(text="The report shows revenue increased 12%."), ENGINE)
    assert "forbidden" in reason


@pytest.mark.parametrize("field", ["chart", "tool_results", "requested_names"])
def test_scoring_tolerates_a_missing_field(field):
    """An outcome built by an older harness must not crash the scorer."""
    partial = outcome()
    del partial[field]
    assert evaluate({"id": "x"}, partial, ENGINE) is None


# -- Harvesting results out of the wire traffic ---------------------------
#
# The recorders read what tools returned from the *next outgoing request*,
# because both engines send results back to the model. That keeps production
# code unaware it is being measured -- but it means the harvesting has to
# understand two different wire shapes, so both are exercised here.

def test_gemini_recorder_harvests_function_responses():
    """Genuine types.Part objects, not mocks, for fake_gemini.py's reason.

    function_response is a computed attribute over the part; a mock would
    return whatever the test asked for while the real accessor was wrong.
    """
    from google.genai import types
    from tests.eval.conftest import RecordingClient

    recorder = RecordingClient(inner=None)
    models = recorder.models

    contents = [
        types.Content(role="model", parts=[types.Part.from_function_call(name="search_files", args={"keyword": "sales"})]),
        types.Content(role="user", parts=[types.Part.from_function_response(
            name="search_files", response={"result": "Found 1 file(s): sales_q3.csv"})]),
    ]
    models._harvest_results(contents)
    assert recorder.tool_results == [("search_files", "Found 1 file(s): sales_q3.csv")]

    # Contents grow within a turn; a second call must not re-record the first.
    contents.append(types.Content(role="user", parts=[types.Part.from_function_response(
        name="read_file", response={"result": "ZEPHYR-441"})]))
    models._harvest_results(contents)
    assert recorder.tool_results == [
        ("search_files", "Found 1 file(s): sales_q3.csv"),
        ("read_file", "ZEPHYR-441"),
    ]


def test_gemini_recorder_ignores_a_turn_with_no_results():
    from google.genai import types
    from tests.eval.conftest import RecordingClient

    recorder = RecordingClient(inner=None)
    recorder.models._harvest_results([
        types.Content(role="user", parts=[types.Part.from_text(text="hello")])
    ])
    recorder.models._harvest_results(None)
    assert recorder.tool_results == []


def test_ollama_recorder_harvests_tool_messages():
    """Ollama's shape: a result comes back as a role='tool' message."""
    from tests.eval.conftest import OllamaRecorder

    recorder = OllamaRecorder()
    messages = [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "find sales"},
        {"role": "assistant", "tool_calls": [{"function": {"name": "search_files", "arguments": {}}}]},
        {"role": "tool", "name": "search_files", "content": "Found 1 file(s): sales_q3.csv"},
    ]
    recorder._harvest_results({"messages": messages})
    assert recorder.tool_results == [("search_files", "Found 1 file(s): sales_q3.csv")]

    messages.append({"role": "tool", "name": "read_file", "content": "ZEPHYR-441"})
    recorder._harvest_results({"messages": messages})
    assert recorder.tool_results == [
        ("search_files", "Found 1 file(s): sales_q3.csv"),
        ("read_file", "ZEPHYR-441"),
    ]


def test_ollama_recorder_survives_a_payload_without_messages():
    from tests.eval.conftest import OllamaRecorder

    recorder = OllamaRecorder()
    recorder._harvest_results(None)
    recorder._harvest_results({})
    assert recorder.tool_results == []
