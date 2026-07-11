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
# Load .env from the project root (two levels up from this file)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"

load_dotenv(dotenv_path=_ENV_PATH)

# ---------------------------------------------------------------------------
# Required environment variables
# ---------------------------------------------------------------------------
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

if not GEMINI_API_KEY:
    sys.exit(
        "[Lithe Config Error] GEMINI_API_KEY is not set.\n"
        f"  1. Copy '{_PROJECT_ROOT / '.env.example'}' to '{_ENV_PATH}'\n"
        "  2. Paste your Gemini API key from https://aistudio.google.com/apikey\n"
        "  3. Re-run the application."
    )

# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------
GEMINI_MODEL: str = "gemini-2.5-flash"
