"""Unit tests for hermes_cli.official_source Root resolution."""

from __future__ import annotations

import json
from pathlib import Path

from hermes_cli.official_source import (
    official_urls_from_source,
    read_official_source,
    resolve_hermes_root,
)


def test_resolve_root_when_home_is_root(tmp_path: Path):
    root = tmp_path / "hermes"
    root.mkdir()
    assert resolve_hermes_root(root) == root.resolve()


def test_resolve_root_when_home_is_profile(tmp_path: Path):
    root = tmp_path / "hermes"
    profile = root / "profiles" / "work"
    profile.mkdir(parents=True)
    assert resolve_hermes_root(profile) == root.resolve()


def test_read_official_source_from_profile_home(tmp_path: Path):
    root = tmp_path / "hermes"
    profile = root / "profiles" / "default"
    profile.mkdir(parents=True)
    payload = {
        "schemaVersion": 1,
        "installUrl": "http://git.superic.com/aiplatform/hermes-agent.git",
        "originUrls": {
            "http": "http://git.superic.com/aiplatform/hermes-agent.git",
            "https": None,
            "ssh": None,
        },
    }
    (root / "official-source.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    data = read_official_source(profile)
    assert data is not None
    assert data["installUrl"].startswith("http://git.superic.com/")
    urls = official_urls_from_source(data)
    assert "http://git.superic.com/aiplatform/hermes-agent.git" in urls
    assert None not in urls
