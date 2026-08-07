"""
Lithe — Configuration (F-01: Core LLM Connection)

Loads environment variables from a `.env` file and exposes
application-wide constants. Fails fast with a clear error if
required variables are missing.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load .env — supports packaged (frozen) and development modes
# ---------------------------------------------------------------------------
_LOADED_ENV = False
_ACTIVE_ENV_PATH = None

# Priority 1: %APPDATA%/Lithe/.env (packaged / installed mode)
_APPDATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / "Lithe"
_APPDATA_ENV = _APPDATA_DIR / ".env"
if _APPDATA_ENV.exists():
    load_dotenv(dotenv_path=_APPDATA_ENV)
    _LOADED_ENV = True
    _ACTIVE_ENV_PATH = _APPDATA_ENV

# Priority 2: Adjacent to the executable (portable mode)
if not _LOADED_ENV and getattr(sys, 'frozen', False):
    _EXE_DIR = Path(sys.executable).parent
    _PORTABLE_ENV = _EXE_DIR / ".env"
    if _PORTABLE_ENV.exists():
        load_dotenv(dotenv_path=_PORTABLE_ENV)
        _LOADED_ENV = True
        _ACTIVE_ENV_PATH = _PORTABLE_ENV

# Priority 3: Project root (development mode — two levels up from this file)
if not _LOADED_ENV:
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    _ENV_PATH = _PROJECT_ROOT / ".env"
    load_dotenv(dotenv_path=_ENV_PATH)
    _ACTIVE_ENV_PATH = _ENV_PATH


# ---------------------------------------------------------------------------
# Required environment variables
# ---------------------------------------------------------------------------
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

if not GEMINI_API_KEY:
    # Provide context-appropriate instructions
    if getattr(sys, 'frozen', False):
        _env_location = _APPDATA_DIR / ".env"
        sys.exit(
            "[Lithe Config Error] GEMINI_API_KEY is not set.\n"
            f"  1. Create a file at: {_env_location}\n"
            "  2. Add this line: GEMINI_API_KEY=your_key_here\n"
            "  3. Get your key from https://aistudio.google.com/apikey\n"
            "  4. Re-launch Lithe."
        )
    else:
        _dev_root = Path(__file__).resolve().parent.parent.parent
        sys.exit(
            "[Lithe Config Error] GEMINI_API_KEY is not set.\n"
            f"  1. Copy '{_dev_root / '.env.example'}' to '{_dev_root / '.env'}'\n"
            "  2. Paste your Gemini API key from https://aistudio.google.com/apikey\n"
            "  3. Re-run the application."
        )

# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------
GEMINI_MODEL: str = "gemini-3.6-flash"

# ---------------------------------------------------------------------------
# Ollama fallback configuration (Phase 2: Reliability)
# ---------------------------------------------------------------------------
# When the Gemini API is unreachable (network drop, rate limit, API error),
# Lithe falls back to a local Ollama model. These values are configurable
# via .env so users can point to different models or remote Ollama instances.
OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_TIMEOUT: int = int(os.getenv("OLLAMA_TIMEOUT", "60"))

# ---------------------------------------------------------------------------
# F-03: Memory & Indexer configuration
# ---------------------------------------------------------------------------
# In packaged mode, store the SQLite DB in %APPDATA%/Lithe/
# In dev mode, store it at <project_root>/.lithe/
if getattr(sys, 'frozen', False):
    _LITHE_DIR = _APPDATA_DIR
else:
    _LITHE_DIR = Path(__file__).resolve().parent.parent.parent / ".lithe"

_LITHE_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH: Path = _LITHE_DIR / "lithe_memory.db"

# Parse the comma-separated whitelist from .env
_raw_whitelist = os.getenv("INDEX_WHITELIST", "")
INDEX_WHITELIST: list[str] = [
    path.strip() for path in _raw_whitelist.split(",") if path.strip()
]


def update_whitelist(path: str, remove: bool = False) -> None:
    """Updates the whitelist in memory and persists to the active .env file."""
    global INDEX_WHITELIST
    path = path.strip()
    
    if remove:
        if path in INDEX_WHITELIST:
            INDEX_WHITELIST.remove(path)
    else:
        if path and path not in INDEX_WHITELIST:
            INDEX_WHITELIST.append(path)

    # Persist to .env
    if _ACTIVE_ENV_PATH and _ACTIVE_ENV_PATH.exists():
        new_val = ",".join(INDEX_WHITELIST)
        
        with open(_ACTIVE_ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        found = False
        for i, line in enumerate(lines):
            if line.startswith("INDEX_WHITELIST="):
                lines[i] = f"INDEX_WHITELIST={new_val}\n"
                found = True
                break
                
        if not found:
            # Ensure file ends with a newline before appending
            if lines and not lines[-1].endswith("\n"):
                lines.append("\n")
            lines.append(f"INDEX_WHITELIST={new_val}\n")
            
        with open(_ACTIVE_ENV_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines)

