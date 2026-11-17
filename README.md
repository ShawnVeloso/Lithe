<div align="center">
  <img src="src/frontend/resources/icon.png" alt="Lithe Logo" width="120" />
  <h1>Lithe</h1>
  <p><strong>A local, permissioned AI assistant for your own files, with a terminal-style desktop UI.</strong></p>
</div>

---

Lithe is a desktop app that lets an LLM work with the files on your machine. It keeps an index of the folders you allow, gives the model tools to search, read and analyse those files, and asks you before any change to the file system. It uses Gemini when it can reach it and falls back to a local Ollama model when it cannot.

## Features

- **Agent with tools.** The model can search, read (including PDF and DOCX contents), list folders, profile CSV/Excel data and draw charts. One turn runs a bounded tool loop (up to 5 rounds); when the budget runs out, the model must answer in text.
- **You approve every change.** Writes, renames and deletes pause the agent and show a diff card in the UI. Nothing changes until you click **ACCEPT**. Calls aimed at a drive root or a protected path are refused before a card is shown.
- **Local index that stays current.** Whitelisted folders are indexed into SQLite (WAL mode). A `watchdog` file watcher updates the index on every create, edit and delete, and startup compares modification times so unchanged files are not re-read.
- **Content search.** An SQLite FTS5 index holds the text of supported files (first 100 KB each), so `search_files` finds files by what they contain as well as by name, and returns the matching passage. Retrieval is keyword-based; there are no embeddings.
- **Offline fallback.** If Gemini is unreachable (network error, rate limit, API error), the same conversation continues on a local Ollama model with the same tools. The default is `qwen2.5`, or `llama3.1` / `llama3.2` if that is what you have pulled. Set `OLLAMA_MODEL` or pick one in Settings to choose.
- **Terminal-style UI.** A three-pane Electron + React window with live telemetry for indexing and token use.

## Architecture

| Layer | Technology |
|---|---|
| Desktop UI | Electron, React, TypeScript, Vite. The renderer has no Node access; all calls go through `contextBridge`. |
| Backend | Python, FastAPI on `localhost:8321`. Electron starts it as a child process and waits for `/api/health`. |
| Index | SQLite (WAL, FTS5), `watchdog` |
| Models | Gemini API (`google-genai`), Ollama |

More detail: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/FEATURES.md`](docs/FEATURES.md).

## Getting started

### Prerequisites
- Node.js 18+
- Python 3.10+
- [Ollama](https://ollama.com/) (optional, for the offline fallback: `ollama pull qwen2.5`)
- A Gemini API key (optional)

### Install and run

```bash
git clone https://github.com/ShawnVeloso/Lithe.git
cd Lithe
pip install -r requirements.txt
```

Create a `.env` file in the repo root (see `.env.example`):

```env
GEMINI_API_KEY=your_api_key_here
INDEX_WHITELIST=C:\path\to\your\project
```

Then start the app in development mode:

```bash
cd src/frontend
npm install
npm run dev
```

`npm run dev` also starts the Python backend.

## Tests and evaluation

```bash
python -m pytest
```

The unit suite (319 passing at v1.1.0) runs with no network and no real indexing.

A separate, opt-in evaluation scores the agent end to end on 22 tool-use cases. It checks that the right tools ran and that their results actually reached the user, with seeded sampling so runs are reproducible:

```bash
LITHE_EVAL=1 OLLAMA_MODEL=qwen2.5 python -m pytest -m eval
```

Latest recorded result: 22 of 22 cases on qwen2.5 (seed 20260905, Ollama 0.34.4). See [`docs/TESTING.md`](docs/TESTING.md) and [`CHANGELOG.md`](CHANGELOG.md) for how the harness works and how the score has moved.

## License

This project is open-sourced under the [MIT License](LICENSE).
