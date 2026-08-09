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

NEEDS_ONBOARDING: bool = False

if not GEMINI_API_KEY:
    NEEDS_ONBOARDING = True
    print("[Lithe Config] GEMINI_API_KEY is not set. Enabling Onboarding Wizard.")

# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------
GEMINI_MODEL: str = "gemini-3.6-flash"
TOKEN_BUDGET_WARNING: int = int(os.getenv("TOKEN_BUDGET_WARNING", "1500000"))

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

DEFAULT_EXCLUDED_EXTENSIONS = [
    ".xnb", ".pak", ".vpk", ".uasset", ".umap", ".unity3d", ".assets",
    ".bsp", ".wad", ".sav", ".fbx", ".blend", ".obj", ".tga", ".dds",
    ".mtl", ".stl", ".ply", ".exe", ".dll", ".so", ".dylib", ".sys", ".bin",
    ".msi", ".apk", ".app", ".ipa", ".elf", ".cab", ".class", ".pyc",
    ".pyo", ".pyd", ".o", ".a", ".lib", ".ilk", ".pdb", ".suo",
    ".idb", ".manifest", ".mp4", ".mkv", ".avi", ".mov", ".webm", ".wmv",
    ".flv", ".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".png", ".jpg",
    ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".tiff", ".psd", ".ai",
    ".prproj", ".aep", ".tmp", ".temp", ".bak", ".swp", ".swo", ".DS_Store",
    "Thumbs.db", ".dat", ".idx", ".pid", ".crdownload", ".part", ".cache",
    ".zip", ".rar", ".7z", ".tar", ".gz", ".xz", ".bz2", ".iso", ".vmdk",
    ".qcow2", ".vdi", ".ova", ".img", ".dmg", ".ttf", ".otf", ".woff",
    ".woff2", ".eot", ".sqlite", ".db", ".frm", ".ibd", ".mdf", ".ldf",
    ".rdb", ".lock"
]

# Parse the comma-separated whitelist from .env
_raw_whitelist = os.getenv("INDEX_WHITELIST", "")
INDEX_WHITELIST: list[str] = [
    path.strip() for path in _raw_whitelist.split(",") if path.strip()
]

# Parse the comma-separated excluded extensions from .env
_raw_excluded_exts = os.getenv("EXCLUDED_EXTENSIONS")
if _raw_excluded_exts is None:
    # Key doesn't exist in .env, use default list
    EXCLUDED_EXTENSIONS = [ext.lower() for ext in DEFAULT_EXCLUDED_EXTENSIONS]
else:
    EXCLUDED_EXTENSIONS = [
        ext.strip().lower() for ext in _raw_excluded_exts.split(",") if ext.strip()
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

def update_excluded_extensions(ext: str, remove: bool = False) -> None:
    """Updates the excluded extensions list in memory and persists to the active .env file."""
    global EXCLUDED_EXTENSIONS
    ext = ext.strip().lower()
    # Ensure it starts with a dot if not empty
    if ext and not ext.startswith("."):
        ext = f".{ext}"
    
    if remove:
        if ext in EXCLUDED_EXTENSIONS:
            EXCLUDED_EXTENSIONS.remove(ext)
    else:
        if ext and ext not in EXCLUDED_EXTENSIONS:
            EXCLUDED_EXTENSIONS.append(ext)

    # Persist to .env
    if _ACTIVE_ENV_PATH and _ACTIVE_ENV_PATH.exists():
        new_val = ",".join(EXCLUDED_EXTENSIONS)
        
        with open(_ACTIVE_ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        found = False
        for i, line in enumerate(lines):
            if line.startswith("EXCLUDED_EXTENSIONS="):
                lines[i] = f"EXCLUDED_EXTENSIONS={new_val}\n"
                found = True
                break
                
        if not found:
            # Ensure file ends with a newline before appending
            if lines and not lines[-1].endswith("\n"):
                lines.append("\n")
            lines.append(f"EXCLUDED_EXTENSIONS={new_val}\n")
            
        with open(_ACTIVE_ENV_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines)

