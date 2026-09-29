STORY = "FORGE-LIVE-1"

from test_worker import calls, install_claude


def pin(repo):
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nworkers = "claude"\n'
                             'models.lite = { model = "sonnet", effort = "medium" }\n')


def synced(repo):
    repo.git("checkout", "-q", "-b", "fix/live-skill")
    done = repo.forge("sync")
    assert done.returncode == 0, done.stderr
    copies = {host: {name: (repo.path / host / "skills/forge" / name).read_text(encoding="utf-8")
                     for name in ("SKILL.md", "standards.md")}
              for host in (".claude", ".codex")}
    assert copies[".claude"] == copies[".codex"]
    return copies[".claude"]


def adopt_section(skill):
    return " ".join(skill.split("\n## Adopt a live app\n")[1].split("\n## ")[0].split())


def test_6_skill_adopts_a_live_app_and_repo_rules_win(repo):
    log = install_claude(repo)
    pin(repo)
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Pin Forge")
    repo.git("push", "-q", "origin", "main")
    started = repo.forge("fix", "start", "Try the brief", "--done", "The brief carries the rule")
    assert started.returncode == 0, started.stderr
    built = repo.forge("work", "try-the-brief")
    assert built.returncode == 0, built.stderr
    brief = calls(log)[-1]["brief"]
    simple = " ".join(brief.split("\n## Build simple\n")[1].split("\n## ")[0].split())
    assert ("Where the repo's own rules (its AGENTS.md House rules and conventions) differ, "
            "they win; these conventions apply only to a repo on the default stack.") in simple

    files = synced(repo)
    adopt = adopt_section(files["SKILL.md"])
    for step in ("`docs/context/codebase.md`", "by name only, never their values",
                 "who approves stories, who merges", "what must never be touched",
                 "one at a time", "`## House rules` in AGENTS.md, outside Forge's",
                 "first add a test that pins today's behaviour",
                 "Migrations only add", "previous version of the app",
                 "the team's own feature flags", "No production credentials on this machine"):
        assert step in adopt, step
    assert ("The repo's own rules, its AGENTS.md House rules and conventions, win where they "
            "differ from these default-stack conventions, which apply only to a repo on the "
            "default stack.") in " ".join(files["standards.md"].split())


def test_7_skill_brings_the_app_history_along(repo):
    pin(repo)
    adopt = adopt_section(synced(repo)["SKILL.md"])
    for step in ("existing decision records and design docs as Forge decisions",
                 "`Imported from <path>.`", "Don't rewrite them",
                 "review comments of about the last 100 merged pull requests",
                 "House rule citing the pull requests it came from",
                 "most-changed, most-reverted and most-hotfixed files",
                 "danger zones", "names it under Risks",
                 "open pull requests and branches in the report",
                 "colliding with a teammate's work"):
        assert step in adopt, step
