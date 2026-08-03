# docs/ARCHITECTURE.md — Lithe(Jarvis-Lite) System Design

> **Status:** Draft (v1)
> **Audience:** AI coding agents, lead developer.
> **Project Goal:** A local, permissioned AI desktop assistant optimized for Data Science, research, and daily developer workflows.

## 1. Project Overview
Lithe is a hybrid desktop application. It acts as an always-on, permissioned local actor that lives on the desktop. It bridges a modern web-based UI with a powerful Python backend capable of exploring local file systems (C: and D: drives), executing data science scripts, and automating daily workflows.

## 2. Technology Stack

| Layer | Technology | Rationale |
| :--- | :--- | :--- |
| **Frontend UI** | Electron + React (TypeScript) | Provides a polished, OS-native desktop window (borrowing the architectural style from the *Winnow* reference). |
| **Backend Engine** | Python | The core orchestrator. Ideal for a Data Science student. Handles file system access, data manipulation, and AI tool execution. |
| **Memory & Indexing** | SQLite (with `sqlite-vec`) | A lightweight, local-first database to index the C: and D: drives. Allows the AI to instantly search your files using vector and keyword search without rescanning the hard drive every time. |
| **The Brain (LLM)** | Gemini API / Ollama | A fallback pattern. Uses the Gemini API for complex, high-speed reasoning, with a fallback to local Ollama models for offline or highly sensitive local file parsing. |

## 3. Architecture Style: The "Permissioned Local Actor"
Unlike cloud-only chatbots, Lithe operates directly on the host machine. 
1. **The UI** sends a request (e.g., "Summarize the dataset I downloaded yesterday").
2. **The Python Backend** intercepts the request.
3. **The Memory Engine (SQLite)** instantly queries the indexed map of the C: and D: drives to find the exact file path of the dataset.
4. **The Tool Executer** runs a Python function to read the CSV/PDF.
5. **The Brain** processes the data and streams the answer back to the UI.

## 4. Drive Exploration & Indexing Strategy
To prevent system crashes and endless scanning, Lithe will **not** blindly read every system file. Instead, it will use a targeted indexing strategy:
* **Whitelisted Directories:** The user configures specific roots (e.g., `C:\Users\Name\Documents\DataScience` and `D:\Projects`).
* **Background Crawler:** A Python script periodically hashes and indexes these directories into the local SQLite database.
* **Agent Access:** When the AI needs a file, it queries the SQLite index first, retrieving the exact path before attempting to open the file.

## 5. Packaging & Distribution
Lithe is packaged as a standalone Windows application (`.exe`) using a two-step build process:
1. **PyInstaller**: Compiles the Python backend and all dependencies (including FastAPI and Google GenAI) into a self-contained executable folder.
2. **electron-builder**: Packages the Electron frontend, embeds the PyInstaller backend as `extraResources`, and generates an NSIS installer. 

In production, the Electron main process spawns the bundled PyInstaller backend (`lithe-server.exe`) instead of relying on a system Python installation. Configuration variables (`.env` and the SQLite database) are loaded from the user's AppData directory (`%APPDATA%\Lithe`) to ensure persistence and proper permissions without requiring admin rights.