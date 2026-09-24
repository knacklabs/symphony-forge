"""Run one required pytest selector with local pytest or the uv fallback."""
from __future__ import annotations

import subprocess
import sys


def main(argv: list[str] | None = None) -> int:
    path, test_id, report = sys.argv[1:] if argv is None else argv
    selector = f"{path}::{test_id}"
    junit = f"--junitxml={report}"
    try:
        import pytest
    except ImportError:
        return subprocess.run([
            "uv", "run", "--python", "3.11", "--with", "pytest", "python",
            "-m", "pytest", selector, "-o", "junit_family=legacy", junit,
        ]).returncode
    return int(pytest.main([selector, "-o", "junit_family=legacy", junit]))


if __name__ == "__main__":
    raise SystemExit(main())
