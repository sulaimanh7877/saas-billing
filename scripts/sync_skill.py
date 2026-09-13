"""Keep the docs copy of the agent skill in sync with its canonical source.

The canonical skill lives at ``skill/SKILL.md`` inside the npm package. The docs
site serves a byte-for-byte copy at
``docs/assets/skill/billing-engine-skill.txt`` so the "Use with a coding agent"
page can offer a one-click copy/download. (The ``.txt`` extension keeps MkDocs
from rendering it as a documentation page.)

Usage::

    python scripts/sync_skill.py           # write the docs copy
    python scripts/sync_skill.py --check    # fail if out of date (CI)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "skill" / "SKILL.md"
TARGET = ROOT / "docs" / "assets" / "skill" / "billing-engine-skill.txt"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero when the docs copy differs from the source",
    )
    args = parser.parse_args(argv)

    if not SOURCE.exists():
        print(f"error: canonical skill not found at {SOURCE}", file=sys.stderr)
        return 1

    content = read(SOURCE)
    if args.check:
        if not TARGET.exists() or read(TARGET) != content:
            print(
                f"error: {TARGET} is out of date; run 'python scripts/sync_skill.py'",
                file=sys.stderr,
            )
            return 1
        print("skill docs copy is up to date")
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(content, encoding="utf-8")
    print(f"synced {SOURCE.relative_to(ROOT)} -> {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
