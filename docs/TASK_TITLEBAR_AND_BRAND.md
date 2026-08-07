# docs/TASK_TITLEBAR_AND_BRAND.md — Themed Title Bar + New Logo

> **Status:** Active task spec
> **Read first:** `docs/agent-logs/INDEX.md`, `.agents/AGENTS.md`, `docs/DESIGN_SYSTEM.md`
> **Assets provided:** `lithe-brand/` folder — `lithe-mark-hero.svg` (thin tapered mark, use in-app: title bar icon, boot screen, README), `lithe-mark-icon.svg` (bolder mark, source for small sizes), `icon.ico` (multi-res Windows icon, ready to use), `app-icon-512.png` + `icon_16/32/48/64/128/256.png` (individual sizes if needed elsewhere)

---

## 0. Context
Two issues from the latest design review:
1. The window currently uses Electron's default native title bar — plain dark gray, un-themed, generic min/max/close buttons. It reads as a different app bolted onto the HUD design below it.
2. The app icon is a placeholder — needs to become the new Lithe mark (thin diagonal amber flowing line, evoking "lithe" + the river Lethe).

---

## 1. Themed title bar

**Recommended approach for Windows: `titleBarOverlay`, not a fully custom frame.**
This keeps native OS window behavior (Aero Snap, Windows 11 Snap Layouts flyout on hover) which users expect and lose if you go fully frameless — but lets you theme the overlay's colors and own the rest of the title bar as your own draggable React content.

In `src/main/index.ts`, update the `BrowserWindow` constructor:
```ts
new BrowserWindow({
  // ...existing options
  titleBarStyle: 'hidden',
  titleBarOverlay: {
    color: '#0e0e11',      // --panel from DESIGN_SYSTEM.md
    symbolColor: '#c9c9ce', // --text
    height: 32
  },
})
```

**Renderer side** (`App.tsx` or a new `TitleBar.tsx` component):
- Build a custom title bar row that fills the space to the left of the native overlay buttons: `-webkit-app-region: drag` on the row itself so it's still draggable, and `-webkit-app-region: no-drag` on anything clickable inside it (buttons, inputs) so they don't accidentally drag the window.
- Layout: `lithe-mark-hero.svg` (small, ~18px) + `LITHE` wordmark (existing amber uppercase treatment) on the left, `LITHE // LOCAL-AI` tag on the right — this is mostly what exists today in the `LITHE ... LITHE // LOCAL-AI` header row already, just move it into the actual title bar area instead of a separate row below it, so there's no duplicate header.
- Background: `--panel` (`#0e0e11`), 1px bottom border `--border`, height 32px to match the overlay height above.
- On hover, the native overlay buttons (min/max/close) already pick up `symbolColor` — no need to hand-build them.

**If cross-platform (Mac/Linux) support matters later:** `titleBarOverlay` is Windows/Linux-only in Electron; macOS would need `titleBarStyle: 'hiddenInset'` with `trafficLightPosition` instead. Not required now since `ARCHITECTURE.md` targets Windows only — flag this as a known gap if cross-platform ever becomes a goal, don't build for it yet.

---

## 2. New app icon

- Replace the existing icon reference in `electron-builder`'s config (likely `build.win.icon` in `package.json` or `electron-builder.yml`) to point at the provided `icon.ico`.
- Set `BrowserWindow`'s `icon` option (main process, dev-mode window icon) to `icon.ico` as well — this is separate from the packaged build icon and often gets missed, causing dev mode to still show the old/default icon even after the build config is fixed.
- Use `lithe-mark-hero.svg` (not `lithe-mark-icon.svg`) for the in-title-bar icon per §1 — it's rendered larger there (~18px+) where the thinner, more elegant taper reads fine; the bolder `lithe-mark-icon.svg` is specifically for tiny system-icon contexts (taskbar, alt-tab) where legibility at 16–32px matters more than elegance. Don't mix these up.
- If the boot sequence screen (`LITHE v1.0.0 initializing local actor...`) has room, consider placing `lithe-mark-hero.svg` above or beside that text at a larger size (e.g. 48–64px) — it's a nice moment for the brand mark to actually breathe, unlike the cramped title bar version.

---

## 3. Two small bugs found in the same review pass, fix alongside this

- **`last event` in `[01] INDEX` never updates** (stuck at `--:--:--`) despite `[03] SYSTEM`'s watcher log clearly receiving live events from the same watcher. Both should read from the same event stream — wire `[01] INDEX`'s timestamp to the same WebSocket data `[03] SYSTEM` already consumes (per `TASK_WATCHER_LOG_CONSOLE.md`), don't maintain two separate paths to the same underlying event.
- **Port-bind conflict (`WinError 10048`) when both a manually-run backend and Electron's own spawned backend are active.** This is likely a dev-workflow collision (two terminals + Electron's own spawn in `main/index.ts` all trying to bind :8321), not necessarily a code bug — but the main process should handle `EADDRINUSE` gracefully: detect a backend already listening on the configured port and connect to it instead of crashing/erroring, with a clear log line stating that's what happened. This will keep coming up during dev otherwise.

---

## Definition of Done (in addition to `AGENT_PLAYBOOK.md` §4)
- [ ] Native Windows title bar buttons (min/max/close) are themed via `titleBarOverlay`, not hand-built — preserves Snap Layouts.
- [ ] No duplicate header row — the existing `LITHE // LOCAL-AI` row is merged into the actual title bar, not kept as a separate row underneath it.
- [ ] `icon.ico` is wired into both the electron-builder packaging config AND the dev-mode `BrowserWindow` icon option.
- [ ] `[01] INDEX`'s `last event` updates live, matching `[03] SYSTEM`'s log.
- [ ] Backend handles a port-already-in-use condition without crashing.
- [ ] Update `docs/agent-logs/INDEX.md` per `.agents/AGENTS.md`.
