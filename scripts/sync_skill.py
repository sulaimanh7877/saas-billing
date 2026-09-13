"""Keep the docs copies of the agent skill in sync with its canonical source.

The canonical skill lives at ``skill/SKILL.md`` inside the npm package. The docs
site consumes byte-for-byte copies:

- ``docs/public/skill/billing-engine-skill.txt`` — served as a static file so the
  skill page can offer one-click copy/download.
- ``docs/src/assets/billing-engine-skill.txt`` — imported by the docs site to
  render the full skill source inline.

Usage::

    python scripts/sync_skill.py           # write the docs copies
    python scripts/sync_skill.py --check    # fail if out of date (CI)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "skill" / "SKILL.md"
TARGETS = (
    ROOT / "docs" / "public" / "skill" / "billing-engine-skill.txt",
    ROOT / "docs" / "src" / "assets" / "billing-engine-skill.txt",
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero when a docs copy differs from the source",
    )
    args = parser.parse_args(argv)

    if not SOURCE.exists():
        print(f"error: canonical skill not found at {SOURCE}", file=sys.stderr)
        return 1

    content = read(SOURCE)
    if args.check:
        stale = [target for target in TARGETS if not target.exists() or read(target) != content]
        if stale:
            for target in stale:
                print(f"error: {target.relative_to(ROOT)} is out of date", file=sys.stderr)
            print("run 'python scripts/sync_skill.py'", file=sys.stderr)
            return 1
        print("skill docs copies are up to date")
        return 0

    for target in TARGETS:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print(f"synced {SOURCE.relative_to(ROOT)} -> {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
