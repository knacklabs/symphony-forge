"""Built-in defaults reach new and previously adopted client apps."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from conftest import ROOT
from test_app_constitution import _fixture_git
from test_setup import _fresh_client
from test_worker import calls, install_claude

STORY = "FORGE-DEFAULTS-1"


@pytest.mark.platform
@pytest.mark.parametrize("adoption", ["new init", "previous release upgrade and sync"])
def test_6_the_constitution_lists_the_built_in_defaults_and_existing_apps_keep_their_code(
        repo, gh, tmp_path, adoption):
    app_files = {
        "apps/web/src/features/home.tsx": b"export const home = new Date().toLocaleString();\n",
        "eslint.config.mjs": b"export default [{ rules: { 'our/rule': 'error' } }];\n",
    }
    if adoption == "new init":
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        client = repo.path
        for rel, contents in app_files.items():
            path = client / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)
        config = client / "forge.toml"
        version = repo.forge("--version").stdout.split()[-1]
        settings = config.read_text("utf-8").replace('"v1.2.2"', json.dumps(version))
        config.write_text(settings, encoding="utf-8")

    config = client / "forge.toml"
    settings = re.sub(r'^workers = ".*"$', 'workers = "claude"',
                      config.read_text("utf-8"), flags=re.M)
    config.write_text(settings, encoding="utf-8")
    _fixture_git(repo, tmp_path, "add", "-A", cwd=client)
    _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Prepare the client", cwd=client)
    _fixture_git(repo, tmp_path, "push", "-q", "origin", "main", cwd=client)

    started = repo.forge("fix", "start", "Check built-in defaults guide", "--done",
                         "The app has built-in defaults guidance", "--kind", "mechanical",
                         cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    top = Path(re.search(r" in (.+)\n", started.stdout)[1])
    if adoption == "previous release upgrade and sync":
        synced = repo.forge("sync", cwd=top)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        for rel, contents in app_files.items():
            assert (top / rel).read_bytes() == contents
        assert not (top / "libs/organisations").exists()
        # The worker receives a clean branch, not a reminder to commit sync's output.
        _fixture_git(repo, tmp_path, "add", "-A", cwd=top)
        _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Sync the client guide", cwd=top)

    # Both starter layouts supply these defaults; the interview must skip them for either.
    outline_sentence = (
        "In an app that has libs/organisations or apps/api/app/organisations, "
        "also copy the built-in lines into ## Fixed rules, "
        "and ask nothing about the defaults they answer."
    )
    fixed_rules = (
        "- Built in: each account belongs to one organisation, as an admin or a member, and every "
        "query is scoped to that organisation.\n"
        "- Built in: admins invite people by email; members cannot invite people or change roles.\n"
        "- Built in: dates and times are stored in UTC and shown in the person's time zone, and "
        "money is stored as an exact decimal with its currency code; the helpers in @app/shared "
        "format them.\n"
        "- Built in: each table has a CSV export, admin actions write change history, and records "
        "are soft deleted.\n"
        "- Built in: each UI or API crash writes one error report to the logs."
    )
    for host in (".claude", ".codex"):
        skills = top / host / "skills/forge"
        guide = (skills / "SKILL.md").read_text("utf-8")
        constitution = guide.split("\n## App constitution\n")[1].split("\n## Adopt a live app\n")[0]
        assert outline_sentence in " ".join(constitution.split())
        outline = constitution.split("```markdown\n")[1].split("```", 1)[0]
        for rule in fixed_rules.splitlines():
            assert rule in outline

        fde = (skills / "fde.md").read_text("utf-8").splitlines()
        built_in_suffix = " Built in when the app has libs/organisations or apps/api/app/organisations."
        for question in (
            "Can people see each other's information, or only their own?",
            "Who can add people and change what they can do?",
            "What happens if someone deletes something by mistake? Do you need history of who changed what?",
        ):
            answer = next(line for line in fde if line.startswith(f"- {question}:"))
            assert answer.endswith(built_in_suffix)
        assert sum(line.endswith(built_in_suffix) for line in fde) == 3
        partial_answers = {
            "Which languages and currencies, date formats, time zones?": (
                " The date, time, number and money formats are built in when the app has "
                "libs/organisations or apps/api/app/organisations."
            ),
            "Do you need reports, charts or exports (PDF, Excel)?": (
                " The CSV export is built in when the app has "
                "libs/organisations or apps/api/app/organisations."
            ),
        }
        for question, suffix in partial_answers.items():
            answer = next(line for line in fde if line.startswith(f"- {question}:"))
            assert answer.endswith(suffix)
        assert ("- Who fixes problems, and how fast must it be back up if it breaks?: Daily managed "
                "backups, error tracking, and no uptime promise.") in fde

    log = install_claude(repo)
    worked = repo.forge("work", "check-built-in-defaults-guide", cwd=top)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = calls(log)[-1]["brief"]
    worker_rule = (
        "In an app that has libs/organisations, scope every query to the caller's organisation "
        "(organisationId on the principal), guard admin actions with @AdminOnly() and record them "
        "with HistoryService.record, format dates, times, numbers and money only with the helpers "
        "in @app/shared, export a table only with sendCsv from @app/core, and let crashes reach "
        "the one error report. An app without libs/organisations keeps the code it has."
    )
    assert worker_rule in " ".join(brief.split())
    match = re.search(r"how-to.*?is in `([^`]+)`", brief, re.S)
    assert match, brief
    conventions = Path(match[1])
    convention_terms = {
        "security.md": (
            "scope every query to `organisationId` on the caller's principal",
            "Guard each admin action with `@AdminOnly()`",
        ),
        "database.md": (
            "Store dates and times in UTC.",
            "each table with `deletedAtUtc` has a `soft_delete_only()` trigger that refuses a hard delete",
            "Record admin actions through `HistoryService.record`",
        ),
        "frontend.md": (
            "format dates, times, numbers and money only with the helpers in `@app/shared`",
            "Show dates and times in the person's time zone, from their browser",
            "Each table has an `Export CSV` link", "the route error page reports the crash once",
        ),
        "backend.md": (
            "libs/organisations", "libs/history",
            "`type:module` for auth, projects, organisations and history",
            "Export a table only with `sendCsv` from `@app/core`",
            "the filter writes one error report per crash",
        ),
        "api.md": ("each list has a `GET /<list>/export` route",),
        "stack.md": (
            "libs/organisations", "libs/history",
            "An app set up before this release keeps its own organisation, date, export, history and error code.",
        ),
    }
    for page, terms in convention_terms.items():
        contents = " ".join((conventions / page).read_text("utf-8").split())
        for term in terms:
            assert term in contents, f"{term!r} is missing from {page}"

    standards = (conventions.parent.parent / "standards.md").read_text("utf-8")
    assert "libs/organisations" in standards and "libs/history" in standards
