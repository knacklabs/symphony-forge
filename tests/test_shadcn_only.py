"""The shadcn-only close and review rules on new and upgraded client apps."""
from __future__ import annotations

import json

import pytest

from test_close import CLEAN, GREEN, blocked, env, finding
from test_close import STORY_DOC
from test_score_notes import _client_repo as setup_client
from test_setup import _fresh_client
from test_worker import calls, install_claude


REVIEW_RULE = (
    "In an app with shadcn/ui set up (a `components.json`), report a new UI component that "
    "hand-builds what a shadcn/ui component or block already does as a P1 finding titled "
    "`shadcn: <the component>`, unless a `Not shadcn: <why>` comment at the component says why "
    "shadcn/ui cannot do it. A composite built from shadcn/ui components is not a finding, and "
    "neither is a library or component the default branch already has."
)
WORKER_RULE = (
    "In a client app with shadcn/ui set up, use shadcn/ui only. Close refuses a new UI component "
    "library and a new file outside components/ui/ named like a shadcn/ui component. Review holds "
    "a hand-built UI component unless a `Not shadcn: <why>` comment says why."
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
    (repo.path / "components.json").write_text("{}\n", encoding="utf-8")
    button = repo.path / "apps/web/src/components/ui/button.tsx"
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
    repo = _shadcn_client(env, tmp_path, adopted)
    item, where = _fix(env, "shadcn-only", {
        "apps/web/package.json": json.dumps({"devDependencies": {"@mui/material": "^7.0.0"}}),
        "apps/web/src/features/orders/Button.tsx": "export function Button() { return null; }\n",
    })

    refused = env.close(item)
    output = refused.stdout + refused.stderr
    assert refused.returncode == 1, output
    assert "This app uses shadcn/ui only, and this change adds" in output
    assert "@mui/material" in output
    assert "apps/web/src/features/orders/Button.tsx" in output
    assert "npx shadcn@4.21.4 add <name>" in output
    assert f"then forge close {item}" in output

    (where / "apps/web/src/features/orders/Button.tsx").unlink()
    (where / "apps/web/package.json").unlink()
    if adopted:
        (where / "package.json").write_text(
            json.dumps({"dependencies": {"antd": "^5.1.0"}}), encoding="utf-8")
    dialog = where / "apps/web/src/components/ui/dialog.tsx"
    dialog.parent.mkdir(parents=True, exist_ok=True)
    dialog.write_text("export function Dialog() { return null; }\n", encoding="utf-8")
    table = where / "apps/web/src/features/orders/orders-table.tsx"
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
    screen = repo.path / "apps/web/src/features/home.tsx"
    screen.parent.mkdir(parents=True, exist_ok=True)
    screen.write_text("export function Home() { return <main>Old</main>; }\n", encoding="utf-8")
    _commit_main(repo, tmp_path, "Add a screen")

    (repo.path / "plans/roadmap.json").write_text('{"items": []}\n', encoding="utf-8")
    _commit_main(repo, tmp_path, "Prepare a story")
    doc = (STORY_DOC.replace("1. A shopper can save a basket.",
                             "1. The home screen uses shadcn/ui components.")
           .replace("`app.py`", "`apps/web/src/features/home.tsx`")
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
            "apps/web/src/features/home.tsx": "export function Home() { return <main>Started</main>; }\n"
        })

    log = install_claude(repo)
    worked = repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    assert WORKER_RULE in calls(log)[-1]["brief"]

    env.commit(where, "apps/web/src/features/home.tsx",
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
