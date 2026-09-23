"""The board's Contributors view, and the snapshot it now serves and pushes.

Contributors: one row per person however many identities they committed
under, bots left out, Forge commits told from plain ones, and the roles Forge
records credit them with.

Snapshot: `/api/state` used to be rebuilt inside every poll (17-59 s on a
30-story repo). It is now built once per change, served with an ETag (an
unchanged board answers 304 with no body), gzipped, and announced on
`/api/events` so an open board repaints without waiting for a poll.
"""
from __future__ import annotations

import gzip
import json
import os
import subprocess
import sys
import threading
import urllib.request
from datetime import date
from pathlib import Path

from test_gates import HARNESS, repo  # noqa: F401

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
from forge_cli import board, contributors  # noqa: E402


def _commit(root: Path, name: str, email: str, subject: str, day: str,
            body: str = "") -> None:
    env = {**os.environ, "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email,
           "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email,
           "GIT_AUTHOR_DATE": f"{day}T12:00:00", "GIT_COMMITTER_DATE": f"{day}T12:00:00"}
    message = subject + (f"\n\n{body}" if body else "")
    proc = subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", message],
                          cwd=root, env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def _history(tmp_path: Path) -> Path:
    root = tmp_path / "people"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    _commit(root, "Ana Silva", "ana@work.example", "APP-1 T1: capture the form", "2026-09-01")
    _commit(root, "Ana Silva", "ana@work.example", "feat(APP-2/T3): totals", "2026-09-10")
    # Same person on another laptop, first name only, GitHub no-reply email.
    _commit(root, "Ana", "123+Ana-S@users.noreply.github.com", "Fix a typo", "2026-09-12",
            body="Confirmed-by: Ana")
    _commit(root, "Ben Okafor", "ben@example.test", "Tidy the header", "2026-05-01")
    _commit(root, "Ben Okafor", "ben@example.test", "Polish tables", "2026-09-15")
    _commit(root, "forge-review", "review@forge.invalid", "APP-1 T1: review bundle", "2026-09-16")
    records = root / ".factory" / "stories" / "APP-1"
    records.mkdir(parents=True)
    (records / "approval.json").write_text(json.dumps(
        {"approved_by": "Ana", "generated_by": "orchestrator", "actor": "orchestrator"}))
    return root


def test_contributors_merge_identities_and_split_forge_from_plain_commits(tmp_path):
    data = contributors.build(_history(tmp_path), today=date(2026, 9, 20))
    people = {person["name"]: person for person in data["people"]}

    # Three identities, one person; the bot is not a contributor.
    assert set(people) == {"Ana Silva", "Ben Okafor"}
    ana, ben = people["Ana Silva"], people["Ben Okafor"]
    assert ana["handle"] == "Ana-S"                      # case kept from GitHub
    assert ana["aliases"] == ["Ana"]
    assert ana["emails"] == ["123+ana-s@users.noreply.github.com", "ana@work.example"]
    # Two story-scoped subjects and one Forge trailer: all three count.
    assert ana["windows"]["all"] == {"commits": 3, "forge": 3}
    assert ana["stories"] == ["APP-2", "APP-1"]          # most recent first
    # Only the human named in the record is credited, never the agent roles.
    assert ana["roles"] == ["Approves plans"]
    assert ana["first_commit"] == "2026-09-01" and ana["last_commit"] == "2026-09-12"

    assert ben["windows"]["all"] == {"commits": 2, "forge": 0}
    assert ben["windows"]["90"] == {"commits": 1, "forge": 0}   # May falls outside
    assert ben["roles"] == [] and ben["handle"] is None


def test_contributors_are_memoised_until_a_commit_lands(tmp_path, monkeypatch):
    root = _history(tmp_path)
    builds = []
    real = contributors.build
    monkeypatch.setattr(contributors, "build",
                        lambda base, today=None: builds.append(1) or real(base, today))
    contributors.contributors(root)
    contributors.contributors(root)
    assert len(builds) == 1
    _commit(root, "Ben Okafor", "ben@example.test", "One more", "2026-09-18")
    contributors.contributors(root)
    assert len(builds) == 2


def test_state_hub_bumps_its_version_only_when_the_content_changes(tmp_path):
    states = [{"generated_at": "t1", "stories": [1]},
              {"generated_at": "t2", "stories": [1]},     # same content, new clock
              {"generated_at": "t3", "stories": [1, 2]}]
    hub = board.StateHub(tmp_path, build=lambda _root: states.pop(0))
    assert hub.refresh() is True and hub.version == 1
    etag = hub.etag
    assert hub.refresh() is False and hub.version == 1 and hub.etag == etag
    assert hub.refresh() is True and hub.version == 2 and hub.etag != etag
    assert json.loads(gzip.decompress(hub.gzipped)) == json.loads(hub.body)
    # A stream waiting on version 1 wakes as soon as version 2 exists.
    assert hub.wait_for_change(1, timeout=0.1) == 2


def test_board_serves_etag_304_gzip_root_probe_and_event_stream(repo, monkeypatch):
    import factory_lib
    # make_server puts this process in board mode; restore CLI mode after.
    monkeypatch.setattr(factory_lib, "MARKER_FETCH_TTL", factory_lib.MARKER_FETCH_TTL)
    monkeypatch.setattr(factory_lib, "BOARD_MEMO", factory_lib.BOARD_MEMO)
    server = board.make_server(repo, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urllib.request.urlopen(f"{base}/api/state", timeout=30) as first:
            etag = first.headers["ETag"]
            assert etag and json.loads(first.read())["root"]

        unchanged = urllib.request.Request(f"{base}/api/state",
                                           headers={"If-None-Match": etag})
        try:
            urllib.request.urlopen(unchanged, timeout=30)
            raise AssertionError("an unchanged board must answer 304")
        except urllib.error.HTTPError as exc:
            assert exc.code == 304

        zipped = urllib.request.Request(f"{base}/api/state",
                                        headers={"Accept-Encoding": "gzip"})
        with urllib.request.urlopen(zipped, timeout=30) as response:
            assert response.headers["Content-Encoding"] == "gzip"
            assert json.loads(gzip.decompress(response.read()))["root"]

        with urllib.request.urlopen(f"{base}/api/root", timeout=5) as probe:
            assert Path(json.loads(probe.read())["root"]) == repo.resolve()

        with urllib.request.urlopen(f"{base}/api/events", timeout=30) as stream:
            assert stream.headers["Content-Type"] == "text/event-stream"
            assert stream.readline() == b"event: state\n"
            assert stream.readline().decode().strip() == f"data: {etag}"

        with urllib.request.urlopen(f"{base}/api/contributors", timeout=30) as people:
            assert "people" in json.loads(people.read())

        page = urllib.request.urlopen(base, timeout=5).read().decode()
        assert 'id="contributors-view"' in page and "/api/contributors" in page
        assert "EventSource" in page and "If-None-Match" in page
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
