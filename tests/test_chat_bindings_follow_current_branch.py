"""Returning machines follow the replacement chat committed on the work branch.

Audit: previous continuity tests erase local records; they do not retain an old
machine's record after another machine commits a replacement. Real work/read
commands own both bindings. Only the providers' retained conversations are faked.
"""
import json

import pytest

from test_codex_worker import sdk_data  # noqa: F401
from test_worker_and_reader_chats_survive_rounds import (
    _chat, _client_reader, _reader_chat, _work, _worker,
)

STORY = "reuse-worker-chats"


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "adopted-v1.2.2"])
@pytest.mark.parametrize("app", ["codex", "claude"])
@pytest.mark.parametrize("kind", ["worker", "reader"])
def test_21_returning_machine_resumes_the_committed_replacement_chat(
        repo, monkeypatch, tmp_path, sdk_data, adopted, app, kind):
    if kind == "worker":
        folder, item, log, record = _worker(repo, monkeypatch, sdk_data, app, "fix", adopted)
        run = lambda: _work(repo, item).stdout
        chat = lambda resumed=False: _chat(log, app, resumed)
    else:
        reader = _client_reader(repo, monkeypatch, tmp_path, sdk_data, app, adopted)
        folder = reader.shop
        record = repo.path / ".git/forge/threads/read/SHOP.json"
        run = reader.ok
        chat = lambda resumed=False: _reader_chat(reader, resumed)
    run()
    first = chat()
    old_record = record.read_bytes()
    store = repo.bin / ("threads.json" if app == "codex" else "claude-sessions.json")
    old_chats = json.loads(store.read_text("utf-8"))
    # Machine B cannot load A's chat. Keep an unrelated Codex chat so its stub
    # allocates a distinct replacement ID, just as the native provider does.
    unavailable = {key: value for key, value in old_chats.items() if key != first}
    if app == "codex":
        unavailable["unrelated"] = {"cwd": str(folder), "turns": {}}
    store.write_text(json.dumps(unavailable), encoding="utf-8")
    replacement_run = run()
    replacement = chat()
    assert replacement != first
    assert "Starting a new" in replacement_run

    # A fetches B's committed branch but retains its own local metadata and
    # native chat. Neither the branch nor its replacement binding is rewritten.
    record.write_bytes(old_record)
    store.write_text(json.dumps({**old_chats, **json.loads(store.read_text("utf-8"))}),
                     encoding="utf-8")
    for _ in range(2):
        resumed = run()
        assert chat(resumed=True) == replacement
        assert "Starting a new" not in resumed
