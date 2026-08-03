# Lithe: Complete Feature Overview

Lithe (Jarvis-Lite) is a local, permissioned AI desktop assistant heavily optimized for Data Science, research, and daily developer workflows. It runs natively on your Windows machine, leveraging a hybrid Electron UI and a robust Python backend to securely search, index, and analyze your local files while maintaining absolute control over what it accesses.

Here is a comprehensive breakdown of Lithe's capabilities:

## 1. Core AI Intelligence (The Brain)
Lithe connects securely to the Gemini API (specifically `gemini-2.5-flash`) to power its reasoning and natural language processing capabilities. By utilizing the official Google GenAI SDK, it ensures rapid, highly-intelligent responses. API keys are handled strictly through a `.env` file locally, keeping your credentials secure.

## 2. Minimal & Premium Chat Interface (The Face)
Lithe features a beautiful, dedicated desktop window built with Electron, React, and TypeScript. 
- **Premium Aesthetics**: It uses a sleek dark navy theme, glassmorphism effects, gradients, and micro-animations, providing a high-end application feel rather than a bland terminal window.
- **Seamless Experience**: Packaged with PyInstaller and `electron-builder`, you get a standalone `Lithe.exe` that automatically manages its own internal Python server without requiring you to use the command line.

## 3. Local Directory Indexer (The Memory)
Instead of wildly scanning your entire hard drive and slowing down your PC, Lithe uses a targeted, lightweight approach.
- **Whitelisting**: You define exactly which directories it is allowed to look at.
- **SQLite Engine**: It silently indexes the paths and metadata of files within these directories into a highly efficient SQLite database.
- **Smart Filtering**: It intentionally ignores heavy folders like `node_modules` or `.git` to save on compute and storage, and automatically updates the index when the server starts.

## 4. RAG & File Context (The Second Brain)
Lithe can read your datasets, PDFs, and code directly.
- **Instant Retrieval**: When you ask about a specific dataset or file, it uses fuzzy searching and queries the SQLite index to find the file instantly.
- **Contextual Injection**: The backend dynamically pulls the content of the file and feeds it to the LLM.
- **Grounded Answers**: The AI gives you answers and insights based *only* on the contents of your local documents, preventing hallucinated answers.

## 5. Basic Task Execution (The Hands)
Lithe isn't just a read-only chatbot; it can act on your behalf.
- **LLM Function Calling**: Lithe has tools registered that allow it to execute system-level Python scripts.
- **Local Automation**: You can ask it to rename files, summarize data, or search your filesystem.
- **Permissioned Actions**: It is programmed to ask for your confirmation before performing any destructive or major actions (like deleting files) to ensure your system's safety.

## 6. Candid Persona & Safeword Override
Lithe is designed to be a peer, not a people-pleaser.
- **Critical Pushback**: The default system prompt instructs Lithe to challenge bad ideas, point out logic flaws, and prioritize factual accuracy over generic politeness. 
- **The Safeword**: If you just need it to blindly comply and execute instructions exactly as written without any debate, you can use the case-insensitive safeword: **"Override Lithe"**. Typing this immediately switches the agent to a strictly compliant mode for that prompt.

---

### In Summary
Lithe successfully bridges the gap between cloud-scale intelligence and local privacy. It’s an intelligent, self-contained desktop peer that knows where your files are, understands how to read them, debates your ideas when they are flawed, and respects your privacy boundaries by only looking where you explicitly tell it to look.
