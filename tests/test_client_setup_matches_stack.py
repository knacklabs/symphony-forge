"""Client setup ships usable defaults on init and after an earlier adoption."""
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from test_worker import calls, install_claude
from test_doctor_batches_file_checks import _adopted_client
from test_doctor_fix_files import _start_fix

STORY = "FIX-SKIPPED-TEMPLATES"


@pytest.mark.parametrize("marker, node", [
    ("package.json", True), ("pyproject.toml", False), ("go.mod", False), (None, True),
])
def test_1_init_only_gives_node_repos_node_deploy_files(repo, gh, tmp_path, marker, node):
    client, remote = tmp_path / "client", tmp_path / "client.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(client)], check=True)
    repo.git("remote", "add", "origin", str(remote), cwd=client)
    if marker:
        (client / marker).write_text("{}\n" if node else "", encoding="utf-8")
    gh.respond("api", stdout="{}")
    result = repo.forge("init", cwd=client)
    assert result.returncode == 0, result.stdout + result.stderr
    for name in ("Dockerfile", ".dockerignore"):
        assert (client / name).exists() == node
    if node:
        assert "FROM node:" in (client / "Dockerfile").read_text()


@pytest.fixture(params=["new init", "previous release"])
def client_templates(repo, gh, tmp_path, monkeypatch, request):
    main = _adopted_client(repo, gh, tmp_path, monkeypatch, request.param)
    client = _start_fix(repo, main, "Use client templates")
    settings = client / "forge.toml"
    settings.write_text(re.sub(r'workers = "[^"]+"', 'workers = "claude"', settings.read_text()),
                        encoding="utf-8")
    result = repo.forge("sync", cwd=client)
    assert result.returncode == 0, result.stdout + result.stderr
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "--allow-empty", "-qm", "Use current templates", cwd=client)
    log = install_claude(repo)
    worked = repo.forge("work", "use-client-templates", cwd=client)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = calls(log)[-1]["brief"]
    match = re.search(r"how-to.*?is in `([^`]+)`", brief, re.S)
    assert match, brief
    conventions = Path(match[1])
    assert conventions.is_dir()
    return client, conventions


def test_2_dependency_guide_names_both_yarn_generations(client_templates):
    client, _ = client_templates
    for host in (".codex", ".claude"):
        guide = (client / host / "skills/forge/SKILL.md").read_text()
        assert "`yarn upgrade` (Yarn 1)" in guide
        assert "`yarn up -R '*'` (Yarn 2+)" in guide


def test_3_backend_logger_fatal_writes_a_fatal_line(tmp_path, client_templates):
    _, conventions = client_templates
    blocks = re.findall(r"```ts\n(.*?)```", (conventions / "backend.md").read_text(), re.S)
    logger = next(b for b in blocks if "implements LoggerService" in b).replace("@Injectable()\n", "")
    script = tmp_path / "logger.ts"
    script.write_text("type LoggerService = object;\n"
                      "const correlationStore = {getStore: () => 'fatal-request'};\n" + logger +
                      "\nnew JsonLogger().fatal('App cannot continue', 'Bootstrap', {reason: 'unavailable'});\n",
                      encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            env=os.environ | {"NODE_ENV": "Local"})
    assert result.returncode == 0, result.stderr
    [entry] = [json.loads(line) for line in result.stdout.splitlines()]
    assert entry["level"] == "fatal"
    assert entry["message"] == "App cannot continue"
    assert entry["module"] == "Bootstrap"
    assert entry["context"] == {"reason": "unavailable"}


def test_4_playwright_config_limits_discovery_to_e2e(client_templates):
    # Shipped config contract: a root config must exclude unit-test folders.
    _, conventions = client_templates
    testing = (conventions / "testing.md").read_text()
    [config] = [b for b in re.findall(r"```ts\n(.*?)```", testing, re.S) if "defineConfig" in b]
    assert re.search(r"testDir:\s*['\"]\./e2e['\"]", config)
