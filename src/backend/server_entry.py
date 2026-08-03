"""
Lithe — PyInstaller Entry Point

This module serves as the standalone entry point for the Python backend
when packaged via PyInstaller. It duplicates the server startup logic
from server.py but uses direct imports instead of package-relative imports,
since PyInstaller bundles everything into a flat namespace.

This file is NOT used in development — only for the packaged build.
"""

import sys
import os

# ---------------------------------------------------------------------------
# Environment setup for packaged mode
# ---------------------------------------------------------------------------
# When running as a PyInstaller bundle, sys._MEIPASS points to the temp
# extraction directory. We need to set up paths so dotenv can find .env
# in the user's AppData folder.

def _get_app_data_dir() -> str:
    """Returns the Lithe application data directory (%APPDATA%/Lithe)."""
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    lithe_dir = os.path.join(appdata, "Lithe")
    os.makedirs(lithe_dir, exist_ok=True)
    return lithe_dir


def _setup_env():
    """Load .env from the app data directory or the project root."""
    from dotenv import load_dotenv

    # Priority 1: %APPDATA%/Lithe/.env (production)
    appdata_env = os.path.join(_get_app_data_dir(), ".env")
    if os.path.exists(appdata_env):
        load_dotenv(dotenv_path=appdata_env)
        return

    # Priority 2: Adjacent to the executable (portable mode)
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        portable_env = os.path.join(exe_dir, ".env")
        if os.path.exists(portable_env):
            load_dotenv(dotenv_path=portable_env)
            return

    # Priority 3: Project root (development fallback)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    dev_env = os.path.join(project_root, ".env")
    if os.path.exists(dev_env):
        load_dotenv(dotenv_path=dev_env)


if __name__ == "__main__":
    _setup_env()

    # Now import and run the server (config.py will pick up the env vars)
    import uvicorn
    from src.backend.server import app

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8321,
        log_level="info",
    )
