"""Close regenerates conflicted sync output, but leaves code conflicts to the worker."""
import json
import shutil
import sys
from pathlib import Path

import pytest

import conftest
from test_close import GREEN, env
from test_setup import _fresh_client

STORY = "when-forge-close-merges-the-default-bran"


@pytest.mark.parametrize("kind", ["new", "adopted", "source", "source CRLF", "code conflict"])
def test_1_close_merges_sync_output_and_stops_on_code_conflicts(env, kind, tmp_path):
    repo = env.repo
    config = (repo.path / "forge.toml").read_text()
    if kind == "new":
        client, initialized = _fresh_client(repo, env.gh, tmp_path)
        assert initialized.returncode == 0, initialized.stderr
        repo = env.repo = conftest.Repo(client, repo.bin)
        repo.write("forge.toml", config)
        env.checks(GREEN)
    remote = Path(repo.git("remote", "get-url", "origin"))
    if kind == "adopted":
        shutil.copytree(conftest.ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.write("forge.toml", repo.git("show", "HEAD:forge.toml") + '\nrepo = "client"\n')
    if kind.startswith("source"):
        shutil.copytree(conftest.ROOT / "src", repo.path / "src",
                        ignore=shutil.ignore_patterns("__pycache__"))
        if kind == "source CRLF":
            # Git keeps canonical LF blobs while checking Markdown out as CRLF, on every OS.
            repo.write(".gitattributes", "*.md text eol=crlf\n")
        repo.write(".gitignore", "__pycache__/\n")
        for host in (".codex", ".claude"):
            shutil.copytree(conftest.ROOT / host / "skills", repo.path / host / "skills")
        repo.write("forge.toml", repo.git("show", "HEAD:forge.toml") + '\nrepo = "forge-source"\n')
        conftest._install(repo.bin, "forge", (
            f"#!{sys.executable}\nimport sys, subprocess\n"
            "from pathlib import Path\n"
            "root = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True).strip()\n"
            "sys.path.insert(0, str(Path(root) / 'src'))\n"
            "from forge.cli import main\nsys.exit(main())\n"))
    repo.git("checkout", "-q", "-b", "fix/setup")
    repo.write(".factory/fixes/setup.json", json.dumps({"kind": "fix", "status": "working",
               "branch": "fix/setup", "why": "Set up Forge", "done_when": "Forge is set up"}))
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Prepare the repo")
    repo.git("push", "-q", "origin", "HEAD:refs/heads/prepared")
    repo.git("update-ref", "refs/heads/main", repo.git("rev-parse", "HEAD"), cwd=remote)
    repo.git("fetch", "-q", "origin", "main")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Sync the repo")
    repo.git("push", "-q", "origin", "HEAD:refs/heads/setup")
    repo.git("update-ref", "refs/heads/main", repo.git("rev-parse", "HEAD"),
             cwd=remote)
    repo.git("fetch", "-q", "origin", "main")
    repo.git("checkout", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/setup")
    repo.git("checkout", "-q", "-b", "fix/default-update")
    env.commit(repo.path, ".factory/fixes/default-update.json", json.dumps({
        "kind": "fix", "status": "working", "branch": "fix/default-update",
        "why": "Refresh guidance", "done_when": "Guidance is current"}))
    # Both branches refresh stale output. Their templates change far apart and merge cleanly;
    # the generated copies also replace the same stale line and therefore conflict.
    skill = ".codex/skills/forge/SKILL.md"
    original = (repo.path / skill).read_text()
    guide = (repo.path / "AGENTS.md").read_text()
    env.commit(repo.path, "AGENTS.md", guide.replace("Working here with Forge", "Old guide", 1))
    env.commit(repo.path, skill, original.replace("# Forge", "# Old Forge", 1))
    env.commit(repo.path, "app.py", "print('base')\n")
    item, where = env.start_fix({skill: original.replace("# Forge", "# Worker Forge", 1),
                                 "AGENTS.md": guide.replace("Working here with Forge", "Worker guide", 1),
                                 "app.py": "print('worker')\n"})
    if kind.startswith("source"):
        template = "src/forge/templates/skill.md"
        if kind == "source CRLF":
            assert b"\r\n" in (where / template).read_bytes()
        text = (where / template).read_text()
        # write_text translates LF to CRLF on Windows. Keep these distant source edits LF;
        # close must resolve the generated copies, and must never discard a template conflict.
        for folder, content in ((where, text + "\nWorker guidance.\n"),
                                (repo.path, "<!-- Default guidance -->\n" + text)):
            (folder / template).write_bytes(content.encode("utf-8"))
            repo.git("add", "--", template, cwd=folder)
            repo.git("commit", "-q", "-m", "Update the skill template", cwd=folder)
    env.commit(repo.path, skill, original.replace("# Forge", "# Default Forge", 1))
    env.commit(repo.path, "AGENTS.md", "Default branch house rules.\n\n" +
               guide.replace("Working here with Forge", "Default guide", 1))
    if kind == "code conflict":
        env.commit(repo.path, "app.py", "print('default')\n")
    moved = repo.git("rev-parse", "HEAD")
    # Publish to a non-default ref through the real hooks; the remote then lands it on main.
    repo.git("push", "-q", "origin", "HEAD:refs/heads/default-update")
    repo.git("update-ref", "refs/heads/main", moved, cwd=remote)
    before = repo.git("rev-parse", "HEAD", cwd=where)
    closed = env.close(item)
    if kind == "code conflict":
        assert closed.returncode == 1
        assert "conflicts in" in closed.stderr and "app.py" in closed.stderr
        assert repo.git("rev-parse", "HEAD", cwd=where) == before
        assert repo.git("status", "--porcelain", cwd=where) == ""
        assert not env.review_calls()
        return
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Ready:" in closed.stdout
    repo.git("merge-base", "--is-ancestor", moved, "HEAD", cwd=where)
    repo.git("merge-base", "--is-ancestor", before, "HEAD", cwd=where)
    assert (where / "app.py").read_text() == "print('worker')\n"
    assert (where / "AGENTS.md").read_text().startswith("Default branch house rules.")
    assert "Working here with Forge" in (where / "AGENTS.md").read_text()
    merge = repo.git("rev-list", "--merges", "-1", "HEAD", cwd=where)
    assert len(repo.git("rev-list", "--parents", "-1", merge, cwd=where).split()) == 3
    assert (where / skill).read_text() != original.replace("# Forge", "# Default Forge", 1)
    if kind.startswith("source"):
        output = (where / skill).read_text()
        assert "Worker guidance." in output and "Default guidance" in output
    synced = repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stderr
    assert repo.git("status", "--porcelain", cwd=where) == ""
