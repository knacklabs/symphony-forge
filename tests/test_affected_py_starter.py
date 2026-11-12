"""The Python starter selects checks through its generated command."""
import json
import shutil
import subprocess
import tomllib

import pytest

from test_setup import _fresh_client

STORY = "FORGE-AFFECTED-1"


@pytest.mark.platform
def _unix(text):
    # Windows prints corepack.cmd and backslash paths.
    return text.replace("\\", "/").replace("corepack.cmd ", "corepack ")


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
    scripts = json.loads((client / "package.json").read_text(encoding="utf-8"))["scripts"]
    # The last field is every `pnpm run <script>` the list prints, in order. A compatible API change
    # must end at the real browser script, so a typo such as `test:browser-typo` fails here.
    cases = (
        ("apps/api/app/projects/service.py",
         ("Affected parts: api, web", "api-types", "ruff", "mypy", "test:imports", "test:api", "tsc --build",
          "test:browser", "libs/shared/api-types/tsconfig.json", "libs/history/contracts/tsconfig.json",
          "libs/projects/contracts/tsconfig.json", "apps/web/tsconfig.json"), (),
         ["api-types", "test:imports", "test:api", "test:browser"]),
        ("apps/web/src/index.css", ("api-types", "eslint", "tsc --build", "vitest run", "--changed", "test:browser"),
         ("test:api", "ruff", "mypy"), ["api-types", "test:browser"]),
        ("libs/shared/util/src/index.ts", ("eslint", "tsc --build", "vitest run", "test:browser"),
         ("test:api", "ruff"), ["api-types", "test:browser"]),
        ("package.json", ("Affected parts: all", "pnpm test"), (), []),
    )
    for relative, expected, absent, ran in cases:
        path = client / relative
        original = path.read_bytes()
        path.write_bytes(original + b"\n")
        result = subprocess.run([node, "scripts/test.mjs", "--list", base], cwd=client,
                                capture_output=True, text=True, timeout=30)
        out = _unix(result.stdout)
        path.write_bytes(original)
        assert result.returncode == 0, out + result.stderr
        for command in expected:
            assert command in out, out
        for command in absent:
            assert command not in out, out
        if "tsc --build" in expected:
            assert out.index("api-types") < out.index("tsc --build"), out
        named = [line.rsplit(" ", 1)[1] for line in out.splitlines()
                 if line.startswith("corepack pnpm run ")]
        assert named == ran, out
        assert all(name in scripts for name in named), (named, sorted(scripts))
    for args, expected in ((["--list"], "Affected parts: all"),
                           (["--list", base], "Affected parts: none")):
        result = subprocess.run([node, "scripts/test.mjs", *args], cwd=client,
                                capture_output=True, text=True, timeout=30)
        out = _unix(result.stdout)
        assert result.returncode == 0, out + result.stderr
        assert expected in out

    # New unstaged tests must select their part, alone or alongside tracked
    # changes in the other part. The old cases above only changed tracked files,
    # so they could not catch Git diff omitting untracked files. This extends the
    # same real command boundary without adding a fake or production test seam.
    for new_file, tracked_file, expected, absent in (
        ("apps/api/tests/test_new.py", None, ("Affected parts: api", "test:api"), ("test:browser",)),
        ("apps/web/src/new.test.ts", None, ("Affected parts: web", "vitest run", "test:browser"), ("test:api",)),
        ("apps/api/tests/test_new.py", "apps/web/src/index.css",
         ("Affected parts: api, web", "test:api", "test:browser"), ()),
        ("apps/web/src/new.test.ts", "apps/api/app/projects/service.py",
         ("Affected parts: api, web", "test:api", "test:browser"), ()),
    ):
        new = client / new_file
        new.write_text("def test_new():\n    assert False\n" if new.suffix == ".py" else
                       "throw new Error('new failing test');\n", encoding="utf-8")
        tracked = client / tracked_file if tracked_file else None
        original = tracked.read_bytes() if tracked else None
        if tracked:
            tracked.write_bytes(original + b"\n")
        try:
            result = subprocess.run([node, "scripts/test.mjs", "--list", base], cwd=client,
                                    capture_output=True, text=True, timeout=30)
            out = _unix(result.stdout)
            assert result.returncode == 0, out + result.stderr
            for command in expected:
                assert command in out, out
            for command in absent:
                assert command not in out, out
        finally:
            new.unlink()
            if tracked:
                tracked.write_bytes(original)
