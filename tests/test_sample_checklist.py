"""Done-when 6: forge next and the board show one sign-off status line and the open items."""
import json
from pathlib import Path

import pytest

from test_setup import _fresh_client

STORY = "FORGE-SAMPLE-1"

SETTLED = ("Sign-off person: Sam Lee, director (client, 2026-11-02)",
           "Demo workflow: settled (salesperson, 2026-11-02)",
           "Users and roles: settled (client, 2026-11-02)",
           "Existing systems: none (client, 2026-11-02)",
           "Sign-in: not known yet (client, 2026-11-02)",
           "Personal data: none (client, 2026-11-02)",
           "Production host: our platform (client, 2026-11-02)")
QUESTION = ("- Open question: Can staff expedite an order?\n"
            "  Touches: Order list\n"
            "  Why we ask: It changes the order list.\n"
            "  Default: No.\n"
            "  Why this default: It matches today's workflow.\n"
            "  If the default stands: Staff keep today's order.\n"
            "  Due: 2099-01-01\n"
            "  Gain 4, Work 2, Harm 3\n")


def brief(*replace):
    lines = list(SETTLED)
    for topic, new in replace:
        lines = [new if line.startswith(f"{topic}:") else line for line in lines]
    return "# Product brief\n\n## Answers\n" + "".join(f"- {line}\n" for line in lines)


@pytest.mark.platform
@pytest.mark.parametrize("adoption", ["new prototype", "earlier adopted"])
def test_6_signoff_status_and_open_items_show_in_next_and_on_the_board(repo, gh, tmp_path, adoption):
    if adoption == "new prototype":
        client, made = _fresh_client(repo, gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
    else:  # as tests/test_proto_next.py builds it
        client = repo.path
        version = repo.forge("--version").stdout.split()[-1]
        repo.write("forge.toml", f'version = "{version}"\nrepo = "client"\nstage = "prototype"\n')
    page = client / "docs/product/BRIEF.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(brief(("Demo workflow", "Demo workflow: ask the client (salesperson, 2026-11-02)"),
                          ("Users and roles", "Users and roles: later, when the team is chosen")),
                    encoding="utf-8")
    (client / "docs/decisions").mkdir(parents=True, exist_ok=True)
    (client / "docs/decisions/open-questions.md").write_text(
        "# Decisions\n\n## To confirm\n\n" + QUESTION, encoding="utf-8")

    def board():
        shown = repo.forge("board", "--json", cwd=client)
        assert shown.returncode == 0, shown.stdout + shown.stderr
        return json.loads(shown.stdout)["signoff"]

    # Two open topics and one open client question, with a signer: one line, then the checklist.
    line = "Sign-off: 3 open questions, signer Sam Lee"
    idle = repo.forge("next", cwd=client)
    assert idle.returncode == 0, idle.stderr
    assert line in idle.stdout.splitlines()
    assert "Open before sign-off" not in idle.stdout
    assert [row for row in idle.stdout.splitlines() if row.startswith("- ")] == [
        '- Demo workflow. Say: "The client answered Demo workflow: <answer>"',
        '- Users and roles. Say: "The client answered Users and roles: <answer>"',
        '- Can staff expedite an order. Say: "The client answered Can staff expedite an order: <answer>"']
    assert board() == {"line": line, "open": [
        {"item": "Demo workflow", "say": "The client answered Demo workflow: <answer>"},
        {"item": "Users and roles", "say": "The client answered Users and roles: <answer>"},
        {"item": "Can staff expedite an order", "say": "The client answered Can staff expedite an order: <answer>"}]}

    # A fix in progress: the line stays, the checklist goes.
    started = repo.forge("fix", "start", "Tidy the readme", "--done", "The readme is tidy",
                         "--kind", "mechanical", cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    busy = repo.forge("next", cwd=client)
    assert busy.returncode == 0, busy.stderr
    assert line in busy.stdout.splitlines()
    assert "Say:" not in busy.stdout
    assert len(board()["open"]) == 3  # the board always lists them

    # A "not known yet" answer is not listed, except Personal data.
    page.write_text(brief(("Personal data", "Personal data: not known yet (client, 2026-11-02)")),
                    encoding="utf-8")
    (client / "docs/decisions/open-questions.md").unlink()
    only = board()
    assert only == {"line": "Sign-off: 1 open question, signer Sam Lee", "open": [
        {"item": "Personal data", "say": "The client answered Personal data: <answer>"}]}

    # No signer, so that part is left out; nothing open, so no line at all.
    page.write_text(brief(("Sign-off person", "Sign-off person: later, when the client is chosen"),
                          ("Sign-in", "Sign-in: email and password (client, 2026-11-02)")),
                    encoding="utf-8")
    assert board()["line"] == "Sign-off: 1 open question"
    page.write_text(brief(), encoding="utf-8")
    assert board() == {"line": "", "open": []}
    assert "Sign-off:" not in repo.forge("next", cwd=client).stdout

    # A live repo has no sign-off list, whatever its brief says.
    page.write_text(brief(("Demo workflow", "Demo workflow: ask the client (salesperson, 2026-11-02)")),
                    encoding="utf-8")
    assert board()["open"]
    config = Path(client / "forge.toml")
    config.write_text(config.read_text("utf-8").replace('stage = "prototype"', 'stage = "live"'),
                      encoding="utf-8")
    assert board() == {"line": "", "open": []}
    assert "Sign-off:" not in repo.forge("next", cwd=client).stdout

    # No settings file at all: the board and forge next --json still work, with an empty list.
    config.unlink()
    for command in (("board", "--json"), ("next", "--json")):
        shown = repo.forge(*command, cwd=client)
        assert shown.returncode == 0, shown.stdout + shown.stderr
        assert json.loads(shown.stdout)["signoff"] == {"line": "", "open": []}
