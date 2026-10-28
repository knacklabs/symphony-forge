"""Command contracts for guide delivery, decision references and the sync notice.

Missing guidance, ambiguous IDs and repeated notices are independent regressions
without existing coverage. No production seam is needed; only the external worker
is stubbed to inspect the brief. Both setup paths exercise the public commands.
"""
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT, FORGE_SHIM, _install
from test_setup import _fresh_client, _version
from test_worker import calls, install_claude

STORY = "FORGE-SPECRULES-1"


@pytest.fixture(params=["new", "previous-release adoption"])
def client(repo, gh, tmp_path, request):
    if request.param == "new":
        top, made = _fresh_client(repo, gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
        started = repo.forge("fix", "start", "Check spec rules", "--done",
                             "Specs state each rule once", "--kind", "mechanical", cwd=top)
        assert started.returncode == 0, started.stdout + started.stderr
        top = tmp_path / "client-fix-check-spec-rules"
        item = "check-spec-rules"
    else:
        old = tmp_path / "previous-release"
        shutil.copytree(ROOT / "tests/fixtures/forge-v1.2.2", old)
        (old / "src/forge/cli-py.txt").rename(old / "src/forge/cli.py")
        _install(repo.bin, "old-forge", FORGE_SHIM.format(
            python=sys.executable, src=str(old / "src")))
        gh.respond("api", stdout="{}")
        made = subprocess.run([sys.executable, str(repo.bin / "old-forge"), "init",
                               "--test", "echo ok", "--checks", "tests",
                               "--interfaces", "api/routes/**", "--approver", "Owner",
                               "--merger", "Owner"], cwd=repo.path,
                              capture_output=True, text=True)
        assert made.returncode == 0, made.stdout + made.stderr
        top = tmp_path / "repo-fix-adopt-forge"
        item = "adopt-forge"
    config = top / "forge.toml"
    text = config.read_text("utf-8").replace('version = "v1.2.2"',
                                            f'version = "{_version(repo)}"')
    text = text.replace('workers = "split"', 'workers = "claude"').replace(
        'workers = "codex"', 'workers = "claude"')
    config.write_text(text, "utf-8")
    return top, item, request.param


def _ok(result):
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def _write(top, name, text):
    path = top / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, "utf-8")


def test_1_specs_state_each_rule_once(repo, client):
    top, item, setup = client
    log = install_claude(repo)
    readme = top / "docs/specs/README.md"
    before = readme.read_bytes() if readme.exists() else None
    if setup == "previous-release adoption":
        _ok(repo.forge("sync", cwd=top))
        assert (readme.read_bytes() if readme.exists() else None) == before
    else:
        text = readme.read_text("utf-8")
        assert "- R-1: An invoice goes out by email" in text
        assert "- AC-1 checks R-1:" in text
    for host in (".claude", ".codex"):
        text = " ".join((top / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert "state each rule once, on an `R-<n>:` line" in text
        assert "`forge decision accept` then lists every spec line that names that ID" in text
    repo.git("add", "-A", cwd=top)
    repo.git("commit", "-q", "-m", "Use current guidance", cwd=top)
    _ok(repo.forge("work", item, cwd=top))
    brief = " ".join(calls(log)[-1]["brief"].split())
    assert "state each rule once, on an `R-<n>:` line" in brief
    assert "When a change edits a rule, update the lines that name its ID in the same change." in brief


def test_2_accept_lists_the_spec_lines_that_name_its_rules(repo, client):
    top, _, _ = client
    _ok(repo.forge("sync", cwd=top))
    lines = ["- R-13: Only the owner sets the limits.",
             "- VAL-11 checks R-13: the top admin's settings page has no limits field.",
             "- AC-11 checks R-2 and R-13: issue a request and check its limits.",
             "- R-130: Another rule.", "- BR-13: A legacy rule."]
    _write(top, "docs/specs/admin.md", "\n".join(lines) + "\n")
    _write(top, "docs/specs/admin.read.md", "R-13 has a cold-read note.\n")
    _write(top, "docs/specs/README.md", "R-13 is an example.\n")
    decisions = {}
    for slug, choice in (("limits-move", "Change R-13. <!-- R-130 -->"),
                         ("plain-choice", "Keep the current choice. <!-- R-13 -->")):
        _ok(repo.forge("decision", "new", slug, cwd=top))
        path = next((top / "docs/decisions").glob(f"*-{slug}.md"))
        _write(top, path.relative_to(top), f"---\nstatus: proposed\n---\n\n# Choice\n\n"
               f"## Context\n\nLimits need a choice.\n\n## Decision\n\n{choice}\n\n"
               "## Consequences\n\nUse the chosen rule.\n")
        decisions[slug] = path.relative_to(top).as_posix()
    repo.git("add", "-A", cwd=top)
    repo.git("commit", "-q", "-m", "Propose choices", cwd=top)
    output = _ok(repo.forge("decision", "accept", "limits-move", "--by", "Ravi", cwd=top))
    assert output == (f"Accepted {decisions['limits-move']}, confirmed by Ravi.\n"
                      "These spec lines name R-13; in this change, update each one that no longer fits the decision:\n"
                      + "".join(f"docs/specs/admin.md:{n}: {line}\n"
                                for n, line in enumerate(lines[:3], 1)))
    assert _ok(repo.forge("decision", "accept", "plain-choice", "--by", "Ravi", cwd=top)) == (
        f"Accepted {decisions['plain-choice']}, confirmed by Ravi.\n")


def test_3_the_first_sync_flags_old_spec_lines_once(repo, client):
    top, _, setup = client
    lines = ["- VAL-11: The top admin cannot set the limits.",
             "| UAT-16 | The top admin sees no settings page |",
             "1. **AC-11**: The limits stay as set.",
             "- VAL-12 checks R-23: Check the limits.", "- BR-24: A legacy rule."]
    _write(top, "docs/specs/admin.md", "\n".join(lines) + "\n")
    _write(top, "docs/specs/admin.read.md", "- VAL-9: A note.\n")
    output = _ok(repo.forge("sync", cwd=top))
    header = "These spec lines seem to repeat a rule instead of naming its R- ID:"
    if setup == "previous-release adoption":
        notice = (header + "\n" + "".join(f"docs/specs/admin.md:{n}: {line}\n"
                  for n, line in enumerate(lines[:3], 1))
                  + 'Next: forge fix start "Specs state each rule once" --done '
                  '"Each VAL, UAT and AC line in docs/specs names the R- rule it checks" --kind mechanical\n')
        assert notice in output
        assert "docs/specs/admin.md:4:" not in output
        assert "docs/specs/admin.md:5:" not in output
        assert "docs/specs/admin.read.md:" not in output
        output = _ok(repo.forge("sync", cwd=top))
    assert header not in output
    assert "docs/specs/admin.md:" not in output
