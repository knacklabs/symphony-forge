"""The prototype build gate and light review are observable through forge commands.

Test audit:
1. Protect close's decision gate, light prompt and model choice, plus the security floor.
2. Regressions: app changes close without owner acceptance; light review runs full checks or the
   wrong model; a security finding below the usual bar passes; docs-only work or an adopted build
   gets blocked.
3. No existing test owns these close outcomes. Each test reaches the real forge close or decision
   command; the existing close fixture fakes only GitHub and Autoreview.
4. No production seam is added. The test observes close output, the decision record and the prompt
   sent to Autoreview.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import pytest

import conftest
from test_close import GREEN, blocked, env  # noqa: F401
from test_story import prototype_design

STORY = "FORGE-PACE-1"


def _prototype(env, *, adopted: bool = False, design: bool = False,
               existing_app: bool = False, model_settings: str = "",
               test_command: str = "") -> None:
    repo = env.repo
    version = repo.forge("--version").stdout.split()[-1]
    repo.git("switch", "-q", "-c", "fix/prototype-setup")
    if adopted:
        shutil.copytree(conftest.ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
    config = (repo.path / "forge.toml").read_text("utf-8")
    config = re.sub(r"^version\s*=.*$", f'version = "{version}"', config, flags=re.M)
    config = re.sub(r"^(?:repo|stage)\s*=.*\n", "", config, flags=re.M)
    top_level = '\nrepo = "client"\nstage = "prototype"\n' + model_settings + "\n"
    if test_command:
        encoded_command = json.dumps(test_command)
        top_level += f"test = {encoded_command}\nfast_test = {encoded_command}\n"
    section = re.search(r"(?m)^\s*\[", config)
    if section:
        config = config[:section.start()].rstrip() + "\n" + top_level + config[section.start():]
    else:
        config += top_level
    repo.write("forge.toml", config)
    # These are init's empty-repo scaffold, not a merged app build.
    repo.write("Dockerfile", "FROM python:3.11-slim\n")
    repo.write(".dockerignore", "__pycache__/\n")
    if design:
        prototype_design(repo)
    if existing_app:
        repo.write("app.py", "print('merged prototype')\n")
    if adopted:
        repo.write(".factory/fixes/prototype-setup.json", json.dumps({
            "kind": "fix", "status": "working", "branch": "fix/prototype-setup",
            "why": "Set up the adopted prototype", "done_when": "The prototype is configured",
        }))
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Set up prototype")
    _publish_main(repo, "fix/prototype-setup")


def _publish_main(repo, branch: str, *, cwd: Path | None = None) -> None:
    cwd = cwd or repo.path
    repo.git("push", "-q", "origin", f"HEAD:refs/heads/{branch.removeprefix('fix/')}", cwd=cwd)
    remote = Path(repo.git("remote", "get-url", "origin"))
    head = repo.git("rev-parse", "HEAD", cwd=cwd)
    repo.git("update-ref", "refs/heads/main", head, cwd=remote)
    repo.git("fetch", "-q", "origin", "main")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", branch)


def _accept_build_decision(repo) -> Path:
    started = repo.forge("fix", "start", "Record the prototype build request",
                         "--done", "The owner accepts the prototype build request",
                         "--kind", "mechanical")
    assert started.returncode == 0, started.stdout + started.stderr
    where = Path(started.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    branch = "fix/record-the-prototype-build-request"
    proposed = repo.forge("decision", "new", "prototype-build", cwd=where)
    assert proposed.returncode == 0, proposed.stdout + proposed.stderr
    page = next((where / "docs/decisions").glob("*prototype-build.md"))
    text = page.read_text("utf-8")
    for placeholder, answer in (
        ("<!-- Why this decision was needed; the forces at play. -->",
         "The canvas cannot prove that demo responses keep one user's records private."),
        ("<!-- What was decided, in one or two sentences. -->",
         "Build a working prototype to verify the demo's data boundary."),
        ("<!-- What follows: tradeoffs accepted, doors closed, work implied. -->",
         "Test the demo steps and verify that data does not leak or disappear."),
    ):
        text = text.replace(placeholder, answer)
    page.write_text(text, encoding="utf-8")
    repo.git("add", page.relative_to(where).as_posix(), cwd=where)
    repo.git("commit", "-q", "-m", "Explain the prototype build request", cwd=where)
    accepted = repo.forge("decision", "accept", "prototype-build", "--by", "A Client", cwd=where)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    _publish_main(repo, branch, cwd=where)
    assert "status: accepted" in page.read_text("utf-8")
    return page


def _start_fix(env, *, kind: str = "backend", path: str = "app.py",
               demo_steps: bool = False, stack_marker: str | None = None) -> tuple[str, Path]:
    repo = env.repo
    started = repo.forge("fix", "start", "Build the demo workflow", "--done", "The demo works",
                         "--kind", kind)
    assert started.returncode == 0, started.stdout + started.stderr
    where = Path(started.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    if stack_marker:
        contents = {
            "pyproject.toml": '[project]\nname = "prototype-demo"\nversion = "0.1.0"\n',
            "go.mod": "module example.com/prototype-demo\n\ngo 1.22\n",
        }[stack_marker]
        env.commit(where, stack_marker, contents, "Choose the app stack")
    app = ("import sys\nfrom pathlib import Path\n"
           "basket = Path(sys.argv[2])\n"
           "if sys.argv[1] == 'save':\n"
           "    basket.write_text('bread', encoding='utf-8')\n"
           "    print('basket saved')\n"
           "else:\n"
           "    print(basket.read_text(encoding='utf-8'))\n" if demo_steps
           else "print('demo workflow')\n")
    env.commit(where, path, app, "Build the demo workflow")
    if demo_steps:
        env.commit(where, "tests/test_demo_steps.py",
                   "import subprocess\nimport sys\n\n\n"
                   "def test_demo_steps_survive_reopen(tmp_path):\n"
                   "    path = str(tmp_path / 'basket.txt')\n"
                   "    for step, expected in [('save', 'basket saved'), ('show', 'bread'), ('show', 'bread')]:\n"
                   "        result = subprocess.run([sys.executable, 'app.py', step, path], "
                   "capture_output=True, text=True)\n"
                   "        assert result.returncode == 0, result.stderr\n"
                   "        assert result.stdout.strip() == expected\n",
                   "Prove the demo steps\n\nProof list: Done-when item 3: "
                   "tests/test_demo_steps.py exercises the demo flow.")
    return "build-the-demo-workflow", where


@pytest.mark.parametrize("stack_marker", [None, "pyproject.toml", "go.mod"],
                         ids=["without-stack-marker", "python-stack", "go-stack"])
def test_3_close_refuses_prototype_app_changes_until_the_owner_accepts_the_build(env, stack_marker):
    _prototype(env)
    item, _ = _start_fix(env, stack_marker=stack_marker)

    refused = env.close(item)
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "Next: forge decision new prototype-build" in refused.stderr
    assert env.review_calls() == []

    page = _accept_build_decision(env.repo)
    assert "canvas cannot prove" in page.read_text("utf-8")
    env.checks(GREEN)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr


def test_31_canvas_only_ui_fix_closes_without_a_build_decision(env):
    _prototype(env, design=True)
    item, _ = _start_fix(env, kind="ui", path="docs/design/prototype/notes.md")

    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert not list((env.repo.path / "docs/decisions").glob("*prototype-build.md"))


def test_32_adopted_prototype_with_merged_app_code_closes_without_a_new_decision(env):
    _prototype(env, adopted=True, existing_app=True)
    item, _ = _start_fix(env, path="app.py")

    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr


@pytest.mark.parametrize(("setting", "model", "effort"), [
    ("", "gpt-6.1-sol", "medium"),
    ('models.light_review = { model = "gpt-6-astra", effort = "high"}',
     "gpt-6-astra", "high"),
    ('models.light_review = { model = "gpt-6-astra"}', "gpt-6-astra", "medium"),
    ('models.light_review.codex = { model = "gpt-6-compact", effort = "low"}',
     "gpt-6-compact", "low"),
], ids=["review-model-at-medium", "light-review-setting", "light-model-at-medium", "codex-entry"])
def test_33_light_review_checks_only_demo_risks_and_uses_light_review_settings(
        env, setting: str, model: str, effort: str):
    demo_steps = model == "gpt-6.1-sol"
    test_command = (f'{json.dumps(Path(sys.executable).as_posix())} -m pytest -q tests/test_demo_steps.py'
                    if demo_steps else "")
    _prototype(env, existing_app=True,
               model_settings='models.review = { model = "gpt-6.1-sol", effort = "high"}\n'
                              + setting,
               test_command=test_command)
    _accept_build_decision(env.repo)
    item, _ = _start_fix(env, demo_steps=demo_steps)
    env.checks(GREEN)

    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    [call] = env.review_calls()
    args = call["args"]
    assert args[args.index("--model") + 1] == f"codex={model}"
    assert args[args.index("--thinking") + 1] == f"codex={effort}"
    prompts = "\n".join(call["prompt_files"].values()).casefold()
    assert "demo breakage" in prompts
    assert "security" in prompts
    assert "data loss" in prompts
    assert "simpler:" not in prompts
    assert "per-function" not in prompts


def test_34_security_finding_blocks_a_light_prototype_review(env):
    _prototype(env, existing_app=True)
    _accept_build_decision(env.repo)
    item, _ = _start_fix(env)
    security = {
        "title": "Demo response exposes another user's records",
        "body": "Gain 4, Work 2, Harm 1\nRaise: Security\n"
                "The response includes another user's private records.",
        "priority": "P1",
        "confidence": 0.9,
        "category": "bug",
        "code_location": {"file_path": "app.py", "line": 1, "column": 1},
    }
    env.reviews(blocked(security))
    env.checks(GREEN)

    closed = env.close(item)
    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "Demo response exposes another user's records" in closed.stdout + closed.stderr
