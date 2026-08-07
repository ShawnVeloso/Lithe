# docs/DESIGN_SYSTEM.md — Lithe HUD Redesign (v2)

> **Status:** Active — supersedes the color/layout choices in `DESIGN_BRIEF.md`, keep that file's constraints (Section 4) and process (Section 5) intact.
> **Reference mood:** Iron Man / HUD console — dense telemetry, hairline borders, monospace, corner-anchored labels. **Not** a reskin of any specific reference tool — Lithe has its own hue, its own panel set, built around its own actual features (F-01–F-06).
> **Read first:** `docs/DESIGN_BRIEF.md` (Sections 0–1), `docs/agent-logs/INDEX.md`

---

## 1. Signature Palette

Lithe's identity color is **amber**, not cyan. This is the one deliberate visual choice that makes Lithe recognizable at a glance versus other tools in this style. Amber reads as "engineering console / active system," warmer and more alert than a cold cyan terminal.

Semantic multi-color coding, used consistently everywhere a state is shown:

| Token | Hex (starting point) | Meaning |
|---|---|---|
| `--bg` | `#08080a` | Base background — near-black, not navy |
| `--panel` | `#0e0e11` | Panel fill, 1 shade up from bg |
| `--border` | `#2a2a2e` | Default hairline border (1px) |
| `--border-active` | `--accent` | Border of the focused/active panel |
| `--text` | `#c9c9ce` | Default body text |
| `--text-dim` | `#6a6a70` | Secondary/meta text (timestamps, labels) |
| `--accent` (Lithe signature) | `#ffb020` (amber) | Primary accent — active states, focus rings, links, cursor |
| `--success` | `#3ddc84` (green) | Completed actions, healthy status, safe tool calls |
| `--danger` | `#ff5c5c` (red) | Errors, critical resource state, destructive-action confirmations |
| `--info` | `#5b8dff` (blue) | Neutral system messages, background/indexing activity |
| `--special` | `#b083ff` (violet) | **Safeword mode active** — reserved for this one state so it's unmistakable |

Rules:
- **Never mix `--danger` and `--special`** in the same view — safeword mode and error state must stay visually distinguishable from each other.
- Amber is the *only* color used for interactive affordances in the idle state (buttons, focus outline, blinking cursor). The other four colors are status-only, never decorative.
- No gradients. No glow/blur. Flat fills, 1px borders.

---

## 2. Typography

- **Font:** monospace stack throughout — `"JetBrains Mono", "IBM Plex Mono", ui-monospace, SFMono-Regular, monospace`.
- **Scale:** small and disciplined, telemetry-style, not editorial:
  - Panel titles: 11px, uppercase, letterspaced (`0.08em`), `--text-dim`
  - Body/chat text: 13–14px, `--text`
  - Meta/labels (timestamps, token counts): 11px, `--text-dim`
  - Numeric readouts (token counts, elapsed time): same monospace, but `--accent` when live/active
- **Corner tag convention:** every top-level window carries a small top-right identifier in the header bar, e.g. `LITHE // LOCAL-AI`, uppercase, `--text-dim`, letterspaced — Lithe's equivalent of a HUD build tag. This is cosmetic but load-bearing for the "console" feel — don't skip it.

---

## 3. Panel Convention

Every panel (not just the chat) follows the same shell:
- 1px `--border`, 0–2px corner radius
- Header row: `[NN] LABEL` on the left (numbered, like `[01] INDEX`), small utility buttons/status pill on the right
- Panel becomes `--border-active` (amber) when it's the focused/active pane
- No drop shadows; depth comes only from the border + slightly lighter panel fill

This numbered-panel-with-label convention is intentionally systems-dashboard-like — but Lithe's version uses bracketed numbers (`[01]`) rather than plain digits, and amber-only active-state highlighting rather than per-panel color variety, to keep it calmer than a multi-tool cockpit.

---

## 4. Layout — Multi-Pane Expansion

Lithe moves from a single chat window to a **three-pane HUD layout**, all real features already in the backend (per `INDEX.md`) — nothing invented:

```
┌─ LITHE ────────────────────────────────────── LITHE // LOCAL-AI ─┐
│ [01] INDEX                    │ [02] CHAT                        │
│ ─────────────────             │ ──────────────────────────────── │
│ watched dirs                  │  lithe> [response stream]        │
│  D:\Projects        1,204 files│                                  │
│  C:\...\DataScience   318 files│  user> [prompt]                  │
│                                │                                  │
│ watcher: ● live                │                                  │
│ last event: 00:04:12 ago       │                                  │
│                                │  ┌──────────────────────────┐   │
│                                │  │ > _                       │   │
│                                │  └──────────────────────────┘   │
├────────────────────────────────┴───────────────────────────────┤
│ [03] SYSTEM                                                      │
│ server: ● connected   mode: ● candid   safeword: ○ inactive     │
│ tokens in/out: 1,204 / 388     tool calls: 2 pending confirm     │
└────────────────────────────────────────────────────────────────┘
```

| Pane | Maps to | Shows |
|---|---|---|
| `[01] INDEX` | F-03/F-04 (indexer, watcher) | Whitelisted directories, file counts, live watcher status (`watcher.py`), last index event — this makes the normally-invisible SQLite indexing *visible*, which is exactly the "system is alive" feeling this style is going for |
| `[02] CHAT` | F-01/F-02/F-04/F-05 | Main conversation, terminal-style `user>` / `lithe>` prefixes, command-line-style input with blinking cursor, inline tool-call confirmation blocks (see §5) |
| `[03] SYSTEM` | F-01/F-05/F-06 | Server health dot, persona mode (candid/compliant), **safeword indicator** (violet when active), live token counters, pending destructive-action confirmations |

Notes:
- This is a **desktop-window redesign**, still inside the existing fixed Electron window — pane proportions should be roughly 20% / 55% / 25% left-to-right, with `[03] SYSTEM` as a full-width strip at the bottom (~15% height) rather than a third column, to keep chat dominant.
- On narrow/resize edge cases, `[01] INDEX` can collapse to an icon rail — flag this to the user rather than guessing if it comes up.

---

## 5. State Treatments (new, since this expands scope slightly)

- **Safeword active (`"Override Lithe"` detected):** `[03] SYSTEM` panel border and the safeword indicator switch to `--special` (violet) for the duration of that response. This is the one state Winnow's reference has no equivalent for — it's Lithe-specific and should be the most visually distinct moment in the app, since it changes agent behavior meaningfully.
- **Destructive tool-call confirmation (F-05):** rendered as a bordered block inline in `[02] CHAT`, `--danger` border, monospace command preview, explicit `[Y] Confirm` / `[N] Cancel` style buttons — not a generic modal.
- **Indexing/watcher activity:** `[01] INDEX` shows a small live dot (`--info` blue, pulsing via opacity only — no motion blur/scale) when the watcher fires an event.
- **Server disconnected:** `[03] SYSTEM` health dot turns `--danger`, and `[02] CHAT` input becomes visibly disabled (dimmed border, not grayed-out text).

---

## 6. What Changed From `DESIGN_BRIEF.md`

- Accent color: **amber**, not left-to-agent-discretion.
- Confirmed semantic multi-color palette (5 colors, table in §1).
- Scope expanded from single-pane to three-pane layout — update `docs/FEATURES.md` to log this as a UI change once implemented, per `AGENTS.md`.
- All other constraints from `DESIGN_BRIEF.md` §4 (no heavy deps, don't touch backend, fixed-window unless justified, accessibility/contrast) still apply.
