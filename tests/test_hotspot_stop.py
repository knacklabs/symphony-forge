STORY = "FORGE-SPOTTED-1"

import json
import shutil
from pathlib import Path

import pytest

from test_close import CLEAN, ROOT, STORY_DOC, blocked, body, env, finding  # noqa: F401
from test_fix_reviews_always_run_on_codex_so_a_team_wi import _claude_only
from test_setup import _fresh_client


STOP_SENTENCE = (
    "When close stops an item because a file keeps breaking, start the fix it prints without "
    "asking the owner, run no more `forge work` on that item, and run `forge close <item>` again "
    "only after that fix merges."
)


def seed(env, path):
    env.repo.write(path, "pass\n")
    env.repo.git("add", "--", path)
    env.repo.git("commit", "-q", "-m", "Existing code")
    env.repo.git("push", "-q", "origin", "main")


def saved(where, item):
    path = (f".factory/stories/SHOP/tasks/{item.split('/')[-1]}.json" if "/" in item
            else f".factory/fixes/{item}.json")
    return json.loads((where / path).read_text())


def rounds(env, item, where, paths):
    for number, path in enumerate(paths, 1):
        env.reviews(blocked(finding("P1", f"Round {number} defect", path)))
        env.commit(where, "app.py", f"print({number})\n")
        result = env.close(item)
        assert result.returncode == 1, result.stdout + result.stderr
        if number < len(paths):
            assert "The review left serious findings open:" in result.stderr
    return result


def _third_review_stops_once_and_next_close_reviews_unchanged_code(env, kind):
    # The CLI owns the stop, committed state, push, draft PR, next step and resumed review.
    # Only GitHub and Autoreview responses are faked; no fake decides when Forge stops.
    seed(env, "src/a.py")
    seed(env, "src/z.py")
    item, where = env.start_approved_task(STORY_DOC) if kind == "task" else env.start_fix()
    rounds(env, item, where, ["src/a.py", "src/z.py"])
    env.reviews(blocked(finding("P1", "Repeated Z defect", "src/z.py"),
                        finding("P1", "Repeated A defect", "src/a.py")))
    env.commit(where, "app.py", "print(3)\n")
    result = env.close(item)
    engine = "claude" if kind == "fix-claude" else "codex"
    for call in env.review_calls():
        assert call["args"][call["args"].index("--engine") + 1] == engine
    why = f"Simplify src/a.py before {item} carries on"
    done = "src/a.py is simpler and behaves as it did before"
    command = f'forge fix start "{why}" --done "{done}", then forge close {item} once that fix merges'
    assert result.returncode == 1
    assert result.stderr.splitlines()[-2:] == [
        f"Review round 3 of {item} still finds serious problems in src/a.py, which an earlier "
        "round flagged too, so Forge stops sending the worker back.", "Next: " + command]
    state = saved(where, item)
    assert state["status"] == "hotspot"
    assert state["stop"] == {"file": "src/a.py", "why": why, "done": done}
    assert state["flagged"] == ["src/a.py", "src/z.py"]
    assert env.repo.git("log", "-1", "--format=%s", cwd=where) == (
        f"Review of {item}: blocked; src/a.py keeps breaking")
    assert env.repo.git("rev-parse", "HEAD", cwd=where) == env.repo.git(
        "rev-parse", state["branch"], cwd=env.tmp / "remote.git")
    creates = env.gh_calls("pr", "create")
    assert all("--draft" in call for call in creates)
    env.open_pr(body(creates[-1]), draft=True)
    next_result = env.repo.forge("next")
    label = item if kind == "task" else "The fix tidy-readme"
    assert f"Close stopped {label}: src/a.py keeps breaking, so a fix that simplifies it goes first." in next_result.stdout
    assert "Next: " + command in next_result.stdout
    assert all(finding["title"] not in result.stderr for finding in state["review"]["findings"])

    if kind == "fix-claude":
        calls = len(env.review_calls())
        env.reviews(CLEAN)
        resumed = env.close(item)
        assert resumed.returncode == 0, resumed.stderr
        assert f"{item} carries on after the stop for src/a.py." in resumed.stdout
        assert len(env.review_calls()) == calls + 1
        assert saved(where, item)["status"] == "waiting for checks"
        env.commit(where, "app.py", "print(4)\n")
        env.reviews(blocked(finding("P1", "Still broken", "src/a.py")))
        later = env.close(item)
        assert later.returncode == 1
        assert "The review left serious findings open:" in later.stderr
        assert saved(where, item)["stop"] == state["stop"]
        return

    # Resume deliberately needs no new worker commit and does not check for a merged fix.
    for answer, expected in [(blocked(finding("P1", "Still broken", "src/a.py")), "fixing"),
                             (CLEAN, "waiting for checks")]:
        if expected == "waiting for checks":
            env.commit(where, "app.py", "print(4)\n")
        calls = len(env.review_calls())
        env.reviews(answer)
        resumed = env.close(item)
        assert len(env.review_calls()) == calls + 1
        assert saved(where, item)["status"] == expected
        assert saved(where, item)["stop"] == state["stop"]
        if expected == "fixing":
            assert f"{item} carries on after the stop for src/a.py." in resumed.stdout
            assert resumed.returncode == 1
            assert "The review left serious findings open:" in resumed.stderr
            assert "Forge stops sending" not in resumed.stderr
        else:
            assert resumed.returncode == 0, resumed.stderr


def _other_blocked_reviews_keep_the_existing_refusal(env, paths, on_default):
    if on_default:
        for path in sorted(set(paths)):
            seed(env, path)
    item, where = env.start_fix()
    if not on_default:
        env.commit(where, paths[0], "pass\n")
    result = rounds(env, item, where, paths)
    assert "The review left serious findings open:" in result.stderr
    assert saved(where, item)["status"] == "fixing"
    assert "stop" not in saved(where, item)


def _carried_dismissal_cannot_stop_the_third_review(env):
    seed(env, "src/a.py")
    item, where = env.start_fix()
    defect = blocked(finding("P1", "Dismissed defect", "src/a.py"))
    env.reviews(defect)
    assert env.close(item).returncode == 1
    assert env.close(item, "--dismiss", "1", "--because", "src/a.py:1 Proven safe").returncode == 0
    for number in (2, 3):
        env.commit(where, "app.py", f"print({number})\n")
        env.reviews(defect)
        result = env.close(item)
        assert result.returncode == 0, result.stderr
    state = saved(where, item)
    assert len([step for step in state["steps"] if step["step"] == "review"]) == 3
    assert "stop" not in state


def _new_and_previously_adopted_clients_get_stop_guidance(repo, gh, tmp_path, previous):
    if previous:
        shutil.copytree(Path(__file__).parent / "fixtures/adopted-v1.2.2/client",
                        repo.path, dirs_exist_ok=True)
        repo.git("checkout", "-q", "-b", "fix/stop-guide")
        version = repo.forge("--version").stdout.split()[-1]
        config = (repo.path / "forge.toml").read_text()
        repo.write("forge.toml", config.replace('version = "v1.2.2"', f'version = "{version}"'))
        client, result = repo.path, repo.forge("sync")
    else:
        client, result = _fresh_client(repo, gh, tmp_path)
    assert result.returncode == 0, result.stderr
    root = Path(__file__).parents[1]
    for path in [root / "src/forge/templates/skill.md",
                 *[top / host / "skills/forge/SKILL.md"
                   for top in (root, client) for host in (".claude", ".codex")]]:
        hotspot = path.read_text().split("## Hotspots\n", 1)[1].split("## Check-back", 1)[0]
        assert STOP_SENTENCE in " ".join(hotspot.split())


@pytest.mark.parametrize("case,details", [
    *[(_third_review_stops_once_and_next_close_reviews_unchanged_code, (kind,))
      for kind in ("fix", "task", "fix-claude")],
    *[(_other_blocked_reviews_keep_the_existing_refusal, details) for details in (
        (["src/a.py", "src/b.py", "src/c.py"], True),
        (["src/a.py", "src/a.py"], True),
        (["src/branch.py"] * 3, False),
        (["src/$cache.py"] * 3, True))],
    (_carried_dismissal_cannot_stop_the_third_review, ()),
    *[(_new_and_previously_adopted_clients_get_stop_guidance, (previous,))
      for previous in (False, True)],
])
def test_5_review_loop_stops_once_then_carries_on(env, repo, gh, tmp_path, monkeypatch, case, details):
    if details == ("fix-claude",):
        _claude_only(tmp_path, monkeypatch, repo.bin,
                     (ROOT / "tests/stubs/autoreview").read_text())
    if case == _new_and_previously_adopted_clients_get_stop_guidance:
        case(repo, gh, tmp_path, *details)
    else:
        case(env, *details)
