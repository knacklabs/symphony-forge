"""The agent researches the prospect once, proposes one prototype, and keeps what it wrote.

Audit: the guide text is what the agent reads, so each test runs `forge init` or `forge sync`
and reads both hosts' copies of the Forge skill and the Discovery reference page. A missing
rule fails here; the page is written by the agent, so no code can check it and none is added.
The example company is made up.
"""
import pytest

from test_setup import _fresh_client
from test_uistandards_words import _adopted

STORY = "FORGE-PROSPECT-1"
HOSTS = (".claude", ".codex")


def _apps(client):
    return {p.relative_to(client).as_posix(): p.read_bytes()
            for folder in ("apps", "libs") if (client / folder).is_dir()
            for p in (client / folder).rglob("*") if p.is_file()}


def _pages(repo, gh, tmp_path, adopted):
    """Both hosts' guide copies after init or after sync on an earlier-adopted repo."""
    if adopted:
        client = _adopted(repo)
        before = _apps(client)
        made = repo.forge("sync")
    else:
        client, made = _fresh_client(repo, gh, tmp_path)
        before = _apps(client)
    assert made.returncode == 0, made.stdout + made.stderr
    assert _apps(client) == before
    assert not [p for p in client.rglob("prospect-research.md") if ".git" not in p.parts]
    pages = {}
    for name in ("SKILL.md", "fde.md"):
        copies = {(client / host / "skills/forge" / name).read_text(encoding="utf-8")
                  for host in HOSTS}
        assert len(copies) == 1, name
        pages[name] = " ".join(copies.pop().split())
    skill = pages["SKILL.md"]
    return {
        "discovery": skill.split(" ## Discovery ")[1].split(" ## ")[0],
        "prototype": skill.split(" ## Prototype ")[1].split(" ## ")[0],
        "step 1": skill.split("1. **Ideas and client notes.**")[1].split(" 2. **Brief.**")[0],
        "sales": skill.split("For a sales demo, save transcripts")[1].split("When the customer converts")[0],
        "fde": pages["fde.md"],
    }


def _has(text, rules):
    for rule in rules:
        assert rule in text, rule


@pytest.mark.parametrize("adopted", [False, True], ids=["init", "earlier-adoption"])
def test_1_the_agent_researches_the_prospect_in_one_bounded_pass(repo, gh, tmp_path, adopted):
    pages = _pages(repo, gh, tmp_path, adopted)
    discovery = pages["discovery"]
    _has(discovery, (
        "the company's name and website",
        "1. what it sells and to whom", "2. how it works today", "3. complaints from its customers",
        "4. its tools", "5. its job posts", "6. two or three close competitors",
        "12 web searches and 20 page reads", "8 searches and 14 page reads",
        "4 searches and 6 page reads", "an estimate, not a measurement",
        "one agent", "public pages", "sign-in", "by role", "own words",
        "`docs/context/prospect-research.md`",
        "Every finding under What we found has its own link to the public page it comes from; "
        "a finding without a link is not written.",
        "could not find", "up to five questions", "two or three companies of the same kind and size",
        "This session cannot search the web, so I could not research <company>.",
    ))
    assert "a company's name and website" in pages["step 1"]
    assert "research the company and propose one prototype before the design" in pages["sales"]
    brief = pages["fde"].split(" ## Pre-meeting brief ")[1].split(" ## Recap ")[0]
    _has(brief, ("Limit used:", "### What we found", "### Not found", "### For the look",
                 "### Questions for you", "Evidence:", "Likely jobs:", "Their terms:", "(guess)",
                 "## First five questions", "`docs/context/`", "website"))
    findings = brief.split("### What we found ")[1].split(" ### ")[0]
    assert findings.count("- ") >= 2
    assert all("](" in line for line in findings.split(" - ")[1:])


@pytest.mark.parametrize("adopted", [False, True], ids=["init", "earlier-adoption"])
def test_2_the_salesperson_chooses_one_prototype_before_any_build(repo, gh, tmp_path, adopted):
    pages = _pages(repo, gh, tmp_path, adopted)
    discovery = pages["discovery"]
    _has(discovery, (
        "one proposed prototype", "up to five features", "exactly one source mark",
        "two other possible prototypes",
        "`not researched` only when the session cannot search the web or the pass did not reach "
        "the item the idea depends on",
        "A point from a transcript is `heard from the customer: <note file in docs/context/>` "
        "with or without web search",
        "yes, picks another, or says in plain words what to change",
        "`## Chosen prototype, <YYYY-MM-DD>`", "the full chosen prototype with its marks",
        "`- Chosen by: salesperson: yes | option <n> | changed: <their words>`", "needs no mark",
        "`- Demo workflow: <task> (salesperson, <YYYY-MM-DD>)`",
        "Build nothing before this choice",
        "This proposal is not the Options step",
        "always with `Don't build` and `Smallest slice`",
    ))
    marks = ("- a link to a public page about this company;",
             "- `from similar companies: <company>` and a link to that company's page;",
             "- `heard from the customer: <note file in docs/context/>`;",
             "- `from the salesperson`",
             "- `not researched`")
    positions = [discovery.index(mark) for mark in marks]
    assert positions == sorted(positions)
    assert "`from the salesperson: <note file in docs/context/>`" in discovery
    assert "add a new dated `Chosen prototype` part" in discovery
    assert "the plan's demo steps come from the newest `Chosen prototype` part" in pages["prototype"]


@pytest.mark.parametrize("adopted", [False, True], ids=["init", "earlier-adoption"])
def test_3_a_second_pass_or_choice_adds_to_the_page(repo, gh, tmp_path, adopted):
    pages = _pages(repo, gh, tmp_path, adopted)
    assert ("A later research pass or a later choice adds a new dated part to the research page; "
            "never remove or rewrite an earlier part.") in pages["discovery"]
    _has(pages["fde"], ("## Research of <YYYY-MM-DD>", "## Chosen prototype, <YYYY-MM-DD>",
                        "## Proposed prototype, <YYYY-MM-DD>"))
