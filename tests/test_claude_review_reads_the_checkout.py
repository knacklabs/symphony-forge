"""A review on Claude can read the whole review checkout, read-only, as a Codex review can."""
from __future__ import annotations

import json
import sys

import conftest
from test_close import PIN, report, env  # noqa: F401  (env is a fixture)
from test_fix_reviews_always_run_on_codex_so_a_team_wi import _claude_only

STORY = "code-reviews-on-claude-see-only-the-diff"

# The pinned helper starts Claude in an empty folder, with web search as its only tool.
HELPER = '''#!{python}
import json, subprocess, sys, tempfile
args = sys.argv[1:]
claude = args[args.index("--claude-bin") + 1] if "--claude-bin" in args else "claude"
subprocess.run([claude, "--safe-mode", "--setting-sources", "user", "--strict-mcp-config",
                "--disallowedTools", "mcp__*", "--print", "--no-session-persistence",
                "--tools", "WebSearch", "--allowedTools", "WebSearch"],
               cwd=tempfile.mkdtemp(), input="Review the change.", text=True, check=True)
with open(args[args.index("--json-output") + 1], "w", encoding="utf-8") as out:
    json.dump({report!r}, out)
'''

# The real claude: records its arguments and what its working folder holds.
CLAUDE = '''#!{python}
import json, os, pathlib, sys
log = pathlib.Path(__file__).resolve().parent / "claude-review-calls.jsonl"
with open(log, "a", encoding="utf-8") as calls:
    calls.write(json.dumps({{"args": sys.argv[1:], "files": sorted(os.listdir("."))}}) + "\\n")
'''


def test_a_claude_review_starts_with_read_access_to_the_checkout_and_nothing_more(
        env, tmp_path, monkeypatch):
    toml = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", toml.read_text("utf-8")
               + '\n[models.grill.claude]\nmodel = "opus"\neffort = "high"\n')
    env.repo.git("push", "-q", "origin", "main")
    _claude_only(tmp_path, monkeypatch, env.repo.bin,
                 HELPER.format(python=sys.executable, report=report()))
    conftest._install(env.repo.bin, "claude", CLAUDE.format(python=sys.executable))
    item, _ = env.start_fix({"app.py": "print('hello')\n"})
    env.open_pr("Readme greets new readers")

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    [call] = [json.loads(line) for line in
              (env.repo.bin / "claude-review-calls.jsonl").read_text("utf-8").splitlines()]
    # Claude works in the review checkout of the branch head, so unchanged files are there too.
    assert {"app.py", "README.md", "forge.toml"} <= set(call["files"])
    args = call["args"]
    tools = set(args[args.index("--tools") + 1].split(","))
    assert {"Read", "Grep", "Glob"} <= tools
    assert not tools & {"Bash", "Edit", "Write", "NotebookEdit", "default"}
    assert "Read" not in args[args.index("--allowedTools") + 1]
    # --restricted keeps the file tools inside the working folder and drops command tools.
    assert "--restricted" in args
