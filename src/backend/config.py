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

# Priority 1: %APPDATA%/Lithe/.env (packaged / installed mode)
_APPDATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / "Lithe"
_APPDATA_ENV = _APPDATA_DIR / ".env"
if _APPDATA_ENV.exists():
    load_dotenv(dotenv_path=_APPDATA_ENV)
    _LOADED_ENV = True

# Priority 2: Adjacent to the executable (portable mode)
if not _LOADED_ENV and getattr(sys, 'frozen', False):
    _EXE_DIR = Path(sys.executable).parent
    _PORTABLE_ENV = _EXE_DIR / ".env"
    if _PORTABLE_ENV.exists():
        load_dotenv(dotenv_path=_PORTABLE_ENV)
        _LOADED_ENV = True

# Priority 3: Project root (development mode — two levels up from this file)
if not _LOADED_ENV:
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    _ENV_PATH = _PROJECT_ROOT / ".env"
    load_dotenv(dotenv_path=_ENV_PATH)


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

