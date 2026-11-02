"""Sign-off scope and decision sections through the command boundary."""
from __future__ import annotations

import json

import pytest

from test_proto_signoff import _adopted_client, _client, _decision

STORY = "FORGE-PACE-1/SIGNOFF"


def _calls(queue):
    path = queue.with_suffix(".calls.jsonl")
    return [json.loads(line) for line in path.read_text("utf-8").splitlines()] if path.exists() else []


def _refuses_app_code_until_a_build_is_requested(repo, tmp_path, monkeypatch, starter):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch, working_build=False)
    page = _decision(fix, answers)
    name = "apps/web/src/app.tsx" if starter else "app.py"
    # A screen on main already counts as a working build. Add the first screen only here,
    # so the command still checks app code introduced before a build request.
    source = fix / name
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("export function App() { return <main>Prototype</main>; }\n"
                      if starter else "print('working prototype')\n", encoding="utf-8")
    repo.git("add", name, cwd=fix)
    repo.git("commit", "-q", "-m", "Add prototype code", cwd=fix)

    refused = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "forge decision new prototype-plan" in refused.stderr
    assert "status: proposed" in page.read_text("utf-8")
    assert not _calls(queue)


def _old_accepted_signoff_needs_no_new_design_check(repo, tmp_path, monkeypatch):
    fix, _, queue = _adopted_client(repo, tmp_path, monkeypatch, old_signoff=True)

    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert "already accepted" in accepted.stdout
    assert not _calls(queue)


def _new_signoff_decision_names_the_pinned_sections(repo, tmp_path, monkeypatch):
    fix, _, _ = _client(repo, tmp_path, monkeypatch, working_build=False)

    created = repo.forge("decision", "new", "client-signoff", cwd=fix)

    assert created.returncode == 0, created.stdout + created.stderr
    template = next((fix / "docs/decisions").glob("*-client-signoff.md")).read_text("utf-8")
    for section in ("## Signed design", "## Proof", "## Decisions"):
        assert section in template


@pytest.mark.parametrize(("check", "args"), [
    (_refuses_app_code_until_a_build_is_requested, (False,)),
    (_refuses_app_code_until_a_build_is_requested, (True,)),
    (_old_accepted_signoff_needs_no_new_design_check, ()),
    (_new_signoff_decision_names_the_pinned_sections, ()),
], ids=["new-code", "starter-screen", "old-signoff", "decision-sections"])
def test_2_client_signoff_scope(repo, tmp_path, monkeypatch, check, args):
    check(repo, tmp_path, monkeypatch, *args)
