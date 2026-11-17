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


# --- GET /api/config/ollama-models ------------------------------------------
#
# The selector's whole point is that a model you cannot serve is visibly a
# model you cannot serve. That requires the endpoint to keep "Ollama is down"
# and "Ollama is up with nothing pulled" apart, because they need different
# things from the user, and conflating them is what let the fallback look
# healthy while it was dead.


def entry(name, family="llama"):
    """One /api/tags row, shaped as Ollama sends it."""
    return {"name": name, "details": {"family": family, "families": [family]}}


def models_client(monkeypatch, installed, current="llama3.2"):
    """`installed` is a list of names, or None for an unreachable Ollama."""
    from fastapi.testclient import TestClient
    from src.backend.server import app
    import src.backend.brain as brain

    catalog = None if installed is None else [
        n if isinstance(n, dict) else entry(n) for n in installed
    ]
    monkeypatch.setattr(brain, "_ollama_catalog", lambda: catalog)
    monkeypatch.setattr(brain, "OLLAMA_MODEL", current)
    return TestClient(app)


def test_lists_installed_models_and_confirms_the_current_one(monkeypatch):
    client = models_client(monkeypatch, ["llama3:latest", "llama3.2:latest"])
    got = client.get("/api/config/ollama-models").json()
    assert got["reachable"] is True
    # Sorted, so the dropdown's order does not depend on Ollama's reply order.
    assert got["installed"] == ["llama3.2:latest", "llama3:latest"]
    assert got["current"] == "llama3.2"
    # `llama3.2` is `llama3.2:latest`; the endpoint must not report the shipped
    # default as missing over a tag suffix.
    assert got["current_installed"] is True


def test_flags_a_current_model_that_is_not_pulled(monkeypatch):
    """The exact configuration that left the fallback silently dead."""
    client = models_client(monkeypatch, ["llama3.2:latest"], current="llama3.1")
    got = client.get("/api/config/ollama-models").json()
    assert got["reachable"] is True
    assert got["current_installed"] is False
    assert got["installed"] == ["llama3.2:latest"]   # so the UI can name what is


def test_unreachable_is_not_the_same_as_nothing_installed(monkeypatch):
    down = models_client(monkeypatch, None).get("/api/config/ollama-models").json()
    empty = models_client(monkeypatch, []).get("/api/config/ollama-models").json()

    assert down["reachable"] is False
    assert empty["reachable"] is True
    assert down["installed"] == empty["installed"] == []
    # Same list, different diagnosis -- which is the point of the flag.
    assert down != empty


def test_an_unreachable_ollama_never_claims_the_model_is_installed(monkeypatch):
    client = models_client(monkeypatch, None)
    assert client.get("/api/config/ollama-models").json()["current_installed"] is False


def test_the_listing_follows_a_live_model_change(monkeypatch):
    """POST /api/config/llm rebinds brain.OLLAMA_MODEL; the listing must see it."""
    import src.backend.brain as brain

    client = models_client(monkeypatch, ["llama3.2:latest", "qwen2.5:latest"])
    assert client.get("/api/config/ollama-models").json()["current"] == "llama3.2"

    monkeypatch.setattr(brain, "OLLAMA_MODEL", "qwen2.5")
    got = client.get("/api/config/ollama-models").json()
    assert got["current"] == "qwen2.5"
    assert got["current_installed"] is True


def test_embedding_models_are_reported_not_hidden(monkeypatch):
    """all-minilm sits in /api/tags beside llama3.2 and cannot chat at all.

    Reported rather than filtered out: a user who has configured one needs to
    be told which entry is the problem, and a name that silently vanishes from
    the list explains nothing.
    """
    client = models_client(
        monkeypatch,
        [entry("llama3.2:latest"), entry("all-minilm:latest", family="bert")],
    )
    got = client.get("/api/config/ollama-models").json()
    assert got["installed"] == ["all-minilm:latest", "llama3.2:latest"]
    assert got["embedding_only"] == ["all-minilm:latest"]


def test_a_chat_model_is_never_called_embedding_only(monkeypatch):
    """The denylist errs toward showing a model: a hidden one cannot be reached."""
    client = models_client(
        monkeypatch,
        [entry("qwen2.5:latest", family="qwen2"), entry("mystery:latest", family="")],
    )
    assert client.get("/api/config/ollama-models").json()["embedding_only"] == []


def test_embedding_detection_reads_the_families_list_too(monkeypatch):
    """Ollama reports both `family` and `families`; either may carry it."""
    import src.backend.brain as brain

    assert brain._is_embedding_only(
        {"name": "x", "details": {"families": ["bert"]}}
    ) is True
    assert brain._is_embedding_only({"name": "x", "details": {}}) is False
    assert brain._is_embedding_only({"name": "x"}) is False


def test_an_unreachable_ollama_reports_no_embedding_models(monkeypatch):
    got = models_client(monkeypatch, None).get("/api/config/ollama-models").json()
    assert got["reachable"] is False
    assert got["embedding_only"] == []


# --- The shipped default ----------------------------------------------------
#
# OLLAMA_MODEL used to default to the literal "llama3.2". It now prefers
# qwen2.5, and the risk was never the model but the upgrade path: a user who
# never saved a model in Settings, with llama3.2 pulled and working, must not
# wake up configured for a 4.7GB model they do not have. So an unnamed model
# settles on the first preference that is actually installed.


@pytest.fixture
def unset_model(monkeypatch):
    """OLLAMA_MODEL as config computes it when nobody named one."""
    from src.backend import config

    monkeypatch.setattr(config, "OLLAMA_MODEL_EXPLICIT", False)
    for module in (config, brain):
        monkeypatch.setattr(module, "OLLAMA_MODEL", config.OLLAMA_MODEL_PREFERENCE[0])


@pytest.mark.parametrize(
    "installed,expected",
    [
        (["llama3.2:latest"], "llama3.2:latest"),   # the upgrade path: keep what works
        (["llama3.2:latest", "qwen2.5:latest"], "qwen2.5:latest"),
        (["llama3.2:latest", "llama3.1:latest"], "llama3.1:latest"),  # our order, not Ollama's
        (["llama3:latest", "all-minilm:latest"], "qwen2.5"),  # none preferred: say what to pull
        ([], "qwen2.5"),
        (None, "qwen2.5"),                          # unreachable
    ],
)
def test_an_unnamed_model_settles_on_the_best_one_installed(
    monkeypatch, unset_model, installed, expected
):
    from src.backend import config

    if installed is None:
        unreachable(monkeypatch)
    else:
        install_tags(monkeypatch, installed)

    brain.settle_default_model_at_startup()

    assert brain.OLLAMA_MODEL == expected
    assert config.OLLAMA_MODEL == expected   # the copy Settings reads


def test_a_named_model_wins_verbatim(monkeypatch):
    """Even one that is not installed, while a preferred one is.

    Being told `ollama pull llama3.1` is the user's configuration talking;
    quietly answering with a different model would be Lithe overruling it.
    """
    monkeypatch.setattr(brain, "OLLAMA_MODEL", "llama3.1")   # explicit, via conftest
    install_tags(monkeypatch, ["qwen2.5:latest", "llama3.2:latest"])

    brain.settle_default_model_at_startup()

    assert brain.OLLAMA_MODEL == "llama3.1"
    assert brain._check_ollama_available() is False


def test_a_default_settled_while_ollama_was_down_recovers(monkeypatch, unset_model):
    """Ollama is often started after Lithe.

    Resolving once at boot would leave this machine -- llama3.2 pulled and
    working -- telling the user to pull qwen2.5 for the whole session.
    """
    from tests.support.fake_ollama import ScriptedOllama

    unreachable(monkeypatch)
    brain.settle_default_model_at_startup()
    assert brain.OLLAMA_MODEL == "qwen2.5"

    ollama = ScriptedOllama(model="llama3.2").install(monkeypatch)
    reply = brain._ollama_chat("system", "hello", tool_map={})

    assert reply == "Done."
    assert ollama.requests[0]["model"] == "llama3.2:latest"


def test_the_listing_reports_the_settled_default(monkeypatch, unset_model):
    """Settings must show the model the fallback will use, not the preference.

    Returned in Ollama's spelling so the picker finds it among the installed
    tags instead of opening on "custom".
    """
    client = models_client(
        monkeypatch, ["llama3.2:latest", "all-minilm:latest"], current="qwen2.5"
    )
    got = client.get("/api/config/ollama-models").json()

    assert got["current"] == "llama3.2:latest"
    assert got["current"] in got["installed"]
    assert got["current_installed"] is True


def test_saving_a_model_in_settings_pins_it(tmp_path, monkeypatch, unset_model):
    """And saving anything else does not.

    A saved model is in the .env, so it would be explicit after a restart
    anyway; treating it as still-unnamed until then would let the next
    /api/tags read quietly undo the user's choice.
    """
    from fastapi.testclient import TestClient
    from src.backend import config
    from src.backend.server import app

    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(config, "_ACTIVE_ENV_PATH", env_file)
    monkeypatch.setattr(config, "OLLAMA_TIMEOUT", 150)
    monkeypatch.setattr(brain, "OLLAMA_TIMEOUT", 150)
    monkeypatch.setattr(config, "NEEDS_ONBOARDING", config.NEEDS_ONBOARDING)
    client = TestClient(app)

    client.post("/api/config/llm", json={"ollama_timeout": 200})
    assert config.OLLAMA_MODEL_EXPLICIT is False
    assert "OLLAMA_MODEL" not in env_file.read_text()

    client.post("/api/config/llm", json={"ollama_model": "llama3.2"})
    assert config.OLLAMA_MODEL_EXPLICIT is True

    install_tags(monkeypatch, ["qwen2.5:latest", "llama3.2:latest"])
    brain.settle_default_model_at_startup()
    assert brain.OLLAMA_MODEL == "llama3.2"
