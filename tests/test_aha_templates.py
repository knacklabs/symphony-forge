STORY = "FORGE-AHA-1"

import re
import subprocess
from pathlib import Path

from test_worker import calls, install_claude


def _client(repo, gh, tmp_path):
    client, remote = tmp_path / "client", tmp_path / "client.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(client)], check=True)
    repo.git("remote", "add", "origin", str(remote), cwd=client)
    gh.respond("api", stdout="{}")
    gh.respond("api", "repos/{owner}/{repo}/branches/main/protection", exit=1,
               stdout='{"message":"Branch not protected","status":"404"}')
    made = repo.forge("init", cwd=client)
    assert made.returncode == 0, made.stderr
    return client


def _section(text, heading):
    return text.split(f"\n## {heading}\n")[1].split("\n## ")[0]


def _conventions(repo, client):
    # A worker reads the conventions from the folder its brief names, so read them from there.
    log = install_claude(repo)
    started = repo.forge("fix", "start", "Show their work", "--done", "The demo has data", cwd=client)
    assert started.returncode == 0, started.stderr
    fix = repo.git("worktree", "list", "--porcelain", cwd=client).split("worktree ")[-1].splitlines()[0]
    toml = Path(fix) / "forge.toml"  # the fix's own settings
    toml.write_text(toml.read_text(encoding="utf-8").replace('workers = "split"', 'workers = "claude"'),
                    encoding="utf-8")
    # Committed: a round that ends with changes uncommitted gets a second, commit-nudge turn.
    repo.git("commit", "-qam", "Use Claude workers", cwd=fix)
    built = repo.forge("work", "show-their-work", cwd=client)
    assert built.returncode == 0, built.stderr
    args = calls(log)[-1]["args"]
    folder = Path(args[args.index("--add-dir") + 1])
    assert f"`{folder}`" in calls(log)[-1]["brief"]
    return {p.name: " ".join(p.read_text(encoding="utf-8").split()) for p in folder.glob("*.md")}


def test_2_new_client_keeps_their_words_and_gets_guarded_demo_data(repo, gh, tmp_path):
    client = _client(repo, gh, tmp_path)
    notes = (client / "docs/product/DISCOVERY.md").read_text(encoding="utf-8")
    assert re.findall(r"^## (.+)$", notes, re.M) == [
        "Problems", "Stakeholders", "Words they use", "Customer call script",
        "Decisions the client approved", "Prototype notes"]
    words = _section(notes, "Words they use")
    assert re.findall(r"^- .+$", words, re.M) == ["- <their word>: <what it means>"]
    assert "screens and demo data are labelled" in words
    reactions = _section(notes, "Prototype notes")
    assert re.findall(r"^### (.+)$", reactions, re.M) == ["<YYYY-MM-DD>"]
    lines = re.findall(r"^- (Did|Said|Asked): (.+)$", reactions, re.M)
    assert [key for key, _ in lines] == ["Did", "Said", "Asked", "Asked"]
    assert re.fullmatch(r'".+"', dict(lines)["Said"])
    assert [value.rsplit(" (", 1)[1] for key, value in lines if key == "Asked"] == [
        "serves the problem)", "after sign-off)"]

    pages = _conventions(repo, client)
    assert "(see demo-data.md)" in pages["stack.md"]
    demo = pages["demo-data.md"]
    for rule in ("The loader lives in the app", "column headers",
                 'the "Words they use" list in `docs/product/DISCOVERY.md`',
                 "no real personal data",
                 "only when `APP_ENV=demo` and `DEMO_DATA=1` are both set and every app table is empty",
                 "Otherwise it refuses, logs why and inserts nothing",
                 "the app tables already hold rows. Point DATABASE_URL at an empty demo database, "
                 "or empty it, then start the app again",
                 "`npx prisma migrate deploy` before `node dist/main.js`",
                 "await app.get(DemoDataService).loadIfAllowed(); await app.listen(port);"):
        assert rule in demo, rule
    assert ("Shared seed data stays out of tests, the demo loader's too: demo data is allowed on "
            "the demo host only") in pages["testing.md"]


def test_3_agentation_toolbar_is_demo_only(repo, gh, tmp_path):
    frontend = _conventions(repo, _client(repo, gh, tmp_path))["frontend.md"]
    for rule in ("Agentation feedback toolbar", "click an element, write what's wrong and paste the "
                 "output to the agent", "only when `APP_ENV=demo` at run time",
                 "served `index.html`", '<meta name="app-env" content="%APP_ENV%">',
                 "replace %APP_ENV% with", "document.querySelector<HTMLMetaElement>('meta[name=app-env]')?.content",
                 "=== 'demo'", "never loads in production", "import('agentation')"):
        assert rule in frontend, rule
    # Helmet's default CSP (script-src 'self') blocks inline scripts, so the flag travels in a meta tag.
    assert "window.__APP_ENV__" not in frontend
