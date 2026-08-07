<div align="center">
  <img src="src/frontend/resources/icon.png" alt="Lithe Logo" width="120" />
  <h1>Lithe</h1>
  <p><strong>A privacy-first, local-RAG agentic coding assistant with a terminal-inspired HUD.</strong></p>
</div>

---

**Lithe** is an intelligent, event-driven coding assistant designed to give LLMs continuous, real-time context about your codebase without compromising your privacy or data sovereignty. It watches your workspace, indexes your files into an ultra-fast SQLite memory graph, and executes coding tasks with explicit, diff-based user consent.

Built for developers who want the power of AI coding assistants without the bloat, cloud dependencies, or loss of control over their file systems.

## ✨ Features

- 🧠 **Event-Driven Memory (Local RAG)**
  Lithe doesn't just read your files once. It uses a background watchdog to monitor your whitelisted directories. Whenever you edit, delete, or create a file, Lithe instantly updates its internal SQLite index, ensuring the AI's context is always perfectly synchronized with your real-world filesystem.
  
- 🛡️ **Interactive Tool Interceptor (Zero Accidental Destruction)**
  Unlike other agents that silently mutate your files, Lithe intercepts all destructive LLM actions (writes, renames, deletes). It parses the changes and presents you with an interactive Diff Card in the UI, forcing the agent to pause until you explicitly click **ACCEPT** or **REJECT**. 

- ⚡ **Indexing Efficiency & Startup Reconciliation**
  Lithe compares OS modification signatures against its database to avoid redundant I/O, meaning it boots instantly regardless of how many files you have indexed. Smart extension filtering blocks heavy binary bloatware (`.dll`, `.exe`, `.pak`) out of the box, keeping your LLM context pristine.

- 🖥️ **Three-Pane Terminal HUD**
  A stunning, custom-built React + Electron user interface heavily inspired by terminal aesthetics. Features an amber-on-near-black palette, monospace fonts, hairline borders, and live telemetry for both file indexing and LLM token usage.

- 📴 **Offline Fallback (Ollama)**
  Lithe is built with a robust model-routing architecture. If the primary Gemini API goes offline or you disconnect from the internet, Lithe will gracefully and automatically failover to your local Ollama models (e.g., `llama3`), allowing you to keep coding completely offline.

## 🏗️ Architecture Stack

Lithe is split into two highly optimized layers communicating via REST and WebSockets:

* **Frontend (Electron + React + Vite)**: A lightweight, sandboxed UI shell rendering the three-pane HUD. It communicates entirely through IPC and REST.
* **Backend (Python + FastAPI)**: The true "brain" of the operation. It runs a Uvicorn server, manages the SQLite memory database, orchestrates the `watchdog` file observer, and handles all LLM API routing and tool execution.

## 🚀 Getting Started

### Prerequisites
- Node.js (v18+)
- Python (3.10+)
- [Ollama](https://ollama.com/) (Optional, for offline fallback)
- A Gemini API Key (Optional, for primary intelligence)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/Lithe.git
   cd Lithe
   ```

2. **Set up the Python Backend:**
   ```bash
   # Navigate to the backend or root and install requirements (example)
   pip install -r requirements.txt
   ```

3. **Set up your Environment Variables:**
   Create a `.env` file in the root directory.
   ```env
   GEMINI_API_KEY=your_api_key_here
   INDEX_WHITELIST=C:\path\to\your\project
   ```

4. **Install Frontend Dependencies:**
   ```bash
   cd src/frontend
   npm install
   ```

5. **Run the App (Development Mode):**
   ```bash
   npm run dev
   ```
   *Note: Running `npm run dev` in the frontend directory will automatically spawn the Python FastAPI backend process.*

## 🗺️ Roadmap & Milestones

Lithe is actively developed. Current major milestones include:
- **Phase 3**: Efficiency & Context (Heuristic Graphs, Event-Driven Memory) - ✅ Complete
- **Phase 4**: Visual Identity & Control (HUD Redesign, Tool Interception) - ✅ Complete
- **Phase 5**: Performance (Indexing Efficiency Upgrades) - ✅ Complete

## 📜 License

This project is open-sourced under the MIT License. Feel free to fork, modify, and build your own local agentic workflows!
