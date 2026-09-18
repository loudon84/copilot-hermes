"""Read Hermes Root ``official-source.json`` (enterprise distribution identity).

Path resolution (C-003 / A-OFFICIAL-001):
- If ``HERMES_HOME`` ends with ``profiles/<name>``, Root is the ancestor that
  contains ``profiles`` (i.e. parent of ``profiles``).
- Otherwise Root = ``HERMES_HOME``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional, Set


OFFICIAL_SOURCE_FILENAME = "official-source.json"


def resolve_hermes_root(hermes_home: Path) -> Path:
    """Return Hermes Root for official-source.json given an active home path."""
    home = Path(hermes_home).expanduser().resolve()
    parts = home.parts
    # Match .../profiles/<name> (case-insensitive on the profiles segment).
    if len(parts) >= 2 and parts[-2].lower() == "profiles":
        return home.parent.parent
    return home


def official_source_path(hermes_home: Path) -> Path:
    return resolve_hermes_root(hermes_home) / OFFICIAL_SOURCE_FILENAME


def read_official_source(hermes_home: Path) -> Optional[dict[str, Any]]:
    """Load official-source.json or return None if missing/unreadable."""
    path = official_source_path(hermes_home)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def official_urls_from_source(data: dict[str, Any]) -> Set[str]:
    """Collect non-null installUrl / originUrls entries from official-source data."""
    urls: Set[str] = set()
    install = data.get("installUrl")
    if isinstance(install, str) and install.strip():
        urls.add(install.strip())
    origin = data.get("originUrls")
    if isinstance(origin, dict):
        for value in origin.values():
            if isinstance(value, str) and value.strip():
                urls.add(value.strip())
    return urls


def get_active_hermes_home() -> Path:
    """Best-effort active Hermes home (env or default LOCALAPPDATA/hermes)."""
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "hermes"
    return Path.home() / ".hermes"
