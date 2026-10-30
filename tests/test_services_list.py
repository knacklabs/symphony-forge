"""New apps declare their main service, and close checks committed service lists."""
from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

import pytest

from conftest import patient
from test_close import CLEAN, GREEN, env  # noqa: F401 (env is a fixture)
from test_score_notes import _client_repo as setup_client
from test_setup import _fresh_client


STORY = "FORGE-SERVICES-1"
SERVICE = {"name": "app", "dockerfile": "Dockerfile", "port": 3000,
           "health": "/health", "expose": "main"}


def _fresh_client_with_own_dockerfile(
    repo, gh, tmp_path: Path,
) -> tuple[Path, subprocess.CompletedProcess[str], bytes]:
    """Run plain init with a Node app's Dockerfile already in the new repo."""
    client, remote = tmp_path / "client", tmp_path / "client.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(client)], check=True)
    repo.git("remote", "add", "origin", str(remote), cwd=client)
    (client / "package.json").write_text("{}\n", encoding="utf-8")
    dockerfile = client / "Dockerfile"
    dockerfile.write_text("FROM node:24-alpine\nEXPOSE 8080\n", encoding="utf-8")
    original = dockerfile.read_bytes()
    gh.respond("api", stdout="{}")
    gh.respond("api", "repos/{owner}/{repo}/branches/main/protection", exit=1,
               stdout='{"message":"Branch not protected","status":"404"}')
    initialized = repo.forge("init", "--actions", "yes", cwd=client)
    return client, initialized, original


@pytest.mark.parametrize("kind", ["react", "python", "plain", "plain-own-dockerfile"],
                         ids=["react", "python", "plain", "plain-own-dockerfile"])
def test_1_new_apps_list_one_main_service(repo, gh, tmp_path, kind):
    # Audit: protects the first-commit contract for real init commands. A missing or misplaced
    # skeleton list would leave new apps without the fact the deploy platform reads. Existing
    # scaffold checks only compare file sets; they do not parse the list or preserve a user's
    # Dockerfile. No production seam is needed; only GitHub's external API is stubbed.
    if kind == "plain-own-dockerfile":
        client, initialized, original = _fresh_client_with_own_dockerfile(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        assert (client / "Dockerfile").read_bytes() == original
        assert not (client / "services.toml").exists()
        assert "services.toml" not in repo.git("ls-files", cwd=client).splitlines()
        return

    init_args = ("--starter", kind) if kind in ("react", "python") else ()
    client, initialized = _fresh_client(repo, gh, tmp_path, *init_args)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    expected_service = {**SERVICE, "mcp": "/mcp"} if kind in {"react", "python"} else SERVICE
    assert tomllib.loads((client / "services.toml").read_text(encoding="utf-8")) == {
        "service": [expected_service],
    }
    assert "EXPOSE 3000" in (client / "Dockerfile").read_text(encoding="utf-8")
    assert "services.toml" in repo.git("ls-files", cwd=client).splitlines()
    assert "services.toml" in repo.git("ls-tree", "-r", "--name-only", "HEAD",
                                       cwd=client).splitlines()


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_2_close_checks_the_list_against_its_dockerfiles(env, tmp_path, adopted):
    # Audit: protects close's committed services.toml contract through the real command. Existing
    # close tests do not cover service declarations. A regression could accept missing Dockerfiles,
    # multiple or zero main services, or invalid TOML. No production seam is needed; only the
    # review, checks and GitHub edges use the existing close fixture.
    setup_client(env, tmp_path, adopted)
    repo = env.repo
    env.reviews(CLEAN)
    env.checks(GREEN)

    if adopted:
        assert not (repo.path / "services.toml").exists()
        item, _ = env.start("services", "fix/services", ".factory/fixes/services.json",
                            {"kind": "fix", "why": "Change an app file",
                             "done_when": "The app file changes"},
                            {"ordinary.py": "value = 1\n"})
        closed = env.close(item)
        assert closed.returncode == 0, closed.stdout + closed.stderr
        assert "services.toml" not in closed.stdout + closed.stderr
        return

    valid = '''[[service]]
name = "app"
dockerfile = "Dockerfile"
port = 3000
health = "/health"
expose = "main"

[[service]]
name = "api"
dockerfile = "apps/api/Dockerfile"
port = 3000
health = "/health"
expose = "subdomain"
subdomain = "api"

[[service]]
name = "worker"
dockerfile = "worker/Dockerfile"
expose = "internal"
command = "exec node worker.js"
'''
    item, where = env.start("services", "fix/services", ".factory/fixes/services.json",
                            {"kind": "fix", "why": "List the app services",
                             "done_when": "The list matches the Dockerfiles"},
                            {"apps/api/Dockerfile": "FROM node:24-alpine\nEXPOSE 3000\n",
                             "worker/Dockerfile": "FROM node:24-alpine\n"})
    env.commit(where, "services.toml", valid, "List services")

    # Close reads the committed list and Dockerfile paths from HEAD.
    (where / "services.toml").write_text("[[service]\n", encoding="utf-8")
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    (where / "services.toml").write_text(valid, encoding="utf-8")

    # Keep the API's exposure but remove its Dockerfile field; the worker path is absent too.
    missing = valid.replace('dockerfile = "apps/api/Dockerfile"\n', "")
    (where / "services.toml").write_text(missing, encoding="utf-8")
    patient(lambda: (where / "worker/Dockerfile").unlink())
    repo.git("add", "-A", cwd=where)
    repo.git("commit", "-q", "-m", "Remove missing service files", cwd=where)
    refused = env.close(item)
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert ("services.toml has a service with no dockerfile; names worker/Dockerfile, "
            "which this branch does not have.") in refused.stderr
    assert f"Next: fix services.toml to match the Dockerfiles, then forge close {item}" in refused.stderr

    env.commit(where, "worker/Dockerfile", "FROM node:24-alpine\n", "Restore worker Dockerfile")
    multiple_main = valid.replace('expose = "subdomain"', 'expose = "main"')
    env.commit(where, "services.toml", multiple_main, "Add a second main service")
    refused = env.close(item)
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert 'services.toml has 2 services with expose = "main"; it needs exactly one.' in refused.stderr
    assert f"Next: fix services.toml to match the Dockerfiles, then forge close {item}" in refused.stderr

    env.commit(where, "services.toml", "[[service]\n", "Break the service list")
    refused = env.close(item)
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "services.toml is not valid TOML:" in refused.stderr
    assert f"Next: fix services.toml to match the Dockerfiles, then forge close {item}" in refused.stderr

    env.commit(where, "services.toml", 'service = "not a list"\n', "Use a non-list service value")
    refused = env.close(item)
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert 'services.toml has 0 services with expose = "main"; it needs exactly one.' in refused.stderr
    assert f"Next: fix services.toml to match the Dockerfiles, then forge close {item}" in refused.stderr

    no_main = valid.replace('expose = "main"', 'expose = "internal"', 1)
    env.commit(where, "services.toml", no_main, "Remove the main service")
    refused = env.close(item)
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert 'services.toml has 0 services with expose = "main"; it needs exactly one.' in refused.stderr
    assert f"Next: fix services.toml to match the Dockerfiles, then forge close {item}" in refused.stderr
