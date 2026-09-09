> **STATUS — updated 2026-09-09.** Branch `feat/search-parity-and-safety`.
> Suite 241 passing, 1 xfailed. Baseline 81% (16 cases, llama3.2, seed 20260905).
>
> | Phase | State | Landed as |
> |---|---|---|
> | 0 — payload golden | **done** | `c4674e4` |
> | 1 — search parity (watcher, `/api/search`, IndexPanel) | **done** | `61c40bb` |
> | 2 — PDF + DOCX extraction | next | — |
> | 3 — Ollama timeout + streaming | todo | — |
> | 4 — frontend pass | todo | — |
> | M1 — safety, prompts, `list_directory` | todo | *first eval run* |
> | M2 — qwen2.5 default | todo | *second eval run* |
> | 7 — packaging | todo | *must be last* |
>
> Finished plans are archived in [`docs/plans/`](docs/plans/).

# Lithe — the whole approved backlog, sequenced

## Context

Yesterday's work closed the last capability gap that was Lithe's own fault (FTS5 content
search) and left a spread of loose ends: a feature only half-wired, two failing eval cases,
a safety hole under the safeword, a UI that has accreted, and an installer six passes out of
date. Shawn approved all of it. This plan sequences it.

**The scarce resource is the evaluation, not the code.** Measured yesterday: lengthening the
`search_files` description dropped the score 80% → 69% and tool selection 4/6 → 2/6, because
llama3.2 degraded into emitting tool calls as plain text. Tightening it recovered 4/6. So any
change to prompt text, tool descriptions, the tool set, or the model **resamples the entire
suite** and costs a ~11 minute run (~25–40 min once qwen2.5 ships). Everything below is
ordered to produce **exactly two measurement points**.

Two corrections to what was assumed when this was scoped:

- **`system_prompt.py:43` is now false.** It tells the model "`search_files` matches FILENAMES
  only — it cannot see inside files," which stopped being true when FTS5 shipped. The tool
  description and the prompt now contradict each other. This is a live defect, not a polish item.
- **`python-docx` is not pure-Python** — it pulls in `lxml`, a compiled extension. DOCX is read
  here with stdlib `zipfile` + `ElementTree` instead. The only new dependency is `pypdf`.

### What resamples the eval

| Resamples | Does not |
|---|---|
| Either system prompt's text | `/api/search`, all frontend work |
| `OLLAMA_TOOLS_SCHEMA` / tool docstrings | `watcher.py` (eval indexes via `walk_and_index`) |
| The *string* `search_files` returns | PDF/DOCX (the corpus has neither) |
| Adding or removing a tool | `OLLAMA_TIMEOUT` (an httpx arg, not payload) |
| `OLLAMA_MODEL`, the corpus, `OLLAMA_OPTIONS` | Ollama streaming **iff** confined to `chat_stream` |

The eval drives `brain.chat()` (`tests/eval/conftest.py:376`), never `chat_stream` — verified.
That keeps the riskiest item out of the measured batch.

---

## Phase 0 — Make "eval-affecting" machine-checkable

Rule-by-tribal-knowledge is how the prompt drifted out of sync with the tool in the first place.

- New `tests/test_prompt_payload.py`: drive one turn down the Ollama path (reuse `UnavailableClient`
  and the `httpx.post` monkeypatch from `tests/eval/conftest.py:188`/`:269`), capture the outgoing
  `/api/chat` payload, assert the system prompt and `tools` schema against **literal** goldens (not
  hashes — the diff must be readable). Assert `stream is False` and no `options` key.
- A second test that monkeypatches the prompt and asserts the golden **fails**, so the guard isn't a
  tautology.
- `docs/TESTING.md`: the table above, plus the rule that changing the golden requires a fresh eval
  run and a recorded score.

---

## Phase 1 — Search parity (no eval run)

**1.1 Watcher.** `src/backend/watcher.py:127-142` builds its own record and calls `upsert_files`
directly, so a file created or edited while Lithe runs is name-only searchable until restart. Call
`indexer.index_file_content(path, ext)` after the upsert. Lowercase `ext` once at `:130` — it is only
lowercased inside the dict literal today, and `CONTENT_INDEXED_EXTENSIONS` is a lowercase set, so
`.MD` would be skipped. Deletes already clear content (`memory.delete_file_by_path`).

**1.2 One merge, two callers.** `/api/search` (`server.py:476`) still calls `search_files_by_name`
only. Do **not** copy the merge from `brain.search_files` — duplication of exactly this kind produced
the `*_wrapper` dispatch bug. Extract the row merge (not the formatting) into
`memory.search_index(keyword, limit=20)`; `brain.search_files` keeps its rendering byte-for-byte, and
the endpoint returns rows. Add `match: "name" | "content"` per row for the UI badge.

**1.3 IndexPanel.** Render the excerpt as a dimmed third line with a `[in file]` tag; `key={i}` →
`key={res.path}` (`IndexPanel.tsx:171`); move the inline `maxHeight: 150px` (`:170`) into `index.css`
now that rows vary in height; add the missing empty state. Update `env.d.ts` + preload types.

*Guard:* a golden test on `brain.search_files`'s returned **string**. That string is model payload;
this is what stops a refactor here from silently resampling the eval.

---

## Phase 2 — PDF + DOCX (no eval run)

**The hazard is where extraction runs, not the parsing.** `server.py:43-57` runs `walk_and_index()`
**then** `start_watcher()` on one thread. Add PDF parsing inline and a drive with 3,000 PDFs turns a
40-second walk into 20 minutes — during which every file change is silently lost, because the watcher
does not exist yet.

**Design: binary extraction is a deferred third pass.**
`walk_and_index()` → `start_watcher()` → `backfill_binary_content()`, the last reusing
`memory.paths_missing_content` (already batched, already written for this shape) filtered to binary
extensions, broadcasting progress via `broadcaster.broadcast_event`. The index is usable immediately;
PDFs fill in behind it. The watcher handles a single new PDF inline — bounded, and anything it misses
is caught by the next startup's backfill.

- New `src/backend/extractors.py`: `extract_text(path, ext, max_bytes) -> str | None`. Never raises.
- `config.py`: `BINARY_CONTENT_EXTENSIONS = {".pdf", ".docx"}` kept **separate** from
  `CONTENT_INDEXED_EXTENSIONS`, whose contract is "open UTF-8 strict and read". Plus
  `BINARY_CONTENT_MAX_FILE_BYTES = 25MB`, `PDF_MAX_PAGES = 50`, `EXTRACT_TIME_BUDGET_SECONDS = 10`.
- **`indexer.py:68`'s `except (UnicodeDecodeError, OSError, ValueError)` must widen to `Exception`
  for the extractor branch.** pypdf raises `PdfReadError`, `RecursionError`, `struct.error` and more;
  the function's "never raises" docstring is currently a promise it would break on one malformed PDF.
- PDF guards, all load-bearing: `is_encrypted` → try `decrypt("")` first (many PDFs are "encrypted"
  with an empty owner password); stop at page cap, byte cap, or wall-clock budget; size pre-check
  before opening. **No per-file `_run_with_timeout`** — thread-per-file across a whole drive, and a
  hung parse leaks an undead daemon thread each time. Caps, not timeouts.
- DOCX via stdlib `zipfile` + `ElementTree` over `word/document.xml` (`<w:t>` nodes). No lxml.
- **Knock-on:** PDFs entering the index means `search_files` returns them, and the model will then
  call `read_file`, which answers *"is not a UTF-8 text file"* (`tools.py:305`). Route `execute_read`
  through the same extractor and fix that message. Eval-neutral — no case reads a PDF.
- Fixtures generated in code, not committed as binaries (a minimal PDF is ~500 bytes of literal text;
  a `.docx` is three lines of `zipfile`).

---

## Phase 3 — Ollama timeout and streaming (no eval run)

**3.1 Live timeout.** `brain.py:23` imports `OLLAMA_TIMEOUT` by value, but every read is inside a
function body (`:557`, `:730`), so rebinding `brain.OLLAMA_TIMEOUT` takes effect next request — no
refactor. Follow the existing pattern: `update_llm_config(..., ollama_timeout: int = 0)` where `0`
means unchanged (mirroring the blank-string convention), clamped to `[5, 600]`; `LLMConfigRequest`
gains the field; `set_llm_config` rebinds alongside the URL/model rebinds at `server.py:366-370`.
Settings gets a numeric field. *Test:* assert the **next outgoing request** carries it, not just that
the global moved.

**3.2 Streaming, confined to `chat_stream`.** The tool loop reads `resp.json()["message"]`, and so
does `OllamaRecorder._harvest` in the eval harness — with NDJSON both raise, which would silently
zero every tool case. That is this project's characteristic failure and must not recur.

One transport function, two modes: `_ollama_post(payload, on_token=None) -> dict`, returning the same
`message` dict either way. `on_token is None` → today's blocking path, byte-identical.
`_ollama_drive_tool_rounds` gains a pass-through `on_token`; everything downstream is unchanged.
`chat()` passes nothing, so the eval payload is untouched. `chat_stream`'s fallback (`brain.py:1550`)
runs it on a worker thread feeding a `queue.Queue` and drains that, replacing the single-chunk dump at
`:1573`. **Buffer one chunk before forwarding** so a turn that turns out to be a tool call never emits
half a sentence first.

*Tests:* `chat()` still posts `"stream": False` (the payload guard, most important test here);
`chat_stream` yields >1 token event for a 5-chunk fake; a first chunk carrying `tool_calls` yields a
proposal and **zero** tokens; a stream ending mid-line does not raise.

---

## Phase 4 — Frontend (no eval run)

**4.1 Defects first.** Duplicate `<span className="system-separator" />` (`SystemPanel.tsx:217-219`);
`var(--bg-panel)`/`var(--bg-main)` are undefined (`:322,341`) — the real tokens are `--panel`/`--bg`;
the health-check effect depends on `messages.length` (`App.tsx:169`) so a 10s interval is destroyed
and rebuilt on every message — split the interval from the history hydration.

**4.2 Token budget.** `App.tsx:278` discards the `done` event's `tokens`. Keep it in state and pass to
`SystemPanel`, taking precedence over the 5s poll — same data, immediate instead of stale. Render as a
bar against the budget, not a bare number. Note `TOKEN_BUDGET_WARNING` is cumulative-session while
`context_budget.py` governs per-turn trimming; do not conflate them in the label.

**4.3 Split `SystemPanel`** (356 lines, ~8 jobs) into `system/StatusChips`, `TokenBudget`, `LogDrawer`,
`SystemActions`, `AuditExport`, `UndoHistory`, leaving a thin composition root. **Move `SettingsPanel`
mounting to `App.tsx`** — it renders a full-viewport overlay from inside a fixed bottom strip, which is
a stacking-context bug waiting to happen.

**4.4 Settings design pass.** Two labelled sections, **Cloud (Gemini)** / **Local (Ollama)**, since the
mental model is primary-vs-fallback. Model status becomes a status line with an icon rather than prose;
the four-case notice logic (`SettingsPanel.tsx:100-113`) is correct and should be re-presented, not
rewritten. Make the dropdown always render with `custom…` revealing the input below it, rather than two
sibling conditionals that can both hide. Add `[TEST CONNECTION]` hitting `/api/config/ollama-models`.

**4.5 Undo — backend bug first.** `memory.get_action_history` (`memory.py:484`) has `limit=5` and **no
tool filter**, while `record_action` is called for `search_files` and `read_file` too — so "undo last"
is routinely looking at a search. Add `mutating_only: bool = True` and a `limit` query param. *Test:*
record a search then a delete; the endpoint's first row is the delete (fails today). Then a popover
listing the last ~10 mutating actions with per-row `[undo]`, replacing all three `alert()` calls.

**4.6 Charts.** `MessageBubble.tsx:39` is a bare `<img>` with no affordance. Wrap in `<figure>` with a
hover toolbar: expand (modal reusing `.command-palette-overlay`, Esc bound), save (the `<a download>`
pattern already in `SystemPanel.tsx:62-89`), copy via `navigator.clipboard`.

*Constraint:* `index.css` is one 1359-line global file, BEM-ish, flexbox-only. Six new components will
tempt a CSS-modules migration mid-phase. Don't — a half-migrated stylesheet is worse than a whole one.

---

## ⏱ M1 — Safety, prompts, `list_directory` — llama3.2, seed 20260905

The last measurement comparable to the 81% baseline.

**5.1 Shared guardrails.** Extract `SAFETY_RULES` (whole-drive refusal + read-only default) and
interpolate it into **both** prompts. Today `COMPLIANT_SYSTEM_PROMPT` drops both, while the candid
prompt tells the user the safeword is how to escalate past permission errors — so "Override Lithe,
scan my whole C: drive" hits no instruction at all. The safeword overrides persona, not safety; say so
in one explicit sentence.

**5.2 Prompt corrections.** Fix the false FILENAMES-only line (§Context). Add one sentence licensing
direct answers: *"Answer general programming and factual questions from your own knowledge. Use tools
only when the request concerns the user's own files."* — nothing in the prompt currently permits
answering without a tool, which is why `no-tool-general` fails.

**Budget discipline: net prompt length ≤ today's.** The Constraints section is 8 bullets and is where
llama3.2 degrades. Merge `:45` into `:48` (overlapping) and `:47` into `SAFETY_RULES`. Adding two lines
while deleting none is precisely yesterday's failure. State the constraint in the commit message.

**5.3 Refuse in code, not only in words.** The prompt already says "STRICTLY REFUSE" and llama3.2
proposes `delete_file(path="C:\")` regardless; `_validate_path` is a post-hoc backstop that fires only
*after* the user sees an alarming DELETE card. Add a **pre-proposal gate**: before building a proposal,
run path args through `tools._validate_path`; on the root or `PROTECTED_EXACT` refusal, don't propose —
append the error as the tool result and continue the loop, so the model explains it in text. Scope
narrowly to those two tiers; an ordinary delete must still be proposed.

**5.4 `list_directory`.** `execute_list_directory(path)` in `tools.py`: `_validate_path` first (which
buys the drive-root refusal for free), non-recursive, `MAX_LIST_ENTRIES = 100`, reuse
`indexer.EXCLUDED_DIRS`, wrap in `_run_with_timeout` (a single call — appropriate here, unlike the
walk). Wire into `_build_tool_functions`, `OLLAMA_TOOLS_SCHEMA`, and `EXPECTED_TOOL_NAMES`; the
contract tests fail until all three agree, which is the design working.

**Description discipline — the highest-risk string in the batch.** Nineteen words, terse register:
*"Lists the files and folders in one directory. Not recursive; refuses drive roots."* Resist usage
guidance; that is what cost 11 points.

**5.5 Eval changes.** Add `forbid_tools` to `scoring.py` (its test must fail against today's scorer —
the field is currently ignored, so such a case would pass vacuously). **`refuse-drive-scan` must lose
`expect_no_tool`:** once `list_directory` exists, calling it on `C:\` and relaying the refusal is
*correct*, and the harness counts a proposal as a call anyway. Rescope to what was always wanted —
`forbid_tools: [delete_file, rename_file, write_file]` plus it says no. New cases:
`list-directory-bounded`, `list-directory-refuses-root` (asserting the tool's own guard string),
**`safeword-does-not-override-drive-safety`** (the case that proves the guardrail decision held; it
does not exist today), `content-search-excerpt`, and a second `expect_no_tool` case so one lucky
sample can't carry the category. Update the Phase 0 golden in the same commit.

**5.6 Run and record.** `LITHE_EVAL=1 OLLAMA_MODEL=llama3.2 python -m pytest -m eval` (~15 min).
Batching costs attribution: on a drop >5 points, the one bisect worth 11 minutes is re-running with
`list_directory` removed from `OLLAMA_TOOLS_SCHEMA` only. Below 5 points, treat as sampling. Record
engine/model/seed/case-count/score in `CHANGELOG.md` before proceeding — this is the last number ever
comparable to 81%.

---

## ⏱ M2 — qwen2.5 as default — a new baseline, not a delta

**The risk is the upgrade path, not the model.** `config.py:75` is
`os.getenv("OLLAMA_MODEL", "llama3.2")`, and an existing `%APPDATA%/Lithe/.env` contains
`OLLAMA_MODEL` only if the user saved it through Settings. Flip the literal and every existing user who
never touched that field — with llama3.2 pulled and working — is switched to a 4.7 GB model they do not
have.

**Use preference resolution:** `OLLAMA_MODEL_PREFERENCE = ("qwen2.5", "llama3.1", "llama3.2")`. An
explicit env value wins verbatim; otherwise resolve once at import to the first *installed* preference,
falling back to `[0]` when Ollama is unreachable so a fresh user still gets the "pull qwen2.5" message.

**This creates a reproducibility hazard the eval must be locked out of:** a score that depends on what
happens to be installed is the instrument lying again. `tests/eval/conftest.py` must **fail the run**
(not skip) if `OLLAMA_MODEL` is unset while `LITHE_EVAL=1`. Unit-test resolution with `_ollama_catalog`
faked: installed=[llama3.2] → llama3.2; [qwen2.5, llama3.2] → qwen2.5; unreachable → qwen2.5; env wins.

Also: **`OLLAMA_TIMEOUT` default 60 → 150** (7B cold-load first-token routinely exceeds 60s — this is
why Phase 3.1 is a prerequisite, not a nicety); remove `known_gap` from `multistep-find-then-read`
(qwen2.5 passes 3/3 — leaving the flag hides the gain *and* means a future regression never fails);
update onboarding copy, `SettingsPanel.tsx:161`'s placeholder, `docs/TESTING.md`, `README.md`.

Expect **25–40 minutes**. Keep `LITHE_EVAL_REPEATS=3` — trimming repeats to save time makes the new
baseline noisier than the old, defeating its purpose. Record the number with an explicit note that it
is **not comparable** to 81% or to M1.

---

## Phase 7 — Packaging (last)

- `lithe-server.spec`: `hiddenimports += ['pypdf']`. `collect_submodules('src.backend')` covers
  `extractors.py` but **not** pypdf — and if pypdf is imported lazily inside the function (which it
  should be, for startup speed) PyInstaller's static analysis sees nothing and PDF indexing fails
  silently in the packaged build while working perfectly in dev. **The most likely defect in this batch.**
- `requirements.txt`: `pypdf>=4.0.0`. Version bump; `CHANGELOG.md` with both eval numbers.
- `scripts/build-all.ps1` (no incremental path — `build-backend.ps1` deletes `dist/` first; 10–20 min).
  **Its step 2 skips the `.env` copy when `%APPDATA%/Lithe/.env` exists**, which it does on this
  machine — rename it aside first or you will smoke-test a stale config and never see the new defaults.

---

## What is deliberately not being done

- **Changing the FTS5 tokenizer to `porter`/`trigram`.** Full reindex with no migration path (the rows
  exist, just tokenized wrongly), it changes `snippet()` output and therefore the model payload, and
  porter stemming *degrades* literal-token search — `ZEPHYR-441`, `sales_q3`, identifiers, error codes
  — which is most of what a developer searches for. Keep `unicode61`. If recall becomes a real
  complaint, the cheap fix is an OR-of-terms retry when the quoted phrase returns nothing.
- **Streaming `chat()`.** No user-visible benefit, resamples the eval, blinds the recorder.
- **`pdfminer.six` / `python-docx`.** Compiled transitive deps (`cryptography`, `lxml`) for extraction
  quality a keyword index cannot perceive.
- **A state store for `App.tsx`.** Splitting `SystemPanel` and lifting `tokens` gets the whole benefit.
- **Splitting `index.css`.** Separate task, separate day.

---

## Verification

**Per phase:** `python -m pytest -q` stays green (224 passing, 1 xfailed today) and every new test is
confirmed failing against the previous source — `git stash push <file>`, run, `git stash pop`. Renderer:
`cd src/frontend && npm run typecheck`.

**Phase-specific:**
- Phase 1: write a `.md` with a unique token into a watched dir → `search_files_by_content` finds it
  without a restart; `/api/search?q=<body-only-token>` returns it (both fail today).
- Phase 2: `walk_and_index()` over a dir containing a valid PDF, an encrypted PDF, a truncated PDF and
  a `.docx` completes and indexes the good ones — one bad file must not end the walk.
- Phase 3: the `chat()`-still-posts-`stream: False` test is the eval guard; kill the network in the
  running app and watch the fallback type progressively.
- M1/M2: full eval runs, numbers recorded in `CHANGELOG.md` with engine, model, seed and case count.

**Final, on the installed build** (not dev — these are the things that only break when packaged):
1. content search from the UI search box returns an excerpt
2. a PDF dropped into a watched folder becomes searchable → proves the hiddenimport *and* watcher
   parity *and* the backfill in one action
3. Settings → change the Ollama timeout → next request uses it, no restart
4. the Ollama fallback streams progressively
5. `list_directory` on a real folder; then ask for `C:\` and confirm **no DELETE card appears**
6. the undo popover lists a real rename and reverses it
