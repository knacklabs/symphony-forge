from __future__ import annotations

import json
import sys
from pathlib import Path

from test_gates import HARNESS, git, load_factory_lib, repo  # noqa: F401

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))


def _seed(repo: Path) -> None:
    lib = load_factory_lib(repo)
    control = Path(git(repo, "rev-parse", "--absolute-git-dir")) / "forge"
    control.mkdir(parents=True, exist_ok=True)
    lib.dump_json(control / "run.json", {"issue_key": "ENG-1"})


def _lifecycle(repo: Path, launch_id: str, statuses: tuple[str, ...]) -> Path:
    from forge_cli.delegate import delegations_path  # noqa: E402

    path = delegations_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for index, status in enumerate(statuses):
            fh.write(json.dumps({
                "launch_id": launch_id,
                "task": "grill-plan",
                "story": "ENG-1",
                "at": f"2026-09-07T10:00:0{index}+00:00",
                "launch_status": status,
                "write": False,
            }) + "\n")
    return path


def _repeat_read_is_refused(repo: Path) -> bool:
    from forge_cli.grill import _refuse_a_second_cold_read  # noqa: E402

    try:
        _refuse_a_second_cold_read(repo, "grill-plan", "plan", "")
    except SystemExit:
        return True
    return False


def test_a_failed_terminal_launch_does_not_consume_the_cold_read(repo: Path):
    _seed(repo)
    _lifecycle(repo, "failed", ("starting", "running", "failed"))

    assert not _repeat_read_is_refused(repo)


def test_a_succeeded_terminal_launch_refuses_another_cold_read(repo: Path):
    _seed(repo)
    _lifecycle(repo, "succeeded", ("starting", "running", "succeeded"))

    assert _repeat_read_is_refused(repo)


def test_a_host_native_preparation_consumes_the_cold_read(repo: Path):
    """Preparing the cold reader is the native release budget boundary.

    The host owns ``spawn_agent``, so Forge never receives a child-process
    terminal row.  Allowing a second preparation would therefore release a
    second independent reader before the first result is recorded.
    """
    _seed(repo)
    path = _lifecycle(repo, "native-preparation", ("prepared",))
    row = json.loads(path.read_text(encoding="utf-8"))
    row.update({
        "transport": "host-native",
        "preparation_id": "native-preparation",
        "artifact_sha256": "a" * 64,
    })
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    assert _repeat_read_is_refused(repo)


def test_starting_and_running_launches_block_an_overlapping_cold_read(
        repo: Path, monkeypatch):
    _seed(repo)
    _lifecycle(repo, "starting", ("starting",))
    _lifecycle(repo, "running", ("running",))
    from forge_cli import codex_status  # noqa: E402
    monkeypatch.setattr(codex_status, "dead_launches", lambda _base: [])

    assert _repeat_read_is_refused(repo)


def test_dead_starting_or_running_launch_does_not_consume_cold_read(
        repo: Path, monkeypatch):
    _seed(repo)
    _lifecycle(repo, "stale", ("starting", "running"))
    from forge_cli import codex_status  # noqa: E402
    monkeypatch.setattr(
        codex_status, "dead_launches",
        lambda _base: [{"launch_id": "stale"}],
    )

    assert not _repeat_read_is_refused(repo)


def test_cold_read_exclusion_holds_the_exact_gate_task_lock(repo: Path):
    from forge_cli import delegate  # noqa: E402

    key = "grill-task-T1"
    path = delegate.delegation_lock_path(repo, key, namespace="grill")
    with delegate.delegation_exclusion(
            repo, key, kind="grill-cold-read", namespace="grill"):
        assert delegate._lock_is_held(path)


def test_launch_lifecycle_rows_are_collapsed_by_launch_id(repo: Path):
    _seed(repo)
    _lifecycle(repo, "failed", ("starting", "running", "failed"))
    _lifecycle(repo, "succeeded", ("starting", "running", "succeeded"))

    from forge_cli import grill  # noqa: E402

    latest = grill._latest_launch_rows(
        repo, "grill-plan", "", story="ENG-1",
    )
    assert [(row["launch_id"], row["launch_status"]) for row in latest] == [
        ("failed", "failed"),
        ("succeeded", "succeeded"),
    ]
    assert _repeat_read_is_refused(repo)


def test_reading_the_guard_does_not_write_a_new_ledger_field(repo: Path):
    _seed(repo)
    path = _lifecycle(repo, "failed", ("starting", "running", "failed"))
    before = path.read_text(encoding="utf-8")

    assert not _repeat_read_is_refused(repo)
    assert path.read_text(encoding="utf-8") == before
    assert all(set(json.loads(line)) == {
        "launch_id", "task", "story", "at", "launch_status", "write",
    } for line in before.splitlines())
