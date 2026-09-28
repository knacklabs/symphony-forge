STORY = "FORGE-PROTO-1"

TOPICS = (
    "Sign-off person", "Demo workflow", "Users and roles", "Existing systems",
    "Sign-in", "Personal data", "Production host", "Data import", "Email or SMS",
    "Domain", "Backups and uptime", "Log retention",
)


def test_4_sync_gives_both_agents_the_prototype_route_and_twelve_topics(repo):
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "forge-source"\n')
    repo.git("checkout", "-q", "-b", "fix/prototype-guidance")
    done = repo.forge("sync")
    assert done.returncode == 0, done.stderr
    copies = {(repo.path / host / "skills/forge/SKILL.md").read_text(encoding="utf-8")
              for host in (".claude", ".codex")}
    assert len(copies) == 1
    [skill] = copies
    prototype = skill.split("\n## Prototype\n")[1].split("\n## ")[0]
    assert "discovery" in prototype and "smallest working" in prototype
    assert "review" in prototype and "sign-off" in prototype and "stories" in prototype
    assert "one" in prototype and "Ask the client" in prototype and "Decide later" in prototype
    rows = [line.split("|")[1].strip() for line in prototype.splitlines()
            if line.startswith("| ") and line.split("|")[1].strip() in TOPICS]
    assert rows == list(TOPICS)
    assert prototype.count("| must |") == 7
    assert prototype.count("| may wait |") == 5
    assert "- <Topic>: <answer> (<source>, <YYYY-MM-DD>)" in prototype


def test_5_init_gives_new_client_one_answers_page_with_all_line_formats(repo, gh, tmp_path):
    import subprocess

    client, remote = tmp_path / "client", tmp_path / "client.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(client)], check=True)
    repo.git("remote", "add", "origin", str(remote), cwd=client)
    gh.respond("api", stdout="{}")
    gh.respond("api", "repos/{owner}/{repo}/branches/main/protection", exit=1,
               stdout='{"message":"Branch not protected","status":"404"}')
    made = repo.forge("init", cwd=client)
    assert made.returncode == 0, made.stderr
    brief = (client / "docs/product/BRIEF.md").read_text(encoding="utf-8")
    answers = brief.split("\n## Answers\n")[1].split("\n## ")[0]
    for line in ("- <Topic>: <answer> (<source>, <YYYY-MM-DD>)",
                 "- <Topic>: ask the client (<who asked>, <date>)",
                 "- <Topic>: later, when <trigger>"):
        assert line in answers


def test_9_cold_read_instructs_reader_to_resolve_deferred_answers(repo):
    # The real reader is an LLM; this guards the prompt delivered at the command boundary.
    import json
    import sys

    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "forge-source"\n'
               'models.grill.claude = { model = "opus", effort = "high" }\n')
    repo.write("plans/roadmap.json", json.dumps({"items": [{"key": "DEMO"}]}))
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Set up cold read")
    repo.git("push", "-q", "origin", "main")
    made = repo.forge("story", "new", "DEMO", "Demo the product")
    assert made.returncode == 0, made.stderr
    reader = repo.bin / "claude"
    reader.write_text(f'#!{sys.executable}\nimport pathlib, sys\n'
                      'pathlib.Path(__file__).with_name("prompt.txt").write_text(sys.stdin.read())\n'
                      'print("No findings.")\n', encoding="utf-8")
    reader.chmod(0o755)
    read = repo.forge("read", "DEMO")
    assert read.returncode == 0, read.stderr
    prompt = (repo.bin / "prompt.txt").read_text(encoding="utf-8")
    for instruction in ("docs/product/BRIEF.md", "later", "Decide first: <topic>",
                        "Decided: <topic>: <answer> (<source>, <date>)",
                        "first task", "disposition"):
        assert instruction in prompt
