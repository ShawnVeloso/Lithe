"""
Lithe — Heuristic Graph (Phase 3: The Heuristic Graph)

Maps file paths to semantic category tags based on folder structure
and file extensions. This gives the AI instant context about project
structures before the user even asks a question.

This module is a pure-function engine with no side effects and no
database access. It takes a file path and returns a category string.
"""

import os

# ---------------------------------------------------------------------------
# Folder-based rules (checked in order — first match wins)
# ---------------------------------------------------------------------------
# Each tuple is (folder_pattern, category_tag). Patterns are matched
# case-insensitively against the normalized (forward-slash) path.
_FOLDER_RULES: list[tuple[str, str]] = [
    ("/src/backend/",    "Backend Logic"),
    ("/backend/",        "Backend Logic"),
    ("/src/frontend/",   "Frontend UI"),
    ("/frontend/",       "Frontend UI"),
    ("/src/cli/",        "CLI Orchestration"),
    ("/cli/",            "CLI Orchestration"),
    ("/tests/",          "Test Suite"),
    ("/test/",           "Test Suite"),
    ("/docs/",           "Documentation"),
    ("/documentation/",  "Documentation"),
    ("/data/",           "Data / Datasets"),
    ("/datasets/",       "Data / Datasets"),
    ("/scripts/",        "Automation Scripts"),
    ("/config/",         "Configuration"),
    ("/configs/",        "Configuration"),
    ("/models/",         "Models"),
    ("/notebooks/",      "Notebooks"),
    ("/lib/",            "Libraries"),
    ("/libs/",           "Libraries"),
    ("/utils/",          "Utilities"),
    ("/helpers/",        "Utilities"),
    ("/api/",            "API Layer"),
    ("/assets/",         "Static Assets"),
    ("/static/",         "Static Assets"),
    ("/public/",         "Static Assets"),
]

# ---------------------------------------------------------------------------
# Extension-based fallback rules (used when no folder pattern matches)
# ---------------------------------------------------------------------------
_EXTENSION_RULES: dict[str, str] = {
    # Data formats
    ".csv":     "Data / Datasets",
    ".xlsx":    "Data / Datasets",
    ".xls":     "Data / Datasets",
    ".parquet": "Data / Datasets",
    ".feather": "Data / Datasets",
    ".arrow":   "Data / Datasets",
    # Notebooks
    ".ipynb":   "Notebooks",
    # Documentation
    ".md":      "Documentation",
    ".txt":     "Documentation",
    ".rst":     "Documentation",
    ".pdf":     "Documentation",
    # Python
    ".py":      "Python Script",
    # JavaScript / TypeScript
    ".ts":      "JavaScript / TypeScript",
    ".tsx":     "JavaScript / TypeScript",
    ".js":      "JavaScript / TypeScript",
    ".jsx":     "JavaScript / TypeScript",
    # Web
    ".css":     "Stylesheet",
    ".html":    "Web Page",
    # Database
    ".sql":     "Database",
    ".db":      "Database",
    # Configuration
    ".json":    "Configuration",
    ".yaml":    "Configuration",
    ".yml":     "Configuration",
    ".toml":    "Configuration",
    ".ini":     "Configuration",
    ".env":     "Configuration",
}


def categorize_path(file_path: str) -> str:
    """Categorize a file based on its location in the directory tree.

    Tries folder-based rules first (most specific), then falls back
    to extension-based rules. Returns an empty string if no rule matches.

    Args:
        file_path: The absolute file path to categorize.

    Returns:
        A human-readable category tag (e.g., "Backend Logic"),
        or "" if no rule matched.
    """
    # Normalize to forward slashes for consistent pattern matching
    normalized = file_path.replace("\\", "/").lower()

    # 1. Folder-based rules (first match wins)
    for pattern, category in _FOLDER_RULES:
        if pattern in normalized:
            return category

    # 2. Extension-based fallback
    _, ext = os.path.splitext(file_path)
    if ext:
        return _EXTENSION_RULES.get(ext.lower(), "")

    return ""
