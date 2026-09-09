> **ARCHIVED — completed 2026-09-08.** Every part of this plan shipped.
>
> Outcome: the multi-step `known_gap` attribution was half wrong. `multistep-find-then-read`
> is genuinely the model's limit (qwen2.5 3/3, llama3.2 0/3), while
> `multistep-profile-then-chart` had never been a gap at all — the recorder was
> under-reporting executed tool calls. Merged in PRs #17 and #18.
>
> Full write-up in [`docs/agent-logs/INDEX.md`](../agent-logs/INDEX.md).
> The plan that superseded this one is [`plan.md`](../../plan.md) at the repo root.


# Stronger local model + an Ollama model selector

## Context

Two capability cases are marked `known_gap` in `tests/eval/cases.py` and blamed on
the model rather than on Lithe:

- `multistep-find-then-read`
- `multistep-profile-then-chart`

The stated reason is that llama3.2 runs `search_files`, gets a path back, then
answers that it "cannot read files" — with `read_file` in the schema it was just
handed. Lithe's own chaining is pinned by `tests/test_ollama_path.py`, so the
reasoning is sound, **but it has never been tested against a different model.**

That matters in both directions. If a stronger model closes the gaps, the
attribution is confirmed and two gaps close. If it does not, the attribution is
wrong, the `known_gap` markers are hiding a real Lithe defect, and the fix is
ours. Right now the codebase asserts an answer it has not measured — the same
posture that produced the 79/86/64 scorecard episode.

While we are here, the model is only changeable by typing a name into a free-text
box (`SettingsPanel.tsx:62-68`). Typing a model that is not pulled reproduces
exactly the failure that left the fallback silently dead for weeks. Shawn asked
for a real selector, so this plan adds one.

Scope decisions already made: **Ollama models only** (Gemini stays the primary
engine), and **select-installed plus custom text** (no pull-from-UI).

---

## Part 0 — Move the Ollama model store to D: — DONE 2026-09-08 (old C: store awaiting Shawn's delete)

`C:` is at 96% (22 GB free) and `~/.ollama/models` is 6.3 GB. qwen2.5 is ~4.7 GB.
D: has 201 GB.

1. Quit Ollama fully (tray → Quit; confirm `ollama.exe`, `ollama app.exe` and
   `llama-server.exe` are gone).
2. Create `D:\ollama\models` and move the contents of
   `C:\Users\SHAWN\.ollama\models` into it.
3. Set the user-level env var `OLLAMA_MODELS=D:\ollama\models`.
4. Restart Ollama and confirm `GET /api/tags` still lists `llama3.2:latest`,
   `llama3:latest`, `all-minilm:latest`. **Do not delete the old directory until
   this check passes.**
5. `ollama pull qwen2.5` — it lands on D:.

Only after step 4 succeeds does anything else in this plan run.

---

## Part 1 — Answer the question — COMPLETE

### 1a. Stamp the scorecard with its model and seed (prerequisite) — DONE 2026-09-07

`tests/eval/scorecard.py:render()` prints only `engine: ollama`. Two runs on
different models are indistinguishable in scrollback, which this comparison
cannot tolerate — and a mislabelled scorecard is how the last measurement
confusion started.

- `render(write, engine, aborted)` gains `model` and `seed`, printed in the header.
- `tests/eval/conftest.py:pytest_terminal_summary` passes `brain.OLLAMA_MODEL`
  (or `config.GEMINI_MODEL` when `ENGINE == "gemini"`) and `EVAL_SEED`.

### 1b. Add an opt-in trace — DONE 2026-09-08

If the gaps *don't* close, a one-line failure reason tells us nothing new. The
harness already builds the full picture in `outcome` (tool calls, tool results,
chart, final text) and then throws all but `failures[0]` away.

- `LITHE_EVAL_TRACE=1` writes each case's outcome as JSON lines to a file.
- Off by default; no effect on scoring. It is a diagnostic, not an assertion.

### 1c. Run it — DONE 2026-09-08

The model is chosen by env var — `load_dotenv` uses `override=False`, so a
shell-set `OLLAMA_MODEL` beats the AppData `.env` **without touching Shawn's
config** (verified this session).

```
# fast: the two cases in question, ~2 min
OLLAMA_MODEL=qwen2.5 LITHE_EVAL=1 LITHE_EVAL_TRACE=1 python -m pytest -m eval -k multistep -q

# then the full comparable scorecard, ~10-15 min at 7B
OLLAMA_MODEL=qwen2.5 LITHE_EVAL=1 python -m pytest -m eval -q
```

Re-run the llama3.2 baseline too if the harness changed, so both scorecards come
from the same code.

### 1d. Record the finding honestly — DONE 2026-09-08 (both branches fired: one gap confirmed, one was never a gap)

**A cross-model score is not the same measurement as a cross-branch score.**
`docs/TESTING.md` is emphatic that the number's job is the delta between branches
on one engine. A qwen2.5 number vs an llama3.2 number says something about the
models, not about Lithe's capability changing. Whatever is written down must say
so.

- **Gaps close** → attribution confirmed. Update the `known_gap` comments in
  `cases.py` to name the model where they close, rather than the vague "a
  stronger local model". Whether to change the shipped default is a *separate*
  decision with real cost (4.7 GB and 7B inference vs 2 GB and 3B) — raise it,
  do not fold it in.
- **Gaps do not close** → the attribution is wrong. Remove `known_gap`, use the
  trace to find where the chain actually breaks, and treat it as a Lithe defect.

---

## Part 2 — Ollama model selector — DONE 2026-09-08 (verified in the running app)

### Backend

New `GET /api/config/ollama-models` in `src/backend/server.py`, next to the
existing `/api/config/llm` pair (line 340). Reuses what already exists:

- `brain._ollama_models()` — installed tags, or `None` when Ollama is unreachable
- `brain._model_is_pulled()` — handles `qwen2.5` matching `qwen2.5:latest`

Returns `{reachable, installed, current, current_installed}`. **`reachable:false`
must stay distinct from `installed: []`** — "Ollama is down" and "Ollama is up
with nothing pulled" are different problems, and collapsing them is precisely the
bug that made the fallback look fine while it was dead.

No changes needed to `POST /api/config/llm`: it already persists via
`config.update_llm_config()` *and* rebinds `brain.OLLAMA_MODEL` live
(`server.py:369`), because brain imports it by value.

### Frontend

- `src/frontend/src/preload/index.ts` — add `getOllamaModels()`, following the
  `getLlmConfig` pattern at line 158.
- `src/frontend/src/renderer/src/env.d.ts` — add the matching type (line 34).
- `SettingsPanel.tsx` — replace the free-text model input with a `<select>` of
  installed models plus a `Custom…` option that reveals the existing text input,
  so remote instances and not-yet-pulled tags stay reachable. Show a warning when
  the selected model is not installed, naming what is.
- Move `TOOL_CAPABLE_OLLAMA_MODELS` out of `SystemPanel.tsx` into a shared module
  so the selector can flag a model that lacks native tool calling, and the badge
  and the picker cannot drift apart. A hand-maintained second copy of that list
  is the same shape as the declared-vs-dispatched tool-name bug.

### Tests

- `tests/test_fallback.py` — endpoint tests with `TestClient(app)` (pattern:
  `tests/test_memory.py:130`), monkeypatching `brain._ollama_models` to cover
  installed / not-installed / unreachable. That file already owns
  `_model_is_pulled` and readiness.
- `npm run typecheck` for the renderer; there is no frontend test runner.

---

## Verification

1. `python -m pytest -q` — currently 170 passed, 1 xfailed. Must not regress.
2. New endpoint tests fail against the current source before they pass.
3. `cd src/frontend && npm run typecheck` clean.
4. `cd src/frontend && npm run dev` — Electron spawns the backend itself. In
   Settings: the dropdown lists the installed models, selecting qwen2.5 saves,
   and the change takes effect **without a restart** (assert `brain.OLLAMA_MODEL`
   moved, not just the `.env`). Selecting a non-installed custom name warns.
5. Both scorecards carry their model and seed in the header.

## Out of scope

Pull-from-UI, a primary-engine switch, other providers, and changing the shipped
default model — the last only after Part 1 reports.