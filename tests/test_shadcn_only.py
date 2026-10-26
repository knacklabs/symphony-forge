"""The shadcn-only close and review rules on new and upgraded client apps."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from test_close import CLEAN, GREEN, blocked, env, finding
from test_close import STORY_DOC
from test_score_notes import _client_repo as setup_client
from test_setup import _fresh_client
from test_worker import calls, install_claude


STORY = "FORGE-STARTER-1"

REVIEW_RULE = (
    "In an app with shadcn/ui set up (a `components.json`), report a new UI component that "
    "hand-builds what a shadcn/ui component or block already does as a P1 finding titled "
    "`shadcn: <the component>`, unless a `Not shadcn: <why>` comment at the component says why "
    "shadcn/ui cannot do it. A composite built from shadcn/ui components is not a finding, and "
    "neither is a library or component the default branch already has."
)
WORKER_RULE = (
    "In a client app with shadcn/ui set up, use shadcn/ui only. If the app has `libs/shared/ui`, "
    "add components with `npx shadcn@4.21.4 add <name> --cwd libs/shared/ui`. Close refuses a "
    "new UI component library and a new file outside the app's shadcn components folder "
    "(`libs/shared/ui/src/components/ui/` when it has that library) named like a shadcn/ui "
    "component. Review holds a hand-built UI component unless a `Not shadcn: <why>` comment "
    "says why."
)


def _commit_main(repo, tmp_path, message):
    hooks = tmp_path / "no-hooks"
    hooks.mkdir(exist_ok=True)
    repo.git("add", "-A")
    repo.git("-c", f"core.hooksPath={hooks}", "commit", "-q", "-m", message)
    repo.git("-c", f"core.hooksPath={hooks}", "push", "-q", "origin", "main")


def _shadcn_client(env, tmp_path, adopted):
    setup_client(env, tmp_path, adopted)
    repo = env.repo
    config = repo.path / ("components.json" if adopted else "libs/shared/ui/components.json")
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("{}\n", encoding="utf-8")
    ui = Path("apps/web/src/components/ui") if adopted else Path("libs/shared/ui/src/components/ui")
    button = repo.path / ui / "button.tsx"
    button.parent.mkdir(parents=True, exist_ok=True)
    button.write_text("export function Button() { return null; }\n", encoding="utf-8")
    if adopted:
        (repo.path / "package.json").write_text(
            json.dumps({"dependencies": {"antd": "^5.0.0"}}), encoding="utf-8")
    _commit_main(repo, tmp_path, "Set up shadcn/ui")
    env.checks(GREEN)
    return repo


def _fix(env, name, changes):
    state = {"kind": "fix", "why": "Keep the app on shadcn/ui", "done_when": "The app uses shadcn/ui"}
    return env.start(name, f"fix/{name}", f".factory/fixes/{name}.json", state, changes)


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_4_close_refuses_a_second_ui_library_and_shadcn_copies(env, tmp_path, adopted):
    # Audit: this protects close's component-folder rule in both the new and old app layouts.
    # A stale folder check could reject shadcn copies or allow hand-built component duplicates.
    # Existing cases cover the old path only; this adds the library path while keeping adoption.
    # The real Forge close command is the boundary, with no test-only seam.
    repo = _shadcn_client(env, tmp_path, adopted)
    screens = Path("apps/web/src/features/orders") if adopted else Path("libs/projects/web/src/pages/orders")
    button = screens / "Button.tsx"
    ui = Path("apps/web/src/components/ui") if adopted else Path("libs/shared/ui/src/components/ui")
    item, where = _fix(env, "shadcn-only", {
        "apps/web/package.json": json.dumps({"devDependencies": {"@mui/material": "^7.0.0"}}),
        button.as_posix(): "export function Button() { return null; }\n",
    })

    refused = env.close(item)
    output = refused.stdout + refused.stderr
    assert refused.returncode == 1, output
    assert "This app uses shadcn/ui only, and this change adds" in output
    assert "@mui/material" in output
    assert button.as_posix() in output
    assert "npx shadcn@4.21.4 add <name>" in output
    assert f"then forge close {item}" in output

    (where / button).unlink()
    (where / "apps/web/package.json").unlink()
    if adopted:
        (where / "package.json").write_text(
            json.dumps({"dependencies": {"antd": "^5.1.0"}}), encoding="utf-8")
    dialog = where / ui / "dialog.tsx"
    dialog.parent.mkdir(parents=True, exist_ok=True)
    dialog.write_text("export function Dialog() { return null; }\n", encoding="utf-8")
    table = where / screens / "orders-table.tsx"
    table.parent.mkdir(parents=True, exist_ok=True)
    table.write_text("export function OrdersTable() { return null; }\n", encoding="utf-8")
    repo.git("add", "-A", cwd=where)
    repo.git("commit", "-q", "-m", "Use shadcn/ui components", cwd=where)

    env.reviews(CLEAN)
    allowed = env.close(item)
    assert allowed.returncode == 0, allowed.stdout + allowed.stderr
    assert len(env.review_calls()) == 1

    # A dependency does not trigger the check in a client repo without shadcn/ui configured.
    no_config_root = tmp_path / "without-shadcn"
    no_config_root.mkdir()
    no_config, made = _fresh_client(repo, env.gh, no_config_root)
    assert made.returncode == 0, made.stdout + made.stderr
    client_config = (repo.path / "forge.toml").read_text(encoding="utf-8")
    (no_config / "forge.toml").write_text(client_config, encoding="utf-8")
    original = repo.path
    repo.path = no_config
    try:
        _commit_main(repo, tmp_path, "Use the test configuration")
        env.checks(GREEN)
        no_config_item, _ = _fix(env, "unconfigured-ui", {
            "package.json": json.dumps({"devDependencies": {"@mui/material": "^7.0.0"}}),
        })
        env.reviews(CLEAN)
        closes = env.close(no_config_item)
        assert closes.returncode == 0, closes.stdout + closes.stderr
        assert len(env.review_calls()) == 2
    finally:
        repo.path = original


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_5_review_holds_a_hand_built_component(env, tmp_path, monkeypatch, adopted):
    repo = _shadcn_client(env, tmp_path, adopted)
    # Audit: this protects the worker brief's shadcn command and the review rule for the app's
    # current screen folder. A brief that still names the old location can put new code elsewhere.
    # Existing tests cover the old app layout; this adds the module web library path through Forge.
    # The real work and close commands are used, with only agent and review answers stubbed.
    screens = Path("apps/web/src/features") if adopted else Path("libs/projects/web/src/pages")
    screen = repo.path / screens / "home.tsx"
    screen.parent.mkdir(parents=True, exist_ok=True)
    screen.write_text("export function Home() { return <main>Old</main>; }\n", encoding="utf-8")
    _commit_main(repo, tmp_path, "Add a screen")

    (repo.path / "plans/roadmap.json").write_text('{"items": []}\n', encoding="utf-8")
    _commit_main(repo, tmp_path, "Prepare a story")
    screen_path = (screens / "home.tsx").as_posix()
    doc = (STORY_DOC.replace("1. A shopper can save a basket.",
                             "1. The home screen uses shadcn/ui components.")
           .replace("`app.py`", f"`{screen_path}`")
           .replace("Save a basket | Shoppers can save their basket with one click",
                    "Change the screen | The home screen uses shadcn/ui components"))
    no_hooks = tmp_path / "fixture-no-hooks"
    no_hooks.mkdir(exist_ok=True)
    git = repo.git

    def fixture_git(*args, cwd=None):
        if args and args[0] in {"commit", "push"}:
            args = ("-c", f"core.hooksPath={no_hooks}", *args)
        return git(*args, cwd=cwd)

    with monkeypatch.context() as patch:
        patch.setattr(repo, "git", fixture_git)
        item, where = env.start_approved_task(doc, changes={
            screen_path: "export function Home() { return <main>Started</main>; }\n"
        })

    log = install_claude(repo)
    worked = repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    assert WORKER_RULE in calls(log)[-1]["brief"]

    env.commit(where, screen_path,
               "export function Home() { return <main>New</main>; }\n", "Change the screen")
    review_finding = {**finding("P1", "shadcn: DatePicker"),
                      "body": "Gain 2, Work 3, Harm 1\nA new date picker duplicates shadcn/ui."}
    env.reviews(blocked(review_finding))
    closed = env.close(item)
    output = closed.stdout + closed.stderr
    assert closed.returncode == 1, output
    assert "The review left serious findings open" in output
    assert "shadcn: DatePicker" in output
    assert "Gain 4, Work 2, Harm 1 (floor: shadcn)" in output
    assert REVIEW_RULE in env.prompt()
