"""Smoke-test the runnable scenario examples end to end."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_EXAMPLES = sorted(_ROOT.joinpath("examples").glob("scenario_*.py"))


@pytest.mark.parametrize("example", _EXAMPLES, ids=[path.stem for path in _EXAMPLES])
def test_scenario_example_runs(example: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(example)],
        capture_output=True,
        text=True,
        cwd=_ROOT,
        check=False,
    )
    assert result.returncode == 0, f"{example.name} failed:\n{result.stdout}\n{result.stderr}"
