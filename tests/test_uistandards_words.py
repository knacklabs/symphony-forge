"""Delivered UI rules and non-blocking upgrades.

Audit: init/sync own this prompt and app-preservation contract. A missing rule
or sync entry fails it; package-byte tests do not cover these rules. No new
production seam is needed. Static prompt checks retain the public wording.
"""
import re
import shutil

import pytest

from conftest import ROOT
from test_setup import _fresh_client, _version

STORY = "FORGE-UISTANDARDS-1"


def _apps(client):
    return {p.relative_to(client).as_posix(): p.read_bytes()
            for folder in ("apps", "libs") for p in (client / folder).rglob("*") if p.is_file()}


def _adopted(repo):
    shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
    config = repo.path / "forge.toml"
    config.write_text(config.read_text(encoding="utf-8").replace(
        "v1.2.2", _version(repo)), encoding="utf-8")
    repo.git("switch", "-qc", "fix/ui-guidance")
    return repo.path


@pytest.mark.parametrize("adopted", [False, True], ids=["init", "earlier-adoption"])
def test_1_clients_receive_baseline_look_guards_and_operate(repo, gh, tmp_path, adopted):
    if adopted:
        client = _adopted(repo)
        before = _apps(client)
        made = repo.forge("sync")
    else:
        client, made = _fresh_client(repo, gh, tmp_path)
        before = {}
    assert made.returncode == 0, made.stdout + made.stderr
    assert _apps(client) == before
    for host in (".codex", ".claude"):
        text = (client / host / "skills/app-baseline/SKILL.md").read_text(encoding="utf-8")
        for rule in ('collapsible="icon"', '375', '24 pixel', '16 pixel',
                     '12, 14, 16, 20, 24 and 30', 'fewer than 7', '7 or more',
                     '2 to 4', 'partial data', 'industry', 'how often',
                     'work, read or persuade', 'brand words', 'brand files',
                     'DESIGN.md', 'document', '4.5 to 1', '3 to 1',
                     '44', 'reduced motion', 'Operate mode', 'terracotta'):
            assert rule in text, (host, rule)
    for filename in ("brief.md", "review.md"):
        text = " ".join((ROOT / "src/forge/templates" / filename).read_text(encoding="utf-8").split())
        assert "App screens and prototypes use impeccable's Operate mode" in text
    assert "Gate: UI standards" in (ROOT / "src/forge/templates/review.md").read_text(encoding="utf-8")


def test_4_sync_preserves_old_ui_and_adds_no_doctor_warning(repo):
    client = _adopted(repo)
    repo.write("apps/web/src/old.tsx", '<main className="p-[13px]"><h1>Old</h1><h1>Old</h1></main>\n')
    repo.write("libs/example/keep.ts", "export const keep = 1;\n")
    before_apps = _apps(client)
    before = {p.relative_to(client): p.read_bytes() for p in client.rglob("*")
              if p.is_file() and ".git" not in p.relative_to(client).parts}
    doctor_before = repo.forge("doctor")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert _apps(client) == before_apps
    changed = [p for p in client.rglob("*") if p.is_file()
               and ".git" not in p.relative_to(client).parts
               and before.get(p.relative_to(client)) != p.read_bytes()]
    assert changed
    for path in changed:
        path.read_bytes().decode("utf-8")
    doctor_after = repo.forge("doctor")
    assert doctor_after.returncode == doctor_before.returncode
    # Sync repairs old generated files and hooks, but must add no new warning.
    warnings_before = {line for line in doctor_before.stdout.splitlines() if line.startswith("- ")}
    warnings_after = {line for line in doctor_after.stdout.splitlines() if line.startswith("- ")}
    assert warnings_after <= warnings_before
    # Repairs reduce the summary count too. Keep every other stderr word checked.
    summary_count = r"(?<=forge doctor found )\d+(?= problem\(s\))"
    assert re.sub(summary_count, "<count>", doctor_after.stderr) == re.sub(
        summary_count, "<count>", doctor_before.stderr)
