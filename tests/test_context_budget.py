"""Tests for what Lithe sends the model, and what it refuses to remember.

Two separate growth problems are covered here:

  * **Transcript growth.** `_chat_history` was appended to forever and sent
    whole on every request. It is now kept whole in memory but sent as a
    trimmed window.
  * **File-context growth.** F-04 appended up to 100KB of a named file onto the
    user message, which was then persisted and replayed on every later turn for
    the life of the conversation. That content now rides in the system
    instruction and never enters the transcript at all.

The trimming tests care most about *where* a window may be cut: a payload that
starts with a function_response whose function_call was trimmed away is
rejected by Gemini outright, so a shorter conversation is not automatically a
valid one.
"""

from google.genai import types

from src.backend import brain, memory
from src.backend.context_budget import (
    content_size,
    drop_orphan_prefix,
    is_turn_start,
    trim_blocks,
    trim_history,
)
from tests.support.fake_gemini import function_call_response, text_response


def user(text):
    return types.Content(role="user", parts=[types.Part.from_text(text=text)])


def model(text):
    return types.Content(role="model", parts=[types.Part.from_text(text=text)])


def tool_call(name="search_files", **args):
    return types.Content(
        role="model", parts=[types.Part.from_function_call(name=name, args=args)]
    )


def tool_result(name="search_files", result="ok"):
    return types.Content(
        role="user",
        parts=[types.Part.from_function_response(name=name, response={"result": result})],
    )


# ---------------------------------------------------------------------------
# Where a request payload may legally begin
# ---------------------------------------------------------------------------

def test_a_tool_result_is_not_a_legal_window_start():
    """The whole reason trimming cannot just slice the last N entries."""
    assert is_turn_start(user("hello"))
    assert not is_turn_start(tool_result())
    assert not is_turn_start(model("hi"))


def test_trim_never_cuts_a_tool_exchange_in_half():
    history = [
        user("a" * 5000),
        tool_call(),
        tool_result(result="b" * 5000),
        model("done"),
        user("what next?"),
    ]
    trimmed = trim_history(history, max_chars=3000)

    assert is_turn_start(trimmed[0]), "payload starts on an orphaned tool turn"
    # Cutting at the only other legal boundary leaves just the final question.
    assert trimmed == history[-1:]


def test_history_that_fits_is_returned_unchanged():
    history = [user("hi"), model("hello"), user("again")]
    assert trim_history(history, max_chars=10_000) == history


def test_oldest_turns_are_dropped_first():
    history = []
    for i in range(10):
        history.append(user(f"question {i} " + "x" * 900))
        history.append(model(f"answer {i}"))
    history.append(user("the current question"))

    trimmed = trim_history(history, max_chars=3000)

    assert len(trimmed) < len(history)
    assert trimmed[-1] is history[-1], "the turn being answered was dropped"
    assert trimmed[0] is not history[0], "nothing was trimmed"
    assert sum(content_size(c) for c in trimmed) <= 3000


def test_a_single_oversized_turn_is_kept_anyway():
    """Dropping the message being answered would be worse than being over."""
    history = [user("old"), model("older"), user("y" * 50_000)]
    trimmed = trim_history(history, max_chars=1000)
    assert trimmed == history[-1:]


def test_drop_orphan_prefix_discards_leading_tool_traffic():
    """A bounded reload from SQLite can slice into a tool exchange."""
    history = [tool_result(), model("stranded"), user("real start"), model("ok")]
    assert drop_orphan_prefix(history) == history[2:]


def test_drop_orphan_prefix_on_all_orphans_returns_nothing():
    assert drop_orphan_prefix([tool_result(), model("stranded")]) == []


def test_trim_blocks_evicts_the_oldest_file():
    blocks = [("a.txt", "a" * 100), ("b.txt", "b" * 100), ("c.txt", "c" * 100)]
    kept = trim_blocks(blocks, max_chars=250)
    assert [key for key, _ in kept] == ["b.txt", "c.txt"]


def test_trim_blocks_keeps_the_newest_even_when_oversized():
    kept = trim_blocks([("big.txt", "x" * 9999)], max_chars=100)
    assert [key for key, _ in kept] == ["big.txt"]


# ---------------------------------------------------------------------------
# File context must not enter the transcript
# ---------------------------------------------------------------------------

def test_file_content_reaches_the_model_but_not_the_history(
    indexed_workspace, scripted_gemini, monkeypatch
):
    """The core regression: naming a file must not enlarge the saved turn."""
    monkeypatch.setattr(brain, "_current_conversation_id", "ctx-conv")
    monkeypatch.setattr(brain, "_context_blocks", [])
    indexed_workspace.add("budget.csv", "month,spend\njan,SENTINEL_VALUE\n")

    client = scripted_gemini([text_response("here you go")])
    brain.chat("summarize budget.csv")

    assert "SENTINEL_VALUE" in client.system_instruction(0), (
        "the model was never given the file it was asked about"
    )

    saved_user_turns = [
        part.text
        for content in brain._chat_history
        if content.role == "user"
        for part in (content.parts or [])
        if part.text
    ]
    assert saved_user_turns == ["summarize budget.csv"]


def test_file_content_is_not_persisted_to_sqlite(
    indexed_workspace, scripted_gemini, monkeypatch
):
    """The durable half of the bug: it used to survive a restart."""
    monkeypatch.setattr(brain, "_current_conversation_id", "ctx-conv")
    monkeypatch.setattr(brain, "_context_blocks", [])
    indexed_workspace.add("budget.csv", "month,spend\njan,SENTINEL_VALUE\n")

    scripted_gemini([text_response("here you go")])
    brain.chat("summarize budget.csv")

    rows = memory.get_chat_history("ctx-conv")
    assert rows, "nothing was saved at all"
    assert not any("SENTINEL_VALUE" in (row["content"] or "") for row in rows)


def test_a_named_file_stays_available_for_the_next_turn(
    indexed_workspace, scripted_gemini, monkeypatch
):
    """Moving context out of the transcript must not break follow-ups.

    "now list its columns" names no file, so retrieval finds nothing; the
    content has to come from the session cache instead.
    """
    monkeypatch.setattr(brain, "_current_conversation_id", "ctx-conv")
    monkeypatch.setattr(brain, "_context_blocks", [])
    indexed_workspace.add("budget.csv", "month,spend\njan,SENTINEL_VALUE\n")

    client = scripted_gemini([text_response("one"), text_response("two")])
    brain.chat("summarize budget.csv")
    brain.chat("now list its columns")

    assert "SENTINEL_VALUE" in client.system_instruction(1), (
        "the follow-up lost the file the user was still asking about"
    )


def test_the_context_cache_is_bounded(indexed_workspace, scripted_gemini, monkeypatch):
    """Naming file after file cannot grow the request without limit."""
    monkeypatch.setattr(brain, "_current_conversation_id", "ctx-conv")
    monkeypatch.setattr(brain, "_context_blocks", [])
    monkeypatch.setattr("src.backend.context_budget.MAX_CONTEXT_CHARS", 4000)

    for i in range(6):
        indexed_workspace.add(f"file{i}.txt", f"MARKER_{i} " + "z" * 1500)

    client = scripted_gemini([text_response(f"ok {i}") for i in range(6)])
    for i in range(6):
        brain.chat(f"summarize file{i}.txt")

    final = client.system_instruction(5)
    assert "MARKER_5" in final, "the file just asked about was evicted"
    assert "MARKER_0" not in final, "the cache grew without bound"


def test_a_new_conversation_forgets_the_previous_files(
    indexed_workspace, scripted_gemini, monkeypatch
):
    monkeypatch.setattr(brain, "_current_conversation_id", "ctx-conv")
    monkeypatch.setattr(brain, "_context_blocks", [])
    indexed_workspace.add("budget.csv", "month,spend\njan,SENTINEL_VALUE\n")

    client = scripted_gemini([text_response("one"), text_response("two")])
    brain.chat("summarize budget.csv")
    brain.new_conversation()
    brain.chat("unrelated question")

    assert "SENTINEL_VALUE" not in client.system_instruction(1)


def test_file_content_is_not_scanned_for_hallucination_keywords(
    indexed_workspace, scripted_gemini, monkeypatch
):
    """Content used to be concatenated onto the message the guard inspects.

    A file whose text happens to contain "delete" and "file" tripped the
    mutating-intent branch, so an ordinary summary came back as an ERROR.
    """
    monkeypatch.setattr(brain, "_current_conversation_id", "ctx-conv")
    monkeypatch.setattr(brain, "_context_blocks", [])
    indexed_workspace.add("runbook.txt", "step 1: delete the stale file\n")

    scripted_gemini([text_response("Done. Here is the summary.")])
    answer = brain.chat("summarize runbook.txt")

    assert "ERROR:" not in str(answer), answer


# ---------------------------------------------------------------------------
# The transcript itself
# ---------------------------------------------------------------------------

def test_a_trimmed_request_does_not_erase_in_memory_history(
    isolated_db, scripted_gemini, monkeypatch
):
    """`_chat_history = contents.copy()` used to delete whatever was trimmed."""
    monkeypatch.setattr(brain, "_current_conversation_id", "ctx-conv")
    monkeypatch.setattr("src.backend.context_budget.MAX_HISTORY_CHARS", 2000)

    scripted_gemini([text_response(f"reply {i}") for i in range(6)])
    for i in range(6):
        brain.chat(f"question {i} " + "q" * 800)

    user_turns = [c for c in brain._chat_history if c.role == "user"]
    assert len(user_turns) == 6, (
        f"history lost turns to trimming: {len(user_turns)} of 6 survived"
    )


def test_the_payload_is_trimmed_even_though_history_is_not(
    isolated_db, scripted_gemini, monkeypatch
):
    monkeypatch.setattr(brain, "_current_conversation_id", "ctx-conv")
    monkeypatch.setattr("src.backend.context_budget.MAX_HISTORY_CHARS", 2000)

    client = scripted_gemini([text_response(f"reply {i}") for i in range(6)])
    for i in range(6):
        brain.chat(f"question {i} " + "q" * 800)

    sent = client.calls[-1]["contents"]
    assert len(sent) < len(brain._chat_history)
    assert sum(content_size(c) for c in sent) <= 2000


def test_tool_traffic_is_persisted_so_a_reload_is_valid(
    isolated_db, scripted_gemini, monkeypatch
):
    """A saved function_response needs its function_call saved too.

    The intra-turn tool messages only ever existed in memory, so restarting
    Lithe rebuilt a transcript whose first tool turn was an orphan -- which
    Gemini rejects with a 400 rather than simply forgetting.
    """
    monkeypatch.setattr(brain, "_current_conversation_id", "ctx-conv")

    scripted_gemini([
        function_call_response("search_files", {"keyword": "report"}),
        text_response("found it"),
    ])
    brain.chat("find my report")

    rows = memory.get_chat_history("ctx-conv")
    assert any(row["tool_proposal_json"] for row in rows), "no function_call was saved"
    assert any(row["tool_resolution"] for row in rows), "no function_response was saved"

    memory.set_app_state("active_conversation_id", "ctx-conv")
    brain._load_history()
    for i, content in enumerate(brain._chat_history):
        has_response = any(
            part.function_response is not None for part in (content.parts or [])
        )
        if has_response:
            earlier = brain._chat_history[:i]
            assert any(
                part.function_call is not None
                for c in earlier
                for part in (c.parts or [])
            ), "reloaded a function_response with no preceding function_call"


def test_reload_is_capped(isolated_db, scripted_gemini, monkeypatch):
    monkeypatch.setattr("src.backend.brain.MAX_HISTORY_MESSAGES", 10)

    for i in range(40):
        memory.save_message(f"m{i}", "ctx-conv", "user", f"message {i}", None, None)
    memory.set_app_state("active_conversation_id", "ctx-conv")

    brain._load_history()
    assert len(brain._chat_history) <= 10


def test_parallel_tool_calls_all_survive_a_reload(isolated_db, monkeypatch):
    """_save_content used to assign rather than accumulate.

    A model turn carrying two function calls reloaded as one call and one
    response, which is not a payload Gemini will accept.
    """
    monkeypatch.setattr(brain, "_current_conversation_id", "ctx-conv")

    brain._save_content(types.Content(
        role="user", parts=[types.Part.from_text(text="do two things")]
    ))
    brain._save_content(types.Content(role="model", parts=[
        types.Part.from_function_call(name="search_files", args={"keyword": "a"}),
        types.Part.from_function_call(name="search_files", args={"keyword": "b"}),
    ]))
    brain._save_content(types.Content(role="user", parts=[
        types.Part.from_function_response(name="search_files", response={"result": "ra"}),
        types.Part.from_function_response(name="search_files", response={"result": "rb"}),
    ]))

    memory.set_app_state("active_conversation_id", "ctx-conv")
    brain._load_history()

    calls = [
        part for content in brain._chat_history
        for part in (content.parts or []) if part.function_call is not None
    ]
    responses = [
        part for content in brain._chat_history
        for part in (content.parts or []) if part.function_response is not None
    ]
    assert len(calls) == 2, f"lost a function_call on reload: {len(calls)}"
    assert len(responses) == 2, f"lost a function_response on reload: {len(responses)}"


def test_a_legacy_single_object_row_still_loads(isolated_db, monkeypatch):
    """Rows written before calls were stored as a list must stay readable."""
    import json

    monkeypatch.setattr(brain, "_current_conversation_id", "ctx-conv")
    memory.save_message("m0", "ctx-conv", "user", "find it", None, None)
    memory.save_message(
        "m1", "ctx-conv", "model", "",
        json.dumps({"name": "search_files", "args": {"keyword": "x"}}), None,
    )
    memory.set_app_state("active_conversation_id", "ctx-conv")

    brain._load_history()

    names = [
        part.function_call.name
        for content in brain._chat_history
        for part in (content.parts or [])
        if part.function_call is not None
    ]
    assert names == ["search_files"]


def test_an_unconfirmed_proposal_is_closed_out_by_the_next_message(
    isolated_db, scripted_gemini, monkeypatch, tmp_path
):
    """Ignoring a confirmation prompt must not dangle a function_call.

    Proposing a mutating tool records the call. If the user just types
    something else, the call needs an answer or every later request carries an
    unresolved one.
    """
    monkeypatch.setattr(brain, "_current_conversation_id", "ctx-conv")
    victim = tmp_path / "keep.txt"
    victim.write_text("still here", encoding="utf-8")

    scripted_gemini([
        function_call_response("delete_file", {"path": str(victim)}),
        text_response("sure, something else then"),
    ])
    brain.chat(f"delete {victim}")
    brain.chat("actually never mind, what is 2+2?")

    assert victim.exists(), "the file was deleted without confirmation"
    assert brain._pending_tool_calls is None, "pending state was left armed"

    calls = sum(
        1 for content in brain._chat_history
        for part in (content.parts or []) if part.function_call is not None
    )
    responses = sum(
        1 for content in brain._chat_history
        for part in (content.parts or []) if part.function_response is not None
    )
    assert calls == responses == 1, f"{calls} calls vs {responses} responses"


def test_history_endpoint_keeps_the_shape_the_ui_expects(isolated_db, monkeypatch):
    """The UI renders one proposal card per message, from an object.

    Storing calls as a list is a backend detail; ToolProposalCard reads
    proposal.name and proposal.args.path directly, so a list would render an
    untitled card with no diff.
    """
    from fastapi.testclient import TestClient

    from src.backend import server

    monkeypatch.setattr(brain, "_current_conversation_id", "ui-conv")
    brain._save_content(types.Content(role="model", parts=[
        types.Part.from_function_call(name="delete_file", args={"path": "C:/x.txt"}),
    ]))

    with TestClient(server.app) as client:
        payload = client.get("/api/chat/history?conversation_id=ui-conv").json()

    proposals = [m["tool_proposal"] for m in payload["history"] if m.get("tool_proposal")]
    assert proposals, "the proposal never reached the UI"
    assert proposals[0]["name"] == "delete_file"
    assert proposals[0]["args"]["path"] == "C:/x.txt"
