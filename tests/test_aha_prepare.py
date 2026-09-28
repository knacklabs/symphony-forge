"""The agent prepares, listens and recaps, and new projects no longer go to /office-hours.

Checked in the skill and FDE page as `forge sync` writes them into a client repo.
"""
from pathlib import Path

STORY = "FORGE-AHA-1"

ROOT = Path(__file__).resolve().parents[1]
HOSTS = (".claude", ".codex")


def _synced(repo) -> dict[str, str]:
    """Each synced page, identical for both hosts, with line wraps flattened."""
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "client"\n')
    repo.git("checkout", "-q", "-b", "fix/prepare-and-listen")
    done = repo.forge("sync")
    assert done.returncode == 0, done.stderr
    pages = {}
    for name in ("SKILL.md", "fde.md"):
        copies = {(repo.path / host / "skills/forge" / name).read_text(encoding="utf-8")
                  for host in HOSTS}
        assert len(copies) == 1, name
        pages[name] = " ".join(copies.pop().split())
    return pages


def test_1_the_agent_prepares_listens_and_recaps(repo):
    pages = _synced(repo)
    discovery = pages["SKILL.md"].split(" ## Discovery ")[1].split(" ## ")[0]
    for rule in (
        # Before the first meeting: the brief from their website.
        "Before the first meeting, draft a one-page pre-meeting brief in `docs/context/` from the "
        "prospect's website", "their likely jobs", "two or three guessed problem cards each marked "
        "`(guess)`", "their terms", "the first five questions",
        # During discovery: their words and their spreadsheet's headers.
        "keep the customer's own words in `## Words they use` in `docs/product/DISCOVERY.md`",
        "`- <their word>: <what it means>`",
        "Ask for the spreadsheet or form they use today and keep only its column headers, never "
        "its rows",
        # The same day: the recap they confirm, and their reply as the answers' source.
        "The same day, draft a recap in `docs/context/` for the customer to confirm",
        "their problem in their words", "the cost in their numbers",
        "the one task the demo will cover", "who signs off",
        'the open "ask the client" questions', "the demo date",
        "record the Demo workflow and Sign-off person answers from it, with `client recap reply` "
        "as the source",
    ):
        assert rule in discovery, rule

    fde = pages["fde.md"]
    brief = fde.split(" ## Pre-meeting brief ")[1].split(" ## Recap ")[0]
    for field in ("`docs/context/`", "website", "Likely jobs:", "Their terms:", "(guess)",
                  "## First five questions"):
        assert field in brief, field
    recap = fde.split(" ## Recap ")[1].split(" ## Question bank ")[0]
    for field in ("`docs/context/`", "same day", "Your problem: <in their words>",
                  "What it costs: <in their numbers>", "The demo will cover:", "Who signs off:",
                  'Still to find out: <each open "ask the client" question>', "Demo date:",
                  "- Demo workflow: <task> (client recap reply, <YYYY-MM-DD>)"):
        assert field in recap, field
    script = fde.split(" ## Customer call script ")[1]
    assert "keep only its column headers, never its rows" in script
    assert "`## Words they use`" in script


def test_8_no_page_sends_a_new_project_to_office_hours(repo):
    pages = _synced(repo)
    for name, page in pages.items():
        assert "office-hours" not in page and "gstack" not in page, name

    [decision] = (ROOT / "docs/decisions").glob("*-discovery-without-office-hours.md")
    text = decision.read_text(encoding="utf-8")
    front = text.split("---\n")[1]
    assert "status: accepted" in front
    assert 'confirmed_by: "Ravi Kiran Vemula"' in front
    assert "../specs/fde-discovery.md" in text and "Forge's own discovery" in text
