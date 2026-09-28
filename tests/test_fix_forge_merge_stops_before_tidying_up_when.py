"""A refused Codex archive does not interrupt a completed Forge merge."""

import json

from test_codex_worker import sdk_data  # noqa: F401
from test_close import env  # noqa: F401
from test_merge_command import _archiving_codex, _merge_at_github, _ready

STORY = "forge-merge-stops-before-tidying-up-when"


def test_1_merge_finishes_cleanup_when_codex_refuses_an_archive(
        env, sdk_data, tmp_path, monkeypatch):
    item, where = _ready(env)
    stub = _archiving_codex(env.repo, sdk_data, tmp_path, monkeypatch)
    record = env.repo.path / ".git" / "forge" / "threads" / "fix" / f"{item}.log"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(''.join(json.dumps({"conversation": thread}) + "\n"
                              for thread in ("thr-one", "thr-two")), encoding="utf-8")
    head = env.repo.git("rev-parse", "HEAD", cwd=where)
    env.gh.respond("pr", "view", stdout=json.dumps({
        "number": 7, "state": "OPEN", "baseRefName": "main", "headRefOid": head,
        "headRefName": "fix/tidy-readme", "title": "Tidy readme", "isDraft": False}))
    _merge_at_github(env)
    monkeypatch.setenv("STUB_ARCHIVE_FAIL_THREAD", "thr-one")

    merged = env.repo.forge("merge", item)

    assert merged.returncode == 0, merged.stderr
    assert "thr-one" in merged.stdout
    assert "archive" in merged.stdout.lower() and "later" in merged.stdout.lower()
    calls = [json.loads(line) for line in stub.read_text("utf-8").splitlines()]
    assert [call["params"]["threadId"] for call in calls
            if call.get("method") == "thread/archive"] == ["thr-one", "thr-two"]
    assert env.repo.git("ls-remote", "--heads", "origin", "fix/tidy-readme") == ""
    assert not where.exists()
    assert "fix/tidy-readme" not in env.repo.git("branch", "--list", "fix/tidy-readme")
    assert not (env.repo.path / ".git" / "forge" / "ready" / f"{item}.json").exists()
