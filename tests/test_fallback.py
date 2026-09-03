"""Tests for the Ollama fallback's readiness check.

The check used to ask only whether the Ollama server answered `/api/tags`. A
machine running Ollama without the configured model pulled therefore passed,
and the real request then failed with a bare 404 that surfaced as "Error
continuing conversation" — so every Gemini outage on such a machine looked like
a Lithe bug rather than one `ollama pull` away from working. This was not
hypothetical: the dev machine had `llama3.2` and `llama3` installed while
OLLAMA_MODEL was `llama3.1`.
"""

import httpx
import pytest

from src.backend import brain


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def install_tags(monkeypatch, names, status_code=200):
    """Make /api/tags report exactly `names`."""
    payload = {"models": [{"name": n} for n in names]}

    def fake_get(url, *args, **kwargs):
        assert "/api/tags" in url
        return FakeResponse(payload, status_code)

    monkeypatch.setattr(httpx, "get", fake_get)


def unreachable(monkeypatch):
    def fake_get(url, *args, **kwargs):
        raise httpx.ConnectError("nothing listening")

    monkeypatch.setattr(httpx, "get", fake_get)


# ---------------------------------------------------------------------------
# Tag matching
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "configured,installed,expected",
    [
        ("llama3.2", ["llama3.2:latest"], True),      # bare name means :latest
        ("llama3.2:latest", ["llama3.2:latest"], True),
        ("llama3.1", ["llama3.2:latest", "llama3:latest"], False),
        ("llama3", ["llama3.2:latest"], False),       # not a prefix match
        ("", ["llama3:latest"], False),
    ],
)
def test_model_tag_matching(configured, installed, expected):
    assert brain._model_is_pulled(configured, installed) is expected


# ---------------------------------------------------------------------------
# Readiness
# ---------------------------------------------------------------------------

def test_a_running_server_without_the_model_is_not_available(monkeypatch):
    """The exact case the old check waved through."""
    monkeypatch.setattr(brain, "OLLAMA_MODEL", "llama3.1")
    install_tags(monkeypatch, ["llama3.2:latest", "llama3:latest"])
    assert brain._check_ollama_available() is False


def test_a_running_server_with_the_model_is_available(monkeypatch):
    monkeypatch.setattr(brain, "OLLAMA_MODEL", "llama3.2")
    install_tags(monkeypatch, ["llama3.2:latest"])
    assert brain._check_ollama_available() is True


def test_an_unreachable_server_is_not_available(monkeypatch):
    unreachable(monkeypatch)
    assert brain._check_ollama_available() is False


def test_a_non_200_from_tags_is_not_available(monkeypatch):
    install_tags(monkeypatch, ["llama3.2:latest"], status_code=500)
    assert brain._check_ollama_available() is False


# ---------------------------------------------------------------------------
# What the user is told
# ---------------------------------------------------------------------------

def test_a_missing_model_names_the_ones_installed(monkeypatch):
    """A dead end becomes one command: the message has to say which."""
    monkeypatch.setattr(brain, "OLLAMA_MODEL", "llama3.1")
    install_tags(monkeypatch, ["llama3.2:latest", "llama3:latest"])

    message = brain._ollama_chat("system", "hello", tool_map={})

    assert "llama3.1" in message
    assert "llama3.2:latest" in message, "did not say what is actually installed"
    assert "ollama pull" in message


def test_a_stopped_server_is_reported_as_stopped(monkeypatch):
    unreachable(monkeypatch)
    message = brain._ollama_chat("system", "hello", tool_map={})

    assert "not running" in message
    assert "ollama serve" in message
