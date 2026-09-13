"""Integrity checks for the published agent skill and its docs mirror."""

from __future__ import annotations

import json
from pathlib import Path

from billing_engine import __version__

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skill" / "SKILL.md"
DOCS_COPIES = (
    ROOT / "docs" / "public" / "skill" / "billing-engine-skill.txt",
    ROOT / "docs" / "src" / "assets" / "billing-engine-skill.txt",
)
PACKAGE = ROOT / "skill" / "package.json"


def test_skill_is_mirrored_into_docs() -> None:
    assert SKILL.exists(), "canonical skill is missing"
    expected = SKILL.read_text(encoding="utf-8")
    for copy in DOCS_COPIES:
        assert copy.exists(), f"docs copy missing at {copy}; run scripts/sync_skill.py"
        assert copy.read_text(encoding="utf-8") == expected


def test_skill_has_valid_frontmatter() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    frontmatter = text.split("---", 2)[1]
    assert "name: billing-engine" in frontmatter
    assert "description:" in frontmatter
    assert "[start:docs]" in text and "[end:docs]" in text


def test_npm_package_is_publishable() -> None:
    data = json.loads(PACKAGE.read_text(encoding="utf-8"))
    assert data["name"] == "billing-engine-skill"
    assert data["version"] == __version__
    assert data["license"] == "MIT"
    assert "SKILL.md" in data["files"]

    binary = data["bin"]["billing-engine-skill"]
    entry = PACKAGE.parent / binary
    assert entry.exists(), f"bin entry {binary} does not exist"
    assert entry.read_text(encoding="utf-8").startswith("#!/usr/bin/env node")
