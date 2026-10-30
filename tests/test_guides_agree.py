"""New and earlier-adopted repos receive guides that match the starters."""
import json
import re
import shutil
from pathlib import Path

import pytest

from conftest import ROOT
from test_app_constitution import _fixture_git
from test_setup import _fresh_client
from test_worker import calls, install_claude

STORY = "FORGE-GUIDES-1"


@pytest.fixture(params=["new init", "previous release"])
def guided_client(repo, gh, tmp_path, request):
    if request.param == "new init":
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    else:
        client = repo.path
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", client,
                        dirs_exist_ok=True)
        config = client / "forge.toml"
        version = repo.forge("--version").stdout.split()[-1]
        config.write_text(config.read_text("utf-8").replace('"v1.2.2"', json.dumps(version)),
                          encoding="utf-8")
    if request.param == "previous release":
        app_files = {
            "Dockerfile": 'FROM node:24-bookworm-slim\nWORKDIR /app\nCOPY . .\nRUN corepack pnpm install --frozen-lockfile\nCMD ["node", "dist/main.js"]\n',
            "README.md": "## Run\nRun our own app.\n",
            "package.json": '{"devDependencies":{"prettier":"3.6.2"}}\n',
            "pnpm-lock.yaml": "packages:\n  prettier@3.6.2: {}\n",
        }
        for name, text in app_files.items():
            (client / name).write_text(text, encoding="utf-8")
    config = client / "forge.toml"
    config.write_text(re.sub(r'^workers = ".*"$', 'workers = "claude"',
                             config.read_text("utf-8"), flags=re.M), encoding="utf-8")
    _fixture_git(repo, tmp_path, "add", "-A", cwd=client)
    _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Prepare guide check", cwd=client)
    _fixture_git(repo, tmp_path, "push", "-q", "origin", "main", cwd=client)
    started = repo.forge("fix", "start", "Check guide alignment", "--done",
                         "The worker receives matching guides", "--kind", "mechanical",
                         cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    top = Path(re.search(r" in (.+)\n", started.stdout)[1])
    if request.param == "previous release" and request.node.originalname != "test_4_an_existing_repo_gets_the_non_root_rule_and_keeps_its_app_files":
        synced = repo.forge("sync", cwd=top)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        _fixture_git(repo, tmp_path, "add", "-A", cwd=top)
        _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Sync the client guide", cwd=top)
    return top


@pytest.mark.platform
def test_1_the_guides_say_what_the_starters_do(repo, guided_client):
    # Audit: the shipped prompt text is the contract. Old paging, currency, formatter or
    # install instructions make workers build the wrong app. Existing starter tests check
    # runtime behavior, not guide delivery to both hosts or the worker's conventions path.
    # Real init, sync and work exercise that delivery without a production test seam.
    for host in (".claude", ".codex"):
        skills = guided_client / host / "skills"
        standards = (skills / "forge/standards.md").read_text("utf-8")
        assert "Lists use keyset paging" in standards
        for term in ("`after`", "`before`", "`data.paging`", "`nextCursor`",
                     "`previousCursor`", "`totalCapped`", "10,000", "`APP_ENV`",
                     "`development`", "`test`", "`demo`", "`qa`", "`uat`", "`staging`",
                     "`production`"):
            assert term in standards
        assert "totalPages" not in standards
        assert "`Local`, `Development`" not in standards
        baseline = (skills / "app-baseline/SKILL.md").read_text("utf-8")
        assert "npx shadcn@4.21.4 add <component>" in baseline
        assert "shadcn@latest" not in baseline
        database = (skills / "database/SKILL.md").read_text("utf-8")
        assert "More than 10,000" in database
        assert "1,000+" not in database
        fde = (skills / "forge/fde.md").read_text("utf-8")
        assert "Currency uses INR" in fde
        assert "USD" not in fde

    log = install_claude(repo)
    worked = repo.forge("work", "check-guide-alignment", cwd=guided_client)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    match = re.search(r"how-to.*?is in `([^`]+)`", calls(log)[-1]["brief"], re.S)
    assert match
    conventions = Path(match[1])
    api = (conventions / "api.md").read_text("utf-8")
    assert "nextCursor" in api and "totalPages" not in api
    assert "Use after or before, not both." in api
    python = (conventions / "python.md").read_text("utf-8")
    assert "data.paging" in python and "data.pagination" not in python
    assert "?page=" not in (conventions / "frontend.md").read_text("utf-8")
    for page in conventions.glob("*.md"):
        assert "Prettier" not in page.read_text("utf-8"), page.name


@pytest.mark.platform
def test_2_the_fde_defaults_promise_only_built_parts(guided_client):
    # Audit: these default answers must distinguish built-in parts from later stories.
    # The previous promises are the regression; suffix coverage in test_6 owns unrelated
    # built-in rules. Checking delivered prompt lines needs no production seam.
    expected = (
        "- How do people sign in?: Email and password. Social sign-in comes with the story that needs it.",
        "- How much information will it hold in a year (rows, files)?: Postgres and server-side pages. File storage comes with the story that adds uploads.",
        "- Should the app send messages (email, text, push, in-app)? About what?: Transactional email. In-app notices come with the story that needs them. No text or push messages.",
        "- Which languages and currencies, date formats, time zones?: English. A message catalogue comes with the story that adds a second language. Dates use YYYY-MM-DD and times use 24-hour format in the user's time zone. Currency uses INR with the currency code (INR 1,234.56). Numbers use comma thousands separators and a decimal point (1,234.56). The date, time, number and money formats are built in when the app has libs/organisations or apps/api/app/organisations.",
        "- Who fixes problems, and how fast must it be back up if it breaks?: Daily managed backups and no uptime promise. Each error is logged with its error id, and Mainline alerts on the error log lines; the app has no error-tracking service.",
    )
    for host in (".claude", ".codex"):
        fde = (guided_client / host / "skills/forge/fde.md").read_text("utf-8")
        for line in expected:
            assert line in fde.splitlines()
        for obsolete in ("social sign-in through", "object storage for files",
                         "and in-app notices", "and a message catalogue", "error tracking,"):
            assert obsolete not in fde


def _worker_conventions(repo, client):
    log = install_claude(repo)
    worked = repo.forge("work", "check-guide-alignment", cwd=client)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    match = re.search(r"how-to.*?is in `([^`]+)`", calls(log)[-1]["brief"], re.S)
    assert match
    return Path(match[1])


@pytest.mark.platform
def test_3_the_guides_hold_the_jobs_calls_and_uploads_rules(repo, guided_client):
    # Audit: delivered rules are the prompt contract. Missing rules cause different
    # client implementations; starter tests do not cover these later features.
    # Real init, sync and work cover delivery without a production test seam.
    for host in (".claude", ".codex"):
        database = (guided_client / host / "skills/database/SKILL.md").read_text("utf-8")
        for term in ("worker entry in `services.toml`", "FOR UPDATE SKIP LOCKED",
                     "clean-up of old sessions, reset tokens and invites", "attempt count",
                     "last error", "schedule only inserts job rows"):
            assert term in database
    conventions = _worker_conventions(repo, guided_client)
    expected = {
        "deploy.md": ('name = "worker"', 'expose = "internal"', 'command ='),
        "stack.md": ("FOR UPDATE SKIP LOCKED",),
        "backend.md": ("AbortSignal.timeout(10_000)", "x-correlation-id", "0.5", "2 seconds"),
        "python.md": ("httpx.Client(timeout=10.0)", "x-correlation-id", "0.5", "2 seconds"),
        "security.md": ("S3_ENDPOINT", "S3_REGION", "S3_BUCKET", "S3_ACCESS_KEY_ID",
                        "S3_SECRET_ACCESS_KEY", "never a URL", "5 minutes or less",
                        "@aws-sdk/client-s3", "boto3"),
    }
    for page, terms in expected.items():
        text = (conventions / page).read_text("utf-8")
        for term in terms:
            assert term in text, (page, term)


@pytest.mark.platform
@pytest.mark.parametrize("guided_client", ["previous release"], indirect=True)
def test_4_an_existing_repo_gets_the_non_root_rule_and_keeps_its_app_files(repo, guided_client, tmp_path):
    # Audit: sync must preserve app-owned bytes, including root images and Prettier.
    # No other delivery test seeds these files; no production seam is needed.
    names = ("Dockerfile", "README.md", "package.json", "pnpm-lock.yaml")
    before = {name: (guided_client / name).read_bytes() for name in names}
    synced = repo.forge("sync", cwd=guided_client)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    for name, content in before.items():
        assert (guided_client / name).read_bytes() == content
    status = _fixture_git(repo, tmp_path, "status", "--porcelain", "-uall", cwd=guided_client)
    for name in names:
        assert name not in status
    _fixture_git(repo, tmp_path, "add", "-A", cwd=guided_client)
    _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Sync the client guide", cwd=guided_client)
    deploy = (_worker_conventions(repo, guided_client) / "deploy.md").read_text("utf-8")
    assert "Containers run as a user that is not root." in deploy


@pytest.mark.platform
def test_5_the_guide_turns_on_security_alerts_only(guided_client):
    # Audit: security setup is a delivered agent instruction. Existing tests do not
    # cover alerts or accidental update configuration; no production seam is needed.
    for host in (".claude", ".codex"):
        guide = (guided_client / host / "skills/forge/SKILL.md").read_text("utf-8")
        assert "gh api --method PUT repos/{owner}/{repo}/vulnerability-alerts" in guide
        assert "Dependabot security updates stay off" in guide
        assert "no Dependabot update pull requests" in guide
    assert not (guided_client / ".github/dependabot.yml").exists()
