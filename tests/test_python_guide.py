"""Python backend guidance reaches new and previously adopted client apps."""
from __future__ import annotations

import re
import shutil
import tomllib
from pathlib import Path

import pytest

from conftest import ROOT
from test_app_constitution import _fixture_git
from test_notes_first_discovery import client
from test_setup import _version
from test_worker import calls, install_claude

STORY = "FORGE-FASTAPI-1"


@pytest.mark.platform
@pytest.mark.parametrize("adoption", ["new init", "previous release upgrade and sync"])
def test_4_a_worker_in_a_python_app_reads_the_python_page(
        repo, client, adoption):
    # Gate: protects worker guidance delivered through init and earlier-release sync. A missing
    # brief pointer or page breaks the worker's ability to find the Python rules. Existing
    # standards tests do not exercise a real worker brief; the Claude stub replaces only delivery.
    # No production seam is needed: this checks shipped prompt and document contracts.
    log = install_claude(repo)
    config = client / "forge.toml"
    settings = re.sub(r'^workers = ".*"$', 'workers = "claude"',
                      config.read_text("utf-8"), flags=re.M)
    config.write_text(settings, encoding="utf-8")
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-q", "--allow-empty", "-m", "Use Claude for the worker check", cwd=client)

    if adoption == "new init":
        started = repo.forge("fix", "start", "Read the Python guide", "--done",
                             "The worker reads the Python page", "--kind", "mechanical", cwd=client)
        assert started.returncode == 0, started.stdout + started.stderr
        item = "read-the-python-guide"
    else:
        item = "sync-the-discovery-guide"
    worked = repo.forge("work", item, cwd=client)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    call = calls(log)[-1]
    brief = call["brief"]
    assert ("In an app with a FastAPI backend, open python.md there for the backend, API, database, "
            "security, test and deploy concerns. The rules of the other pages apply to it, and "
            "their NestJS and Prisma code does not.") in " ".join(brief.split())

    match = re.search(r"how-to.*?is in `([^`]+)`", brief, re.S)
    assert match, brief
    conventions = Path(match[1])
    page = (conventions / "python.md").read_text(encoding="utf-8")
    for heading in ("Layout", "Modules", "Config", "Logs", "Errors", "API", "Database",
                    "Migrations", "Security", "Tests", "Deploy"):
        assert f"## {heading}" in page
    for term in ('extra="forbid"', "errorId", "x-correlation-id", "Uuid", "_at_utc",
                 "_in_cents", "deleted_at_utc", "alembic upgrade head", "lint-imports",
                 "ruff format --check", "mypy", "pytest"):
        assert term in page
    for host in (".claude", ".codex"):
        standards = (client / host / "skills/forge/standards.md").read_text(encoding="utf-8")
        assert "`python.md`" in standards


def test_5_an_existing_app_keeps_its_stack(repo, gh, tmp_path):
    # A previous-release client may already have a Python app. Upgrade and sync must preserve
    # its files and test command while withholding the new starter.
    shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
    files = {
        "pyproject.toml": b'[project]\nname = "existing-api"\nversion = "0.1.0"\n',
        "uv.lock": b'version = 1\nrevision = 1\nrequires-python = ">=3.12"\n',
        "Dockerfile": b"FROM python:3.12-slim\nCOPY app /app\n",
        "app/main.py": b"from fastapi import FastAPI\n\napp = FastAPI()\n",
    }
    for rel, contents in files.items():
        path = repo.path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
    config = repo.path / "forge.toml"
    old_settings = config.read_text("utf-8")
    settings = re.sub(r'^test = .*$', 'test = "uv run pytest"', old_settings,
                      count=1, flags=re.M)
    config.write_text(settings, encoding="utf-8")
    _fixture_git(repo, tmp_path, "add", "-A")
    _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Adopt existing Python app")
    config.write_text(re.sub(r'^version = ".*"$', f'version = "{_version(repo)}"',
                             settings, count=1, flags=re.M), encoding="utf-8")
    _fixture_git(repo, tmp_path, "add", "forge.toml")
    _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Upgrade Forge")
    _fixture_git(repo, tmp_path, "push", "-q", "origin", "main")

    started = repo.forge("fix", "start", "Preserve the existing Python app", "--done",
                         "The Python app keeps its files and test command", "--kind", "mechanical")
    assert started.returncode == 0, started.stdout + started.stderr
    top = Path(re.search(r" in (.+)\n", started.stdout)[1])
    synced = repo.forge("sync", cwd=top)
    assert synced.returncode == 0, synced.stdout + synced.stderr

    for rel, contents in files.items():
        assert (top / rel).read_bytes() == contents
    assert tomllib.loads((top / "forge.toml").read_text("utf-8"))["test"] == "uv run pytest"
    for rel in ("apps/api", "libs/shared", "scripts/test.mjs", "pnpm-lock.yaml"):
        assert not (top / rel).exists()
