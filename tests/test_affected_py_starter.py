"""The Python starter selects checks through its generated command."""
import shutil
import subprocess
import tomllib

import pytest

from test_setup import _fresh_client

STORY = "FORGE-AFFECTED-1"


@pytest.mark.platform
def test_6_python_starter_selects_its_affected_parts(repo, gh, tmp_path):
    # Contract: init's command selects API, web and library checks. A full-only
    # script would run unrelated suites. Existing tests do not run Python list
    # mode. Real init and git own this boundary; no fake or test seam is needed.
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for generated starter selection")
    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", "python")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    settings = tomllib.loads((client / "forge.toml").read_text(encoding="utf-8"))
    assert settings["test"] == "node scripts/test.mjs"
    assert settings["fast_test"] == "node scripts/test.mjs {base}"
    # Fail before the old script can install dependencies.
    assert (client / "scripts/affected.mjs").is_file()
    base = repo.git("rev-parse", "HEAD", cwd=client)
    cases = (
        ("apps/api/app/projects/service.py", ("api-types", "ruff", "mypy", "test:imports", "test:api"),
         ("eslint", "vitest", "test:browser")),
        ("apps/web/src/index.css", ("eslint", "tsc --build", "vitest run", "--changed", "test:browser"),
         ("test:api", "ruff", "mypy")),
        ("libs/shared/util/src/index.ts", ("eslint", "tsc --build", "vitest run", "test:browser"),
         ("test:api", "ruff")),
        ("package.json", ("Affected parts: all", "pnpm test"), ()),
    )
    for relative, expected, absent in cases:
        path = client / relative
        original = path.read_bytes()
        path.write_bytes(original + b"\n")
        result = subprocess.run([node, "scripts/test.mjs", "--list", base], cwd=client,
                                capture_output=True, text=True, timeout=30)
        path.write_bytes(original)
        assert result.returncode == 0, result.stdout + result.stderr
        for command in expected:
            assert command in result.stdout, result.stdout
        for command in absent:
            assert command not in result.stdout, result.stdout
    for args, expected in ((["--list"], "Affected parts: all"),
                           (["--list", base], "Affected parts: none")):
        result = subprocess.run([node, "scripts/test.mjs", *args], cwd=client,
                                capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        assert expected in result.stdout
