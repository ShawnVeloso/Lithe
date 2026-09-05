# Lithe — Testing & Evaluation

Two separate things live in `tests/`:

| | Unit + contract suite | Capability evaluation |
|---|---|---|
| Command | `python -m pytest` | `LITHE_EVAL=1 python -m pytest -m eval` |
| Speed | seconds | minutes |
| Network | none (blocked) | real LLM calls (local Ollama by default) |
| Cost | free | free on Ollama; consumes quota on Gemini |
| Answers | "does the harness work?" | "does Lithe give good answers?" |

The first is a correctness gate and should always be green. The second is a
measuring instrument and is *expected* to be imperfect.

## Running the normal suite

```
python -m pytest          # or just `pytest`
```

`pytest.ini` sets `pythonpath = .` so both invocations work. Before it existed
only `python -m pytest` from the repo root did, because `src.backend` imports
failed otherwise.

`testpaths = tests` keeps collection out of the repo root, which contains
`test_gemini.py` — a manual live-API diagnostic with no assertions that would
otherwise be imported on every run.

### Reading the output

A normal run ends with a list of `XFAIL` lines. Those are **known defects,
deliberately unfixed**, each recorded as a test rather than a comment:

```
XFAIL tests/test_tool_contract.py::test_declared_tool_names_match_dispatch_map
  - B2: closures are named *_wrapper, so the SDK declares profile_data_wrapper
    while tool_map is keyed profile_data
```

They are marked `xfail(strict=True)`, so when a fix lands the test XPASSes and
the run turns **red** until the marker is removed. A defect cannot be quietly
fixed without the suite noticing, and cannot be quietly forgotten either.

## Test layers

**`tests/test_tool_contract.py`** — drives the real `brain.chat()` with a
scripted LLM (`tests/support/fake_gemini.py`). This is where agent-loop
behaviour is pinned down: which tools are declared, whether dispatch reaches
them, and the mutating-tool confirmation handshake.

The scripted client returns genuine `google.genai.types` objects rather than
`MagicMock`s, because `response.function_calls` and `response.text` are
computed properties over `candidates[0].content.parts`. A mock would satisfy
the test while the real plumbing was broken.

One subtlety worth preserving: tests that script a tool call resolve the name
through `_as_the_model_would_call_it()`. A model can only call a tool by the
name it was *given*, so scripting the name we wish were declared would bypass
the exact mismatch the test exists to catch.

**`tests/test_retrieval.py`** — the measured ceiling of file-context injection.
Several tests assert current limitations rather than desired behaviour (no
content search, head-only truncation, every basename collision injected). They
are labelled as such and will need updating when content indexing lands.

**`tests/test_safeword.py`** — the persona override, which had no coverage at
any level despite being the main behavioural switch.

**`tests/test_eval_scoring.py`** — the measuring instrument, tested like any
other code. Each test pins one scenario the previous scorer called a pass: the
guard ERROR, the undelivered chart, the undispatchable tool. These run in the
normal suite on purpose, so a mistake in the scorer surfaces on every run
rather than only when someone opts into a live evaluation.

**`tests/conftest.py`** — shared fixtures. Two are autouse for safety:
`reset_brain_state` (brain keeps the session in module globals, so a leftover
pending tool proposal would otherwise change the next test's result) and
`no_real_network` (stops a unit test passing because a real Ollama happened to
be running locally).

Note that importing `src.backend.brain` runs `_load_history()` at module scope,
which reads `DB_PATH`. That is why `isolated_db` patches both `memory.DB_PATH`
and `config.DB_PATH`.

## The capability evaluation

```
LITHE_EVAL=1 python -m pytest -m eval                          # scores Ollama
LITHE_EVAL=1 LITHE_EVAL_REPEATS=1 python -m pytest -m eval     # quicker, noisier
LITHE_EVAL=1 LITHE_EVAL_ENGINE=gemini python -m pytest -m eval # needs a paid key
```

Requires `LITHE_EVAL=1`; otherwise every case skips. `addopts = -m "not eval"`
keeps it out of normal runs entirely.

### Which engine gets scored

`LITHE_EVAL_ENGINE` picks it and **defaults to `ollama`**.

Gemini's free tier allows **20 `generate_content` requests per day per model**.
One pass of this suite needs roughly **80–100** — `cases × repeats`, and a tool
case costs several calls apiece. A free key therefore cannot complete a run no
matter how long you wait for a reset. Three attempts established that the
expensive way; the last ground for 67 minutes and reported a score composed
entirely of fallbacks.

Ollama is local, free and repeatable, which is what a measuring instrument
needs. Scoring it also covers something that was never measured before: on a
free Gemini key exhausted after 20 requests, the fallback path is where users
spend much of their day.

`LITHE_EVAL_ENGINE=ollama` does *not* call `_ollama_chat` directly. It installs
a Gemini client that raises `ConnectError`, so `brain.chat()` takes exactly the
path a user gets during an outage — including the fact that the Ollama branch
has no agent loop and sends no history, which is why the multi-step cases
cannot pass there. Scores are only comparable **between runs of the same
engine**; the scorecard header names which one produced them.

### Pre-flight and the abort guard

Before collection the harness checks the chosen engine can actually serve:
Ollama must be running *and* have `OLLAMA_MODEL` pulled; Gemini gets one cheap
call. A failure skips the suite in seconds with the reason, instead of a
nine-minute run burning fifty unusable calls.

Passing pre-flight is not a promise the run will finish — it proves one request
is allowed, not the ~80–100 a full pass needs. So the Gemini path also aborts
mid-run: the first `RESOURCE_EXHAUSTED` sets a flag, every remaining case skips
with that reason, and the scorecard is stamped `PARTIAL RUN`. A quota wall is
not a capability result and must never be scored as one.

Use `LITHE_EVAL_REPEATS=1` while iterating, and save the 3-repeat run for an
actual before/after comparison.

### Why runs are seeded

The scorecard exists to be compared between branches, which requires that two
runs of the *same* code agree. They did not. Three runs of one commit scored
**86% -> 64% -> 86%**, and the requests were later proved byte-identical by
hashing the outgoing `/api/chat` payload on both commits — so the swing was
sampling, and noise was indistinguishable from a regression.

The Gemini path pins `temperature=0.7`; the Ollama payload set no options at
all, so the model's own default sampling applied. `brain.OLLAMA_OPTIONS` is
empty in production — shipped behaviour is unchanged — and the evaluation sets
`seed = LITHE_EVAL_SEED + repeat`. The same payload with the same seed gives the
same output, so runs are comparable, while the seed still varies per repeat so
the repeats sample different outputs instead of producing one answer three
times.

Change `LITHE_EVAL_SEED` to resample the whole suite deliberately rather than by
accident. A seeded score is a fixed sample of model behaviour, not an average
of it: treat a one- or two-case move as within the sample, and prefer a
mechanical explanation (diff the payload) over assuming a real regression.

### The corpus

It runs against a **synthetic corpus** built in a temp directory
(`tests/eval/conftest.py::corpus`), never your real drive — a score is only
comparable between runs if the inputs are identical. The corpus contains a CSV
with known columns and row count, a markdown file whose *body* holds the token
`ZEPHYR-441` (not its filename), an over-100KB file with a marker only in its
tail, and a binary.

Cases live in `tests/eval/cases.py` as plain dicts. Scoring is structural —
tool name, an argument predicate, substring presence or absence. There is
deliberately **no LLM judge**: it would add nondeterminism and cost without
sharpening assertions that are already this concrete.

Each case runs `LITHE_EVAL_REPEATS` times (default 3) because model output
varies. A majority passes the case; a minority reports it flaky.

### Two things the harness does on purpose

**Engine integrity check.** If a case runs on an engine other than the one
being scored, it is recorded as a failure with an explicit reason rather than
as a capability result. `brain.chat()` reroutes to Ollama on a transport error,
so without this a Gemini 503 would silently be scored as the model giving a bad
answer.

**Transport retries.** Gemini returns 503 "high demand" often enough to distort
a score. `EvalHarness.ask()` detects the wrong engine and retries with backoff,
so transport noise is not counted against capability. A 429 is deliberately
*not* retried — the quota is gone for the day, so the run aborts instead.

**Tool-call recording.** `brain.chat()` returns only final text, so the harness
wraps the client to capture which tool was chosen — that is most of what is
being measured. Gemini is recorded by wrapping the client object; Ollama is
spoken to with a bare `httpx.post`, so that is wrapped instead. Neither
requires production code to cooperate: an evaluation that needed `brain.py` to
know it was being tested would be measuring something other than what ships.

**Tool-result recording.** The recorders also capture what each tool
*returned*, harvested from the next outgoing request — Gemini's
`function_response` parts, Ollama's `role: "tool"` messages. Both engines
always send the results back to the model, so nothing has to be read out of
production code to see them. This closes a blind spot described below.

## What a run is judged on

`tests/eval/scoring.py` holds the rules, kept out of the test module so the
normal suite can exercise them (`tests/test_eval_scoring.py`). That separation
was earned: **the scorecard has twice reported a pass over a real defect, and
both times the fault was in the scoring rules rather than in Lithe.**

Both misses have one shape. A case asserted that a tool was *called* and
stopped there, so everything after the tool returned was invisible:

- `select-search` passed while the hallucination guard was replacing correct
  answers with *"ERROR: The LLM generated a narrative claiming to have searched
  for files…"*. The tool ran; the user got an error message.
- `select-chart` passed while charts were generated and then dropped on the
  Ollama path. The tool ran; the image reached nobody.

Calling a tool is not the capability. The user receiving its result is. So
scoring now runs in three layers.

**1. Invariants**, applied to every case whether it asks for them or not —
because the next case someone writes should not have to remember them:

| Invariant | Catches |
|-----------|---------|
| The answer is not one of Lithe's own failure strings (`LITHE_FAILURE_TEXT`) | The hallucination guard destroying a correct answer; `chat()`'s internal-error branch; an empty Ollama reply |
| No tool result is `Error: Tool X not recognized.` | Lithe declaring a tool under one name and dispatching another — the exact defect that left 5 of 9 tools unreachable on Gemini, and which every affected case scored as the *model* choosing badly |
| The run stayed on the engine being scored | A transport failure rerouting to Ollama mid-case |

**2. Call-level** — `expect_tool`, `args_predicate`, `expect_all_tools`,
`expect_no_tool`. Unchanged.

**3. Result-level** — new, and where a case should reach first:

| Field | Asserts |
|-------|---------|
| `result_must_contain` | The tool did its job: substrings required in what the tools returned |
| `must_contain` | The user was told: substrings required in the final answer |
| `expect_chart` | An actual `data:image` URI reached the caller, not the model's word that one was sent |

`result_must_contain` and `must_contain` are most useful as a pair. When only
one fails, the failure detail says which half broke — a tool that returned
nothing useful, or an answer that dropped a result which was fine.

### Reading the scorecard

```
  tool selection         5/6
      fail   select-chart: expected tool inline_chart, got []
  CAPABILITY SCORE: 71%  (14 scored cases)
  Known gaps (excluded from the score):
      retrieval-by-content         still failing
```

**The absolute percentage is close to meaningless** — it is a function of which
cases someone chose to write. Do not quote it as a fact about Lithe. Its only
job is the **delta**: run it before a change and after, and see which cases
moved.

Cases marked `known_gap` are documented limitations (no content index, no
multi-step tool chaining). They are excluded from the score and reported
separately, so they show up as capability that is missing rather than as a
regression. When one flips to "now passing", that gap has been closed.

### Adding a case

Append a dict to `CASES` in `tests/eval/cases.py`. Prefer assertions that can
only pass for the right reason: check that a chart's `x_column` is a real
column in the corpus rather than that a chart was produced at all. Include
negative cases — `no-tool-arithmetic` checks that Lithe does *not* reach for
the filesystem to do arithmetic, and over-calling is as damaging as
under-calling.

**`expect_tool` on its own is the weakest useful assertion there is.** It
passes the moment the model names the right tool. Reach for a result-level
field as well, and prefer one whose substring can only appear if the work
actually happened: `"--- DATA PROFILE:"` is emitted by a successful
`profile_data` and by none of its error paths, so it distinguishes a profile
from a call that was merely made.
