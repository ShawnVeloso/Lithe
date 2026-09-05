"""Tests for the Ollama fallback as a real engine rather than a stub.

Until now this path had three deficits, all invisible while the fallback itself
was broken by an unpulled model:

  * **No conversation history.** It sent `[system, user]` and nothing else, so
    every turn was amnesiac -- "summarize budget.csv" then "now list its
    columns" left the second turn with no idea what "its" meant.
  * **No agent loop.** It executed `tool_calls[0]`, asked once more with tools
    withdrawn, and stopped. It could not search and then read what it found.
  * **No transcript record.** Its tool traffic never reached `_chat_history`,
    so switching back to Gemini mid-conversation replayed a history with holes.

The engine is chosen by an outage, not a setting, so these drive `brain.chat()`
with an unreachable Gemini client -- exactly what a real fallback looks like.
"""

import pytest
from google.genai import types

from src.backend import brain, memory
from src.backend.ollama_bridge import call_name_and_args, to_ollama_messages
from tests.support.fake_ollama import (
    ScriptedOllama,
    force_gemini_outage,
    text_message,
    tool_call_message,
)


@pytest.fixture
def ollama(monkeypatch):
    """A scripted Ollama, with Gemini unreachable so the fallback is taken."""
    monkeypatch.setattr(brain, "OLLAMA_MODEL", "llama3.2")
    monkeypatch.setattr(brain, "_current_conversation_id", "ollama-conv")
    monkeypatch.setattr(brain, "_context_blocks", [])
    force_gemini_outage(monkeypatch, brain)

    def _install(responses=None, default="Done."):
        return ScriptedOllama(responses, default=default).install(monkeypatch)

    return _install


# ---------------------------------------------------------------------------
# Transcript translation
# ---------------------------------------------------------------------------

def test_roles_are_translated_not_renamed():
    """A tool result is a `user` turn to Gemini and a `tool` turn to Ollama."""
    history = [
        types.Content(role="user", parts=[types.Part.from_text(text="hi")]),
        types.Content(role="model", parts=[types.Part.from_text(text="hello")]),
        types.Content(role="model", parts=[
            types.Part.from_function_call(name="search_files", args={"keyword": "x"}),
        ]),
        types.Content(role="user", parts=[
            types.Part.from_function_response(
                name="search_files", response={"result": "found x.txt"}
            ),
        ]),
    ]

    messages = to_ollama_messages(history)

    assert [m["role"] for m in messages] == ["user", "assistant", "assistant", "tool"]
    assert messages[2]["tool_calls"][0]["function"]["name"] == "search_files"
    assert messages[3]["content"] == "found x.txt"


def test_a_result_payload_is_unwrapped_for_the_model():
    """Lithe wraps results as {"result": ...}; the model should read the value."""
    history = [types.Content(role="user", parts=[
        types.Part.from_function_response(name="read_file", response={"result": "body"}),
    ])]
    assert to_ollama_messages(history)[0]["content"] == "body"


def test_call_name_and_args_accepts_both_engines():
    ollama_call = {"function": {"name": "delete_file", "arguments": {"path": "x"}}}
    assert call_name_and_args(ollama_call) == ("delete_file", {"path": "x"})

    gemini_call = types.Part.from_function_call(
        name="delete_file", args={"path": "x"}
    ).function_call
    assert call_name_and_args(gemini_call) == ("delete_file", {"path": "x"})


# ---------------------------------------------------------------------------
# History reaches the fallback
# ---------------------------------------------------------------------------

def test_the_fallback_sees_the_conversation(isolated_db, ollama):
    """The core regression: it used to send [system, user] and nothing more."""
    server = ollama([text_message("first"), text_message("second")])

    brain.chat("what is the capital of France?")
    brain.chat("and its population?")

    second_turn = server.texts(1)
    assert "what is the capital of France?" in second_turn, (
        "the fallback had no memory of the previous question"
    )
    assert "first" in second_turn, "the fallback did not see its own last answer"


def test_the_current_turn_is_not_duplicated(isolated_db, ollama):
    """The transcript already ends with this turn, so it must not be re-added."""
    server = ollama([text_message("only once")])

    brain.chat("a distinctive question")

    sent = server.texts(0)
    assert sum(1 for t in sent if "a distinctive question" in t) == 1, sent


def test_a_one_off_caller_gets_no_conversation(isolated_db, ollama, monkeypatch):
    """Watch-rule summarisation must not inherit the chat transcript."""
    server = ollama([text_message("summary")])
    brain._chat_history.append(
        types.Content(role="user", parts=[types.Part.from_text(text="UNRELATED_CHAT")])
    )

    brain._ollama_chat("system", "summarise this file")

    assert not any("UNRELATED_CHAT" in t for t in server.texts(0))


def test_the_payload_sent_to_ollama_is_budget_trimmed(isolated_db, ollama, monkeypatch):
    monkeypatch.setattr("src.backend.context_budget.MAX_HISTORY_CHARS", 2000)
    server = ollama([text_message(f"reply {i}") for i in range(6)])

    for i in range(6):
        brain.chat(f"question {i} " + "q" * 800)

    # system prompt + a trimmed window, not the whole conversation.
    assert len(server.messages(5)) < len(brain._chat_history) + 1


# ---------------------------------------------------------------------------
# The agent loop
# ---------------------------------------------------------------------------

def test_the_fallback_chains_two_tool_rounds(isolated_db, ollama):
    """search_files, then act on the result -- previously impossible here."""
    server = ollama([
        tool_call_message([("search_files", {"keyword": "report"})]),
        tool_call_message([("read_file", {"path": "report.txt"})]),
        text_message("here is what the report says"),
    ])

    answer = brain.chat("find my report and tell me about it")

    assert server.call_count >= 3, (
        f"the loop stopped after {server.call_count} calls; it cannot chain"
    )
    assert "here is what the report says" in answer


def test_every_call_in_a_parallel_turn_runs(isolated_db, ollama):
    """It used to take tool_calls[0] and silently drop the rest."""
    server = ollama([
        tool_call_message([
            ("search_files", {"keyword": "a"}),
            ("search_files", {"keyword": "b"}),
        ]),
        text_message("both done"),
    ])

    brain.chat("search for a and b")

    tool_turns = [m for m in server.messages(1) if m["role"] == "tool"]
    assert len(tool_turns) == 2, f"only {len(tool_turns)} of 2 calls were executed"


def test_the_loop_is_bounded(isolated_db, ollama):
    """A model that keeps calling tools must be stopped, not followed forever."""
    endless = [
        tool_call_message([("search_files", {"keyword": "x"})]) for _ in range(20)
    ]
    server = ollama(endless)

    brain.chat("loop please")

    assert server.call_count <= brain.MAX_TOOL_ROUNDS + 1, (
        f"ran {server.call_count} calls against a budget of {brain.MAX_TOOL_ROUNDS}"
    )
    # The final call withdraws the tools so the model has to answer in text.
    assert server.tools_offered(server.call_count - 1) == []


# ---------------------------------------------------------------------------
# The confirmation gate
# ---------------------------------------------------------------------------

def test_a_mutating_tool_pauses_without_touching_disk(isolated_db, ollama, tmp_path):
    victim = tmp_path / "victim.txt"
    victim.write_text("still here", encoding="utf-8")
    ollama([tool_call_message([("delete_file", {"path": str(victim)})])])

    result = brain.chat(f"delete {victim}")

    assert victim.exists()
    assert result["tool_proposal"]["name"] == "delete_file"
    assert str(victim) in result["tool_proposal"]["diff"]


def test_a_mutating_call_behind_a_readonly_one_still_pauses(
    isolated_db, ollama, tmp_path
):
    """The same parallel-call hole that existed on the Gemini path."""
    victim = tmp_path / "victim.txt"
    victim.write_text("still here", encoding="utf-8")
    ollama([
        tool_call_message([
            ("search_files", {"keyword": "victim"}),
            ("delete_file", {"path": str(victim)}),
        ]),
    ])

    result = brain.chat("find victim.txt and delete it")

    assert victim.exists(), "a mutating call was executed without confirmation"
    assert result["tool_proposal"]["name"] == "delete_file"


# ---------------------------------------------------------------------------
# The shared transcript
# ---------------------------------------------------------------------------

def test_fallback_tool_traffic_reaches_the_transcript(isolated_db, ollama):
    """Both engines share _chat_history, so a fallback turn must be recorded."""
    ollama([
        tool_call_message([("search_files", {"keyword": "report"})]),
        text_message("found it"),
    ])

    brain.chat("find my report")

    calls = [
        part for content in brain._chat_history
        for part in (content.parts or []) if part.function_call is not None
    ]
    responses = [
        part for content in brain._chat_history
        for part in (content.parts or []) if part.function_response is not None
    ]
    assert len(calls) == 1, "the fallback tool call was not recorded"
    assert len(responses) == 1, "the fallback tool result was not recorded"

    rows = memory.get_chat_history("ollama-conv")
    assert any(row["tool_proposal_json"] for row in rows)
    assert any(row["tool_resolution"] for row in rows)


def test_a_chart_is_not_replayed_as_base64(isolated_db, ollama, monkeypatch):
    """As on the Gemini path: the image must not enter the transcript."""
    monkeypatch.setattr(
        brain, "_inline_chart", lambda *a, **k: "data:image/png;base64,AAAA"
    )
    server = ollama([
        tool_call_message([
            ("inline_chart", {"file_path": "x.csv", "chart_type": "bar",
                              "x_column": "a", "y_column": "b"}),
        ]),
        text_message("charted"),
    ])

    brain.chat("chart it")

    assert not any("base64,AAAA" in str(m) for m in server.messages(1))


# ---------------------------------------------------------------------------
# Confirming a fallback tool
# ---------------------------------------------------------------------------

def test_confirming_a_tool_resumes_the_loop(isolated_db, ollama, tmp_path):
    """Accepting must return to the loop, not end the turn after one call."""
    victim = tmp_path / "goner.txt"
    victim.write_text("bye", encoding="utf-8")
    server = ollama([
        tool_call_message([("delete_file", {"path": str(victim)})]),
        tool_call_message([("search_files", {"keyword": "anything"})]),
        text_message("deleted it, and here is what is left"),
    ])

    brain.chat(f"delete {victim} then search for anything")
    result = brain.handle_tool_response(accept=True)

    assert not victim.exists(), "the confirmed delete never ran"
    assert server.call_count >= 3, (
        f"the loop did not resume ({server.call_count} calls)"
    )
    assert "here is what is left" in str(result)


def test_confirming_runs_the_call_that_was_proposed(isolated_db, ollama, tmp_path):
    """The branch used to resolve tool_calls[0] whatever was confirmed.

    With the gate pausing on the first *mutating* call, a delete behind a
    search meant confirming ran the search and left the delete undone.
    """
    victim = tmp_path / "goner.txt"
    victim.write_text("bye", encoding="utf-8")
    ollama([
        tool_call_message([
            ("search_files", {"keyword": "goner"}),
            ("delete_file", {"path": str(victim)}),
        ]),
        text_message("done"),
    ])

    brain.chat(f"find and delete {victim}")
    brain.handle_tool_response(accept=True)

    assert not victim.exists(), "the confirmed delete was never executed"


def test_rejecting_leaves_the_file_and_records_an_audit_row(
    isolated_db, ollama, tmp_path
):
    victim = tmp_path / "keep.txt"
    victim.write_text("still here", encoding="utf-8")
    ollama([
        tool_call_message([("delete_file", {"path": str(victim)})]),
        text_message("understood"),
    ])

    brain.chat(f"delete {victim}")
    brain.handle_tool_response(accept=False)

    assert victim.exists()
    # get_action_history() does not select decision_outcome; export does.
    outcomes = [row["decision_outcome"] for row in memory.export_action_history()]
    assert "rejected" in outcomes, outcomes


def test_confirmation_clears_the_pending_state(isolated_db, ollama, tmp_path):
    victim = tmp_path / "goner.txt"
    victim.write_text("bye", encoding="utf-8")
    ollama([
        tool_call_message([("delete_file", {"path": str(victim)})]),
        text_message("done"),
    ])

    brain.chat(f"delete {victim}")
    brain.handle_tool_response(accept=True)

    assert brain._pending_ollama_tool_calls is None
    assert brain._pending_ollama_messages is None


# ---------------------------------------------------------------------------
# The hallucination guard must not eat correct answers
# ---------------------------------------------------------------------------

def test_a_real_search_result_is_not_flagged_as_a_hallucination(
    isolated_db, ollama
):
    """The guard ran unconditionally here, so success looked like fabrication.

    It keys on words like "found" and "located", which is exactly how a model
    reports a search that really happened -- so a genuine search_files result
    reached the user as "ERROR: ... failed to actually invoke the system
    search tool".
    """
    ollama([
        tool_call_message([("search_files", {"keyword": "sales"})]),
        text_message("Found 1 file: sales_q3.csv"),
    ])

    answer = brain.chat("find files with 'sales' in the name")

    assert "ERROR" not in str(answer), answer
    assert "sales_q3.csv" in str(answer)


def test_a_claimed_search_with_no_tool_call_is_still_flagged(isolated_db, ollama):
    """Gating the guard must not disable it: this is what it exists for."""
    ollama([text_message("Found 1 file: sales_q3.csv")])

    answer = brain.chat("find files with 'sales' in the name")

    assert "ERROR" in str(answer), answer


# ---------------------------------------------------------------------------
# Charts have to reach the user
# ---------------------------------------------------------------------------

def test_a_chart_is_delivered_and_not_merely_announced(
    isolated_db, ollama, monkeypatch
):
    """The data URI was dropped while the model said it had been sent.

    Lithe replaces the image with "Chart generated and sent to user
    successfully" so a base64 blob does not sit in the transcript -- but it
    then returned only the text, so the model truthfully relayed a delivery
    that never happened.
    """
    monkeypatch.setattr(
        brain, "_inline_chart", lambda *a, **k: "data:image/png;base64,CHARTDATA"
    )
    ollama([
        tool_call_message([
            ("inline_chart", {"file_path": "x.csv", "chart_type": "bar",
                              "x_column": "a", "y_column": "b"}),
        ]),
        text_message("here is your chart"),
    ])

    result = brain.chat("chart revenue by month from x.csv")

    assert isinstance(result, dict), f"the chart was dropped: {result!r}"
    assert result["chart"] == "data:image/png;base64,CHARTDATA"
    assert "here is your chart" in result["text"]


def test_a_streamed_chart_is_yielded_as_its_own_event(
    isolated_db, ollama, monkeypatch
):
    monkeypatch.setattr(
        brain, "_inline_chart", lambda *a, **k: "data:image/png;base64,CHARTDATA"
    )
    ollama([
        tool_call_message([
            ("inline_chart", {"file_path": "x.csv", "chart_type": "bar",
                              "x_column": "a", "y_column": "b"}),
        ]),
        text_message("here is your chart"),
    ])

    events = list(brain.chat_stream("chart revenue by month from x.csv"))

    charts = [e for e in events if e.get("type") == "chart"]
    assert charts, f"no chart event was emitted: {[e.get('type') for e in events]}"
    assert charts[0]["data_uri"] == "data:image/png;base64,CHARTDATA"


def test_a_turn_without_a_chart_returns_plain_text(isolated_db, ollama):
    """The chart flag must not leak from one turn into the next."""
    ollama([text_message("just words")])
    assert brain.chat("say something") == "just words"
