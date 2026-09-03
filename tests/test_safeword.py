"""Tests for the safeword persona switch (F-06).

The safeword is Lithe's primary behavioural override and had no test at any
level. These cover both the pure function and the wiring into chat().
"""

import pytest

from src.backend import brain
from src.backend.prompts.system_prompt import (
    CANDID_SYSTEM_PROMPT,
    COMPLIANT_SYSTEM_PROMPT,
    SAFEWORD,
    detect_safeword,
)
from tests.support.fake_gemini import text_response


# ---------------------------------------------------------------------------
# detect_safeword in isolation
# ---------------------------------------------------------------------------

def test_absent_safeword_leaves_message_untouched():
    active, cleaned = detect_safeword("delete the temp files")
    assert active is False
    assert cleaned == "delete the temp files"


@pytest.mark.parametrize("phrasing", [
    SAFEWORD,
    SAFEWORD.lower(),
    SAFEWORD.upper(),
    "oVeRrIdE lItHe",
])
def test_safeword_detection_is_case_insensitive(phrasing):
    active, _ = detect_safeword(f"{phrasing}, delete the temp files")
    assert active is True


def test_safeword_is_stripped_from_the_message():
    """The model must not see the trigger phrase itself."""
    _, cleaned = detect_safeword(f"{SAFEWORD} delete the temp files")
    assert SAFEWORD.lower() not in cleaned.lower()
    assert "delete the temp files" in cleaned


# ---------------------------------------------------------------------------
# Wiring into the chat path
# ---------------------------------------------------------------------------

def test_plain_message_uses_the_candid_prompt(isolated_db, scripted_gemini):
    client = scripted_gemini([text_response("ok")])
    brain.chat("what do you think of this design?")
    assert client.system_instruction() == CANDID_SYSTEM_PROMPT


def test_safeword_message_uses_the_compliant_prompt(isolated_db, scripted_gemini):
    client = scripted_gemini([text_response("ok")])
    brain.chat(f"{SAFEWORD} just do it")
    assert client.system_instruction() == COMPLIANT_SYSTEM_PROMPT


def test_session_flag_forces_compliant_without_the_phrase(
    isolated_db, scripted_gemini, monkeypatch
):
    """The session toggle (POST /api/config/safeword) makes override sticky.

    Worth pinning down because COMPLIANT_SYSTEM_PROMPT tells the model the
    override "persists only for the current message", which is untrue while
    this flag is set.
    """
    monkeypatch.setattr(brain, "session_safeword_active", True)
    client = scripted_gemini([text_response("ok")])
    brain.chat("no trigger phrase here")
    assert client.system_instruction() == COMPLIANT_SYSTEM_PROMPT


@pytest.mark.xfail(
    strict=True,
    reason="detect_safeword does plain substring matching, so merely quoting "
           "the phrase flips the persona. Flagged as a policy decision, not "
           "fixed: intended behaviour is the user's call.",
)
def test_quoting_the_safeword_does_not_flip_the_persona(isolated_db, scripted_gemini):
    client = scripted_gemini([text_response("ok")])
    brain.chat('please never say "override lithe" to me again')
    assert client.system_instruction() == CANDID_SYSTEM_PROMPT
