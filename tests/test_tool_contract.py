"""Contract tests for the agent loop, driven by a scripted LLM.

These are the tests that answer "does the harness behave correctly", as
distinct from "does the model give a good answer" (see tests/eval/). They are
deterministic, offline and free.

Tests marked xfail(strict=True) document a real, known defect. They land green;
the moment the defect is fixed they XPASS and the marker must be removed, which
forces the fix branch to acknowledge them.
"""

import pytest

from src.backend import brain
from tests.support.fake_gemini import function_call_response, text_response

# The tool names Lithe intends to expose. This is the contract: whatever is
# declared to the model must be dispatchable by the same name.
EXPECTED_TOOL_NAMES = {
    "rename_file",
    "delete_file",
    "write_file",
    "search_files",
    "read_file",
    "profile_data",
    "inline_chart",
    "create_watch_rule",
    "list_watch_rules",
    "delete_watch_rule",
}


def _drain(generator):
    """Consume chat_stream() fully and return the yielded events."""
    return list(generator)


def _probe_declared_names(scripted_gemini):
    """Run one throwaway turn to capture the tool names Lithe declares."""
    client = scripted_gemini([text_response("probe")])
    brain.chat("probe")
    names = client.declared_tool_names()
    brain._chat_history = []
    return names


def _as_the_model_would_call_it(declared: set, intended: str) -> str:
    """The name the model will actually emit when it wants `intended`.

    A model can only call a tool by the name it was given. Scripting the name
    we *wish* were declared would bypass the very mismatch these tests exist to
    catch, so resolve the intent against what was really declared. Once
    declaration and dispatch agree, this returns `intended` unchanged.
    """
    if intended in declared:
        return intended
    prefixed = sorted(n for n in declared if n.startswith(intended))
    return prefixed[0] if prefixed else intended


# ---------------------------------------------------------------------------
# Tool declaration vs dispatch
# ---------------------------------------------------------------------------

def test_declared_tool_names_match_dispatch_map(isolated_db, scripted_gemini):
    client = scripted_gemini([text_response("hi")])
    brain.chat("hello")
    assert client.declared_tool_names() == EXPECTED_TOOL_NAMES


def test_declared_tool_names_match_dispatch_map_streaming(isolated_db, scripted_gemini):
    client = scripted_gemini([text_response("hi")])
    _drain(brain.chat_stream("hello"))
    assert client.declared_tool_names() == EXPECTED_TOOL_NAMES


def test_ollama_schema_matches_gemini_declarations(isolated_db, scripted_gemini):
    """The two providers must offer the model the same tool vocabulary.

    They drifted precisely because the tool contract is written out three times
    (Gemini closures, tool_map, OLLAMA_TOOLS_SCHEMA).
    """
    client = scripted_gemini([text_response("hi")])
    brain.chat("hello")
    ollama_names = {t["function"]["name"] for t in brain.OLLAMA_TOOLS_SCHEMA}
    assert ollama_names <= client.declared_tool_names()


# ---------------------------------------------------------------------------
# Dispatch actually reaching the implementation
# ---------------------------------------------------------------------------

def test_profile_data_call_is_dispatched(isolated_db, scripted_gemini):
    declared = _probe_declared_names(scripted_gemini)
    called_as = _as_the_model_would_call_it(declared, "profile_data")

    client = scripted_gemini([
        function_call_response(called_as, {"file_path": "missing.csv"}),
        text_response("here is the profile"),
    ])
    brain.chat("profile missing.csv")

    # The second call carries the tool result back to the model.
    fed_back = " ".join(client.function_response_texts(1))
    assert "not recognized" not in fed_back


@pytest.mark.parametrize("tool_name,args", [
    ("list_watch_rules", {}),
    ("create_watch_rule", {"directory": "C:\\nope", "pattern": "*.csv"}),
    ("delete_watch_rule", {"rule_id": 1}),
])
def test_watch_rule_tools_are_dispatched(isolated_db, scripted_gemini, tool_name, args):
    declared = _probe_declared_names(scripted_gemini)
    called_as = _as_the_model_would_call_it(declared, tool_name)

    client = scripted_gemini([
        function_call_response(called_as, args),
        text_response("ok"),
    ])
    brain.chat("manage my watch rules")
    fed_back = " ".join(client.function_response_texts(1))
    assert "not recognized" not in fed_back


# ---------------------------------------------------------------------------
# The real safety gate: mutating tools must be proposed, never auto-executed.
#
# tests/test_tools.py proves execute_delete(safeword_active=False) refuses, but
# every LLM-facing wrapper passes safeword_active=True, so that guard is dead
# code on this path. The actual gate is the proposal handshake below, which had
# no test at all before these.
# ---------------------------------------------------------------------------

def test_mutating_tool_returns_proposal_without_touching_disk(
    isolated_db, scripted_gemini, tmp_path
):
    victim = tmp_path / "precious.txt"
    victim.write_text("do not delete me", encoding="utf-8")

    scripted_gemini([function_call_response("delete_file", {"path": str(victim)})])
    result = brain.chat(f"delete {victim}")

    assert isinstance(result, dict) and "tool_proposal" in result
    assert result["tool_proposal"]["name"] == "delete_file"
    assert victim.exists(), "file was deleted before the user confirmed"
    assert brain._pending_tool_calls, "no pending call stashed for confirmation"


def test_reject_leaves_file_and_records_audit_row(
    isolated_db, scripted_gemini, tmp_path, monkeypatch
):
    monkeypatch.setattr(brain, "_current_conversation_id", "test-conv")
    victim = tmp_path / "precious.txt"
    victim.write_text("do not delete me", encoding="utf-8")

    scripted_gemini([
        function_call_response("delete_file", {"path": str(victim)}),
        text_response("understood, cancelled"),
    ])
    brain.chat(f"delete {victim}")
    brain.handle_tool_response(accept=False)

    assert victim.exists(), "rejecting the proposal still deleted the file"

    # get_action_history() does not select decision_outcome; export does.
    from src.backend.memory import export_action_history
    outcomes = [row["decision_outcome"] for row in export_action_history()]
    assert "rejected" in outcomes


def test_accept_executes_and_clears_pending_state(
    isolated_db, scripted_gemini, tmp_path, monkeypatch
):
    monkeypatch.setattr(brain, "_current_conversation_id", "test-conv")
    victim = tmp_path / "goner.txt"
    victim.write_text("bye", encoding="utf-8")

    scripted_gemini([
        function_call_response("delete_file", {"path": str(victim)}),
        text_response("deleted it"),
    ])
    brain.chat(f"delete {victim}")
    brain.handle_tool_response(accept=True)

    assert not victim.exists(), "accepting the proposal did not delete the file"
    assert brain._pending_session is None
    assert brain._pending_tool_calls is None


# ---------------------------------------------------------------------------
# Defects must not masquerade as connectivity failures
# ---------------------------------------------------------------------------

def test_missing_tool_argument_is_reported_as_a_bug(isolated_db, scripted_gemini):
    """A model that omits a required argument triggers a KeyError in the diff
    builder (`call.args['path']`). That is a defect in Lithe, and it must not be
    laundered into "Gemini connection failed" and a silent engine switch — which
    is what the old blanket `except (..., Exception)` did.
    """
    scripted_gemini([function_call_response("delete_file", {})])  # no 'path'
    result = brain.chat("delete something")

    assert isinstance(result, str)
    assert "internal error" in result.lower(), result
    assert brain.active_engine != "ollama", "a bug silently switched engines"


# ---------------------------------------------------------------------------
# Multi-step reasoning (B3)
# ---------------------------------------------------------------------------

def test_second_round_tool_call_is_executed(isolated_db, scripted_gemini):
    """search_files, then act on what came back — the essence of an agent."""
    client = scripted_gemini([
        function_call_response("search_files", {"keyword": "report"}),
        function_call_response("search_files", {"keyword": "report-2024"}),
        text_response("found it"),
    ])
    brain.chat("find my report and tell me about it")

    # Round 2's tool call must itself be executed, requiring a third model call.
    assert client.call_count >= 3, (
        f"expected >=3 model calls for a two-round conversation, got {client.call_count}"
    )


def test_confirming_a_tool_resumes_the_loop(isolated_db, scripted_gemini, tmp_path, monkeypatch):
    """Accepting a mutating tool must return to the loop, not end the turn.

    The confirmation handshake interrupts the round sequence, so the resumed
    turn has to carry the remaining budget and keep executing tools; otherwise
    "delete this, then tell me what's left" stops after the delete.
    """
    monkeypatch.setattr(brain, "_current_conversation_id", "test-conv")
    victim = tmp_path / "goner.txt"
    victim.write_text("bye", encoding="utf-8")

    client = scripted_gemini([
        function_call_response("delete_file", {"path": str(victim)}),
        function_call_response("search_files", {"keyword": "anything"}),
        text_response("deleted it, and here is what is left"),
    ])
    brain.chat(f"delete {victim} then search for anything")
    result = brain.handle_tool_response(accept=True)

    assert not victim.exists()
    # The search_files round after the confirmation needs its own model call.
    assert client.call_count >= 3, (
        f"loop did not resume after confirmation ({client.call_count} model calls)"
    )
    assert "here is what is left" in str(result)


def test_agent_loop_is_bounded(isolated_db, scripted_gemini):
    """A model that keeps calling tools must be stopped, not followed forever."""
    endless = [function_call_response("search_files", {"keyword": "x"}) for _ in range(20)]
    client = scripted_gemini(endless)
    result = brain.chat("loop please")

    assert client.call_count <= 8, f"unbounded tool loop: {client.call_count} model calls"
    assert isinstance(result, (str, dict))
