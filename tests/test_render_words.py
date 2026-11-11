"""The words around the rendered check: the agent's steps, the review rule, the phone-view question.

Test audit:
1. Protect what a new client repo (init) and an earlier-adopted repo (sync) get for the rendered check,
   and that a sample-data prototype runs no rendered check before sign-off.
2. Credible regressions: a helper file that differs from the template, a skill without the `Phone view`
   row, a sync that touches app files or makes a missing answer refuse, a sample-data close that runs the
   test command.
3. test_render_check.py owns the check itself; no test owns these words or the sample-data path for it.
4. No production seam is needed.
"""
import re
import shutil
from pathlib import Path

import pytest

from conftest import ROOT
from test_app_constitution import _fixture_git
from test_close import CLEAN, GREEN, env  # noqa: F401
from test_sample_setup import _prepared_client, _settings
from test_setup import _fresh_client, _version

STORY = "FORGE-RENDER-1"
TEMPLATES = ROOT / "src/forge/templates"
CASES = [pytest.param(False, id="new client"), pytest.param(True, id="earlier adopted")]


def _text(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def _files(client: Path) -> dict[str, bytes]:
    return {p.relative_to(client).as_posix(): p.read_bytes() for p in client.rglob("*")
            if p.is_file() and ".git" not in p.relative_to(client).parts}


@pytest.mark.parametrize("adopted", CASES)
def test_4_new_and_existing_repos_get_the_rendered_check_and_the_phone_question(repo, gh, tmp_path, adopted):
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        client = repo.path
        config = client / "forge.toml"
        config.write_text(config.read_text("utf-8").replace("v1.2.2", _version(repo)), encoding="utf-8")
        repo.git("switch", "-qc", "fix/rendered-check")
        before = _files(client)
        doctor_before = repo.forge("doctor")
        next_before = repo.forge("next")
        made = repo.forge("sync")
    else:
        client, made = _fresh_client(repo, gh, tmp_path)
        before = {}
    assert made.returncode == 0, made.stdout + made.stderr
    for name in ("render-check.mjs", "render-check.d.mts"):
        assert (client / ".forge/design" / name).read_bytes() == (TEMPLATES / "design" / name).read_bytes()
    for host in (".claude", ".codex"):
        skill = _text(client / host / "skills/forge/SKILL.md")
        assert re.search(r"\| Phone view \| Does the app need a phone view\?", skill), host
        assert "A missing `Phone view` answer means desktop width only and refuses nothing" in skill
    brief, review = _text(TEMPLATES / "brief.md"), _text(TEMPLATES / "review.md")
    assert "add it to the render list beside the app's browser tests" in brief
    assert "Gate: rendered check" in review
    assert "checkScreen" in _text(TEMPLATES / "conventions/testing.md")
    if adopted:
        after = _files(client)
        assert {k: v for k, v in after.items() if k.startswith(("apps/", "libs/", "scripts/"))
                or k == "package.json"} == {k: v for k, v in before.items() if k.startswith(
                    ("apps/", "libs/", "scripts/")) or k == "package.json"}
        # Sync repairs old generated files, so it can only remove warnings; the answer's absence adds none.
        doctor_after = repo.forge("doctor")
        warnings = lambda done: {line for line in done.stdout.splitlines() if line.startswith("- ")}  # noqa: E731
        assert warnings(doctor_after) <= warnings(doctor_before)
        next_after = repo.forge("next")
        assert next_after.returncode == next_before.returncode
        assert "Phone view" not in next_after.stdout + next_after.stderr


@pytest.mark.parametrize("case", ["new client", "earlier adopted"])
def test_5_a_sample_data_prototype_runs_no_rendered_check_before_signoff(env, tmp_path, case):
    repo, gh = env.repo, env.gh
    marker = tmp_path / "test-results" / "render-ran"
    marker.parent.mkdir()
    top, config = _prepared_client(repo, gh, tmp_path, case, marker, "local")
    repo.write("docs/decisions/0000-prototype-build.md",
               '---\nstatus: accepted\nconfirmed_by: "Owner"\n---\n# Build the sample demo\n')
    repo.git("add", "-A")
    _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Enable the sample-data prototype")
    _fixture_git(repo, tmp_path, "push", "-q", "origin", "main")
    for sample, ran in ((True, False), (False, True)):
        if ran:
            _settings(config, sample_data=False)
            repo.git("add", "-A")
            _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Turn sample data off")
            _fixture_git(repo, tmp_path, "push", "-q", "origin", "main")
        name = f"Tidy {sample}"
        started = repo.forge("fix", "start", name, "--done", "The readme is ready", "--kind", "mechanical")
        assert started.returncode == 0, started.stdout + started.stderr
        item = re.sub(r"\W+", "-", name.lower())
        where = Path(re.search(r" in (.+)\n", started.stdout)[1])
        env.commit(where, "app.py", "print('screen')\n", "Add a screen")
        env.reviews(CLEAN)
        env.open_pr("")
        env.checks(GREEN)
        closed = env.close(item)
        assert closed.returncode == 0, closed.stdout + closed.stderr
        assert ("Sample-data mode skips tests and CI." in closed.stdout) is not ran
        assert marker.exists() is ran
