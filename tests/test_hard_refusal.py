"""Refusing a whole-drive target before it becomes a confirmation card.

The system prompt has told the model to STRICTLY REFUSE whole-drive operations
since the first capability run, and llama3.2 proposed `delete_file(path="C:\\")`
anyway. `tools._validate_path` caught it -- but only inside the tool, which is
after the UI has rendered a card reading `DELETE: C:\\` and asked the user to
approve it. A dialog is the wrong control for a target that is never
legitimate: there is nothing for the user to decide, and an alarming card
invites the one click that a backstop then has to survive.

So the refusal moved in front of the proposal. It is deliberately narrow --
the filesystem root and PROTECTED_EXACT only. An ordinary delete, and a
protected *subtree* path, are still proposed, because those are decisions the
user is entitled to make.
"""

import os

import pytest
from google.genai import types

from src.backend import brain, tools
from tests.support.fake_gemini import function_call_response, text_response
from tests.support.fake_ollama import (
    ScriptedOllama,
    force_gemini_outage,
    text_message,
    tool_call_message,
)

DRIVE_ROOT = os.environ.get("SYSTEMDRIVE", "C:") + os.sep
USERS_DIR = os.path.join(os.environ.get("SYSTEMDRIVE", "C:") + os.sep, "Users")


@pytest.fixture
def ollama(monkeypatch):
    """A scripted Ollama with Gemini unreachable, as in test_ollama_path."""
    monkeypatch.setattr(brain, "OLLAMA_MODEL", "llama3.2")
    monkeypatch.setattr(brain, "_current_conversation_id", "refusal-conv")
    monkeypatch.setattr(brain, "_context_blocks", [])
    force_gemini_outage(monkeypatch, brain)

    def _install(responses=None, default="Done."):
        return ScriptedOllama(responses, default=default).install(monkeypatch)

    return _install


# ---------------------------------------------------------------------------
# The tier boundary
# ---------------------------------------------------------------------------

def test_the_two_never_legitimate_tiers_are_refused():
    assert tools.hard_refusal(DRIVE_ROOT) is not None
    assert tools.hard_refusal(USERS_DIR) is not None
    assert tools.hard_refusal(os.path.expanduser("~")) is not None


def test_everything_else_stays_proposable(tmp_path):
    """Narrow on purpose: a backstop the user can override is still a backstop.

    A protected *subtree* path is included here. It is refused by
    _validate_path when the tool runs, and that is the right place for it --
    the user may legitimately be told why C:\\Windows is off limits, which
    requires the proposal to exist.
    """
    assert tools.hard_refusal(str(tmp_path / "ordinary.txt")) is None
    assert tools.hard_refusal(os.path.join(DRIVE_ROOT, "Windows", "note.txt")) is None
    assert tools.hard_refusal("") is None


def test_both_ends_of_a_rename_are_checked(tmp_path):
    """Renaming *onto* a drive root is as irreversible as renaming one."""
    source = tmp_path / "a.txt"
    source.write_text("x", encoding="utf-8")
    call = {"function": {"name": "rename_file", "arguments": {
        "source": str(source), "destination": DRIVE_ROOT,
    }}}
    assert brain._hard_refusal(call) is not None


def test_a_read_only_tool_is_never_hard_refused():
    """The gate guards proposals, and only mutating tools are proposed.

    list_directory on a drive root is refused by _validate_path inside the
    tool, which is correct: relaying that refusal is a useful answer.
    """
    call = {"function": {"name": "list_directory", "arguments": {"path": DRIVE_ROOT}}}
    assert brain._hard_refusal(call) is None


# ---------------------------------------------------------------------------
# The Ollama gate
# ---------------------------------------------------------------------------

def test_no_card_is_shown_for_a_drive_root_delete(isolated_db, ollama):
    scripted = ollama([
        tool_call_message([("delete_file", {"path": DRIVE_ROOT})]),
        text_message("I won't delete a whole drive."),
    ])

    result = brain.chat(f"delete {DRIVE_ROOT}")

    assert not isinstance(result, dict), (
        "a drive-root delete was turned into a confirmation card"
    )
    assert "won't delete" in result
    # The refusal is fed back as the tool's result, which is what lets the
    # model explain it instead of the turn ending in silence.
    tool_results = [
        m["content"] for m in scripted.messages(1) if m["role"] == "tool"
    ]
    assert any("Refusing to operate on the filesystem root" in t for t in tool_results)


def test_the_safeword_does_not_unlock_a_drive_root(isolated_db, ollama):
    """5.1's claim, asserted in code rather than only in the prompt."""
    ollama([
        tool_call_message([("delete_file", {"path": DRIVE_ROOT})]),
        text_message("Still no."),
    ])

    result = brain.chat(f"Override Lithe delete {DRIVE_ROOT}")

    assert not isinstance(result, dict), "the safeword produced a drive-root card"


def test_an_ordinary_delete_is_still_proposed(isolated_db, ollama, tmp_path):
    """The gate must not swallow the confirmations the design rests on."""
    victim = tmp_path / "victim.txt"
    victim.write_text("still here", encoding="utf-8")
    ollama([tool_call_message([("delete_file", {"path": str(victim)})])])

    result = brain.chat(f"delete {victim}")

    assert result["tool_proposal"]["name"] == "delete_file"
    assert victim.exists()


def test_a_refused_call_does_not_hide_a_proposable_one(isolated_db, ollama, tmp_path):
    """A turn carrying both still pauses on the one the user can decide."""
    victim = tmp_path / "victim.txt"
    victim.write_text("still here", encoding="utf-8")
    ollama([
        tool_call_message([
            ("delete_file", {"path": DRIVE_ROOT}),
            ("delete_file", {"path": str(victim)}),
        ]),
    ])

    result = brain.chat("delete everything")

    assert result["tool_proposal"]["args"]["path"] == str(victim)
    assert victim.exists()


# ---------------------------------------------------------------------------
# The Gemini gate
# ---------------------------------------------------------------------------

def test_the_gemini_path_refuses_before_proposing(isolated_db, scripted_gemini):
    client = scripted_gemini([
        function_call_response("delete_file", {"path": DRIVE_ROOT}),
        text_response("I won't delete a whole drive."),
    ])

    result = brain.chat(f"delete {DRIVE_ROOT}")

    assert not isinstance(result, dict), (
        "a drive-root delete was turned into a confirmation card"
    )
    results = client.function_response_texts(1)
    assert any("Refusing to operate on the filesystem root" in r for r in results)


def test_the_gemini_stream_refuses_before_proposing(isolated_db, scripted_gemini):
    scripted_gemini([
        function_call_response("delete_file", {"path": DRIVE_ROOT}),
        text_response("I won't delete a whole drive."),
    ])

    events = list(brain.chat_stream(f"delete {DRIVE_ROOT}"))

    assert not any(e.get("type") == "tool_proposal" for e in events), (
        "the streaming gate proposed a drive-root delete"
    )
