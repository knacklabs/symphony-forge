"""forge close <item> --show prints the saved review in full and runs nothing."""
import json
import sys

import pytest
import conftest
from test_close import blocked, env, finding  # noqa: F401

STORY = "FORGE-FINDINGS-1"


def _git_facts(env, where):
    fetch = env.repo.path / ".git" / "FETCH_HEAD"
    return (len(env.review_calls()), len(env.gh.calls()), env.repo.git("rev-parse", "HEAD", cwd=where),
            env.repo.git("status", "--porcelain", cwd=where),
            fetch.stat().st_mtime_ns if fetch.exists() else None)


@pytest.mark.parametrize("kind", ["task", "fix"])
def test_1_close_show_prints_saved_findings_in_full_and_runs_nothing(env, kind):
    marker = env.tmp / "tests-ran"
    conftest._install(env.repo.bin, "client-tests", f'''#!{sys.executable}
with open({json.dumps(marker.as_posix())}, "a", encoding="utf-8") as out:
    out.write("ran\\n")
''')
    settings = (env.repo.path / "forge.toml").read_text("utf-8")
    env.commit(env.repo.path, "forge.toml", settings + '\ntest = "client-tests"\ntest_place = "local"\n')
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_task() if kind == "task" else env.start_fix()

    missing = env.repo.forge("close", item, "--show", cwd=where)
    assert missing.returncode != 0
    assert f"This checkout has no saved review of {item}." in missing.stderr
    assert "Next:" in missing.stderr

    # A fix stops for the owner at its first blocking P1 and takes no dismissal then; a P0 never does.
    top = "P1" if kind == "task" else "P0"
    p1 = finding(top, "The greeting is missing")
    p1["body"] = "\n\n".join(f"Paragraph {n}: " + "the greeting has no text. " * 6 for n in range(40))
    assert p1["body"].count("\n") >= 40 and len(p1["body"]) > 4000
    p2 = finding("P2", "The greeting is plain")
    p2["body"] = "Gain 2, Work 1, Harm 1\nShort note."
    env.reviews(blocked(p1, p2))
    assert env.close(item).returncode == 1

    lines = marker.read_text("utf-8").count("\n")
    before = _git_facts(env, where)
    shown = env.repo.forge("close", item, "--show", cwd=where)
    assert shown.returncode == 0, shown.stdout + shown.stderr
    for text in ("Review: blocked.", f"1. {top} The greeting is missing (app.py:1)", "Open: blocks the merge.",
                 p1["body"], "2. P2 The greeting is plain (app.py:1)", "Open: does not block the merge."):
        assert text in shown.stdout, text
    assert marker.read_text("utf-8").count("\n") == lines
    assert _git_facts(env, where) == before

    env.commit(where, "other.py", "value = 1\n")  # a repair, so close reviews again
    dismissed = env.close(item, "--dismiss", "1", "--because", "app.py:1 the greeting exists")
    assert dismissed.returncode in (0, 1), dismissed.stdout + dismissed.stderr
    shown = env.repo.forge("close", item, "--show", cwd=where)
    assert "Dismissed: app.py:1 the greeting exists." in shown.stdout
    assert p1["body"] in shown.stdout
