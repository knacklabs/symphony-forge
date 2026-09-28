STORY = "FORGE-ONECHAT-1"

import hashlib
import subprocess
from pathlib import Path

from conftest import Repo
from test_story import DOC, claude_plan, hook, ready, setup


def _other(repo, tmp_path, name="other"):
    remote, path = tmp_path / f"{name}.git", tmp_path / name
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    other = Repo(path, repo.bin)
    other.write("README.md", "# Another repo\n")
    other.git("add", "README.md")
    other.git("commit", "-q", "-m", "First commit")
    other.git("remote", "add", "origin", str(remote))
    other.git("push", "-q", "-u", "origin", "main")
    other.git("remote", "set-head", "origin", "main")
    return other


def _markers(repo):
    common = repo.git("rev-parse", "--path-format=absolute", "--git-common-dir")
    return list((Path(common) / "forge" / "approvals").glob("*"))


def test_3_one_chat_approves_other_repo_once(repo, tmp_path, claude_payload):
    setup(repo, keys=("LOCAL",))
    twin = DOC.replace("save a basket", "share a basket")
    local = ready(repo, "LOCAL", twin)
    other = _other(repo, tmp_path)
    setup(other, keys=("SHOP", "TWIN"))
    shop = ready(other, "SHOP")
    assert other.forge("next").returncode == 0  # remembers its main checkout
    before = other.git("rev-parse", "story/SHOP")
    payload = claude_plan(claude_payload, DOC, cwd=local)
    git_dir = Path(other.git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=shop))
    commit_hook = git_dir / "hooks" / "commit-msg"
    commit_hook.write_text("#!/bin/sh\ngit branch --show-current > approval-hook-ran\n", encoding="utf-8")
    commit_hook.chmod(0o755)

    approved = hook(repo, payload)
    assert approved.returncode == 0, approved.stderr
    assert (shop / "approval-hook-ran").read_text(encoding="utf-8").strip() == "story/SHOP"
    assert "Recorded the approval of Shoppers can save a basket." in approved.stdout
    assert other.git("rev-parse", "story/SHOP") != before
    assert "plans/SHOP.md" in other.git("show", "--name-only", "--format=", "story/SHOP")
    assert len(_markers(repo)) == len(_markers(other)) == 1
    assert hook(repo, payload).stderr.startswith("This approval was already recorded once")
    assert hook(other, {**payload, "cwd": str(shop)}).stderr.startswith(
        "This approval was already recorded once")

    client = _other(repo, tmp_path, "client")
    # The waiting story predates the creation gate; this test exercises approval routing.
    setup(client, kind="forge-source", keys=("SHOP",))
    client_doc = DOC.replace("save a basket", "keep a basket")
    client_story = ready(client, "SHOP", client_doc)
    (client_story / "forge.toml").write_text(
        (client_story / "forge.toml").read_text("utf-8").replace(
            'repo = "forge-source"', 'repo = "client"'), encoding="utf-8")
    client.write("forge.toml", (client.path / "forge.toml").read_text("utf-8").replace(
        'repo = "forge-source"', 'repo = "client"'))
    client.git("commit", "-q", "-am", "Make this a client repo")
    client.git("push", "-q", "origin", "main")
    assert client.forge("next").returncode == 0
    client_head = client.git("rev-parse", "story/SHOP")
    client_approval = claude_plan(claude_payload, client_doc)
    refused = hook(repo, client_approval)
    assert refused.stderr.startswith("This client's sign-off isn't recorded yet")
    assert client.git("rev-parse", "story/SHOP") == client_head

    # A used event in the story repo alone is refused while the story still waits.
    marker_name = hashlib.sha256(
        f"claude\0{client_approval['session_id']}\0{client_approval['tool_use_id']}".encode()).hexdigest()
    marker = Path(client.git("rev-parse", "--path-format=absolute", "--git-common-dir"))
    marker = marker / "forge" / "approvals" / marker_name
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("used", encoding="utf-8")
    assert hook(repo, client_approval).stderr.startswith("This approval was already recorded once")
    marker.unlink()
    client.write("docs/decisions/0001-client-signoff.md", "---\nstatus: accepted\n---\n")
    client.git("add", "-A")
    client.git("commit", "-q", "-m", "The client signed off")
    client.git("push", "-q", "origin", "main")
    assert hook(repo, client_approval).returncode == 0

    # A matching waiting story in each repo makes the approval ambiguous.
    ready(other, "TWIN", twin)
    head = other.git("rev-parse", "story/TWIN")
    ambiguous = hook(repo, claude_plan(claude_payload, twin))
    assert ambiguous.returncode == 1
    assert "matches 2 story docs, so nothing was recorded" in ambiguous.stderr
    assert other.git("rev-parse", "story/TWIN") == head


def test_4_other_repo_version_refusal_precedes_config(repo, tmp_path, claude_payload):
    setup(repo, keys=("LOCAL",))
    other = _other(repo, tmp_path)
    setup(other, keys=("SHOP",))
    shop = ready(other, "SHOP")
    assert other.forge("next").returncode == 0
    head = other.git("rev-parse", "story/SHOP")
    version = repo.forge("--version").stdout.split()[-1]
    # The config is deliberately invalid beyond its pin. The version refusal must win.
    (shop / "forge.toml").write_text('version = "v0.0.1"\nrepo = "invalid"\n', encoding="utf-8")
    refused = hook(repo, claude_plan(claude_payload, DOC))
    assert refused.returncode == 1
    assert refused.stderr == (
        f"{other.path} pins Forge v0.0.1, but {version} is installed, so nothing was recorded.\n"
        f"Next: ask your agent to upgrade {other.path} to {version}, then approve again\n")
    assert other.git("rev-parse", "story/SHOP") == head
    assert not _markers(other)
