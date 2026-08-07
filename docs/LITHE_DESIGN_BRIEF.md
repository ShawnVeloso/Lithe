# docs/DESIGN_BRIEF.md — Lithe Visual Redesign (Terminal/Technical Direction)

> **Status:** Active — Design Pass v2
> **Audience:** AI coding agents (Antigravity or successor)
> **Read first:** `docs/AGENT_PLAYBOOK.md`, `docs/agent-logs/INDEX.md`
> **Scope:** Full visual overhaul of the Electron + React frontend. No backend, no feature logic changes — this is styling and component-structure only, unless a visual requirement genuinely needs a new UI state (e.g. an indexing-status indicator).

---

## 0. Before You Touch Any Code

1. Read `docs/agent-logs/INDEX.md` to confirm current project state.
2. Read this file completely.
3. Reply with a short plan (which files you'll touch, in what order) before writing code.
4. This is a **replacement** of the current dark navy / glassmorphism theme (`src/renderer/src/index.css`), not an addition to it. Old gradient/blur/glow styles should be removed, not layered under.

---

## 1. Creative Direction

**Theme: Technical / terminal-inspired.**

Lithe is a local, permissioned, developer-facing tool that reads your file system and executes code. The UI should *look* like that — not like a consumer chatbot. Think: a well-designed terminal, a code editor's chrome, a systems-monitoring dashboard. Precise, legible, a little austere. The opposite of soft glassmorphism.

**Reference points (mood, not literal copy):** Warp terminal, Zed editor, htop/btop dashboards, Linear's information density, old-school green-phosphor terminals as a *color accent*, not the whole palette.

**Principles:**
- **Monospace-first.** Primary typeface should be a monospace font (e.g. `JetBrains Mono`, `IBM Plex Mono`, `Berkeley Mono` fallback stack). Use a monospace font for chat text, UI labels, everything — this is a deliberate, consistent choice, not just code blocks.
- **Sharp edges.** No large border-radius. 0–2px radius max. Rectangular panels, hard dividers.
- **Flat, not glassy.** Remove blur/backdrop-filter, drop the gradient backgrounds. Use flat solid panels with 1px borders instead of shadows for depth.
- **Restrained color.** A near-black or dark-graphite base (not navy). One accent color used sparingly and consistently (e.g. terminal green, amber, or cyan — pick one and use it for focus states, active indicators, the safeword-triggered state, and links only).
- **Visible structure.** Embrace grid lines, dividers, and labeled sections rather than hiding structure behind whitespace. Status indicators (server health, indexing state, safeword mode) should look like system telemetry — small, monospace, corner-anchored.
- **Motion:** minimal. A blinking cursor, a terminal-style text reveal on new messages, is welcome. Avoid bouncy/springy animations.

---

## 2. Surfaces In Scope (from current file manifest)

Redesign all of these, consistently, as one system — don't reskin App.tsx and leave the rest:

| File | What it is | Design ask |
|---|---|---|
| `src/renderer/src/index.css` | Global design tokens | Replace with new CSS variables: monospace font stack, dark-graphite palette, single accent color, 0–2px radii, flat borders |
| `src/renderer/src/App.tsx` | Chat shell | Restructure as a terminal-pane layout — consider a persistent top status bar showing server health / index status |
| `src/renderer/src/components/ChatWindow.tsx` | Message feed + welcome screen | Welcome screen should read like a boot/init screen, not a hero banner |
| `src/renderer/src/components/MessageBubble.tsx` | Message cards | Reconsider "bubbles" entirely — a terminal-style prefix (`user>`, `lithe>`) with flat text may fit the theme better than rounded gradient cards |
| `src/renderer/src/components/ChatInput.tsx` | Input box | Style as a command-line input — consider a prompt character prefix, blinking cursor, monospace |
| `src/main/index.ts` | Window config | Confirm window chrome/titlebar treatment matches (e.g. keep it minimal/frameless if that fits the terminal look) |

---

## 3. Functional States That Need Visual Treatment

These exist in the backend already (per `INDEX.md`) and need a clear visual language, not just default browser styling:

- **Server health** (`GET /api/health`) — connected / connecting / disconnected
- **Indexing status** — idle / actively scanning (watcher running)
- **Safeword mode active** (`"Override Lithe"`) — should be *visibly distinct*, e.g. accent color shifts or a mode label appears, since this changes agent behavior meaningfully
- **Typing / thinking indicator** — already exists per `ChatWindow.tsx`, restyle to fit (e.g. animated monospace ellipsis or cursor blink, not a spinner)
- **Tool execution confirmation** (F-05 destructive-action confirmation) — needs a clear, distinct visual treatment since this is a safety-critical moment, not just another message

---

## 4. Constraints

- Don't introduce heavy new dependencies for this (no large icon libraries, no animation frameworks) — pure CSS/SVG is preferred, consistent with the "lightweight" philosophy in `ARCHITECTURE.md`.
- Keep the Electron window non-resizable/fixed-size behavior unless you have a specific reason tied to the new layout — flag it if you think it should change.
- Don't touch `src/backend/**` — this is a frontend-only pass.
- Accessibility: maintain readable contrast ratios even with the darker, flatter palette — don't sacrifice legibility for aesthetic.

---

## 5. Deliverable & Process

1. Propose the color token set + font stack first (as CSS variables) before touching components, so it can be reviewed as one small diff.
2. Then work top-down: global shell → ChatWindow → MessageBubble → ChatInput → status indicators.
3. Take a screenshot or describe the result after each major component for review before moving to the next.
4. Follow `AGENTS.md`: update `docs/agent-logs/INDEX.md` with what was changed and why, and sync `docs/FEATURES.md` if this introduces any new trackable feature (e.g. a formalized "status bar" component).
