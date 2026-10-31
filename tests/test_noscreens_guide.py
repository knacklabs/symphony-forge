"""Screen guidance reaches new and synced clients, and review selection follows web apps.

Test-audit answers:
1. The client-visible contracts are who builds screens, their order, and when the review rule
   applies; init, sync, work and close are the owning boundaries.
2. A template or review-selection regression can omit the guidance, lose it during sync, or add
   the web-app rule to an API-only client's review. Checking only apps/web misses web and
   frontend apps; checking directories alone mistakes web documentation for an app.
3. Existing guide tests do not cover this screen guidance or its conditional review delivery.
   Extend this owning prompt-delivery table with all three package-manifest locations and a
   directory-only negative control, including an earlier-adopted client at the same boundary.
4. No production seam is needed; only Autoreview, GitHub and the Claude worker edge are
   stubbed.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from conftest import ROOT
from test_close import CLEAN, GREEN, blocked, env, finding
from test_score_notes import _client_repo as setup_client
from test_setup import LISTED, _fresh_client, _version
from test_shadcn_only import _commit_main
from test_worker import calls, install_claude

STORY = "FORGE-NOSCREENS-1"

GUIDE_SENTENCES = (
    "Every API a person uses gets its screen in the client's design, built by the agent when it "
    "builds the API, with no need to ask.",
    "Webhooks, endpoints only agents or other systems call, and background jobs get no screen.",
    "The design comes first.",
    "a neutral design when there is no brand",
    "Build the basic screens first, then the business screens.",
    "The demo opens on the client's business task, and the basic screens are shown last.",
)
BASIC_SCREEN_RULES = (
    "Build these screens first in every prototype, in the client's design: sign-in, forgot "
    "password, reset password, accept invite, members and settings.",
    "Sign-in has `Email`, `Password`, a `Sign in` button and a `Forgot password?` link.",
    "the same neutral message for known and unknown emails",
    "expired or used link shows the API message",
    "The admin has no `Remove` button on their own row",
    "Every screen refetches the account on each page change",
)
REVIEW_RULE = (
    "In a client repo with a web app, report as P1, titled `Screen: <route>`, a route this change "
    "adds that people use, when the change adds no screen for it. Webhooks, agent-only routes, "
    "MCP, system endpoints and jobs are not findings, nor is a screen marked `Build: later`."
)
PENDING_SCREENS_RULE = (
    "When you build a basic screen, remove its name from `pendingScreens` so its rule specs run."
)


def _collapsed(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def _app_files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for base in ("apps", "libs")
        for path in (root / base).rglob("*")
        if path.is_file()
    }


@pytest.mark.platform
@pytest.mark.parametrize("setup", ["new init", "previous release"])
def test_6_the_guide_says_who_builds_the_screens(repo, gh, tmp_path, setup):
    if setup == "new init":
        client, made = _fresh_client(repo, gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        client = repo.path
        config = client / "forge.toml"
        config.write_text(config.read_text("utf-8").replace(
            'version = "v1.2.2"', f'version = "{_version(repo)}"'), "utf-8")
        repo.git("add", "-A", cwd=client)
        repo.git("commit", "-q", "-m", "Adopt the earlier client", cwd=client)
        repo.git("push", "-q", "origin", "main", cwd=client)
        sentinels = {
            "apps/web/src/forge-noscreens-existing.tsx": "export const existingScreen = true;\n",
            "libs/forge-noscreens-existing.ts": "export const existingLibrary = true;\n",
        }
        for path, content in sentinels.items():
            destination = client / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")
        _commit_main(repo, tmp_path, "Keep existing app files")

    started = repo.forge("fix", "start", "Check screen guidance", "--done",
                         "The screen guidance is delivered", "--kind", "mechanical", cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    client = client.parent / f"{client.name}-fix-check-screen-guidance"

    if setup == "previous release":
        before_apps = _app_files(client)
        synced = repo.forge("sync", cwd=client)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        changed = {line.split(None, 1)[1] for line in repo.git(
            "status", "--porcelain", "-uall", cwd=client).splitlines()}
        assert changed <= LISTED
        assert not any(path.startswith(("apps/", "libs/")) for path in changed)
        assert _app_files(client) == before_apps

    for host in (".claude", ".codex"):
        baseline = _collapsed(client / host / "skills/app-baseline/SKILL.md")
        assert "## Screens for the API" in baseline
        assert "## Basic screens" in baseline
        for sentence in (*GUIDE_SENTENCES, *BASIC_SCREEN_RULES):
            assert sentence in baseline, (host, sentence)

        guide = _collapsed(client / host / "skills/forge/SKILL.md")
        assert "Build the basic screens first, in the client's design" in guide
        assert "the starter has none, and has a `Project` API" in guide
        assert guide.count("the agent builds the Members screen in the client's design") == 2
        assert "writes no pages" in guide


def _fix(env, name: str, changes: dict[str, str]) -> tuple[str, Path]:
    state = {"kind": "fix", "why": "Build a screen for a person-facing API",
             "done_when": "The review reports a person-facing API with no screen"}
    return env.start(name, f"fix/{name}", f".factory/fixes/{name}.json", state, changes)


@pytest.mark.platform
@pytest.mark.parametrize(
    "setup,web_path",
    [("new init", "apps/web"), ("new init", "web"), ("new init", "frontend"),
     ("previous release", "frontend"), ("API-only", None)],
    ids=["new-client", "new-web", "new-frontend", "previous-release", "api-only-client"],
)
def test_7_the_review_reports_a_person_facing_api_with_no_screen(
        env, tmp_path, setup, web_path):
    setup_client(env, tmp_path, setup == "previous release")
    repo = env.repo
    if web_path:
        repo.write(f"{web_path}/package.json", json.dumps({"name": "client-web", "private": True}))
        repo.write(f"{web_path}/index.html", "<main>Client web app</main>\n")
    else:
        repo.write("apps/web/README.md", "Web integration notes for API consumers.\n")
    _commit_main(repo, tmp_path, "Record the client layout")
    env.checks(GREEN)

    item, _ = _fix(env, f"screen-rule-{setup.lower().replace(' ', '-')}", {
        "apps/api/orders/routes.ts": "export const route = '/api/v1/orders';\n",
    })
    log = install_claude(repo)
    worked = repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = " ".join(calls(log)[-1]["brief"].split())
    assert REVIEW_RULE in brief
    assert PENDING_SCREENS_RULE in brief

    if web_path:
        review_finding = {**finding("P1", "Screen: /api/v1/orders", "apps/api/orders/routes.ts"),
                          "body": "Gain 4, Work 2, Harm 1\nRaise: Functional\n"
                                  "Case: normal use - a person uses this API but has no screen."}
        env.reviews(blocked(review_finding))
        closed = env.close(item)
        output = closed.stdout + closed.stderr
        assert closed.returncode == 1, output
        assert "Screen: /api/v1/orders" in output
        assert REVIEW_RULE in " ".join(env.prompt().split())
    else:
        env.reviews(CLEAN)
        closed = env.close(item)
        assert closed.returncode == 0, closed.stdout + closed.stderr
        assert REVIEW_RULE not in " ".join(env.prompt().split())
