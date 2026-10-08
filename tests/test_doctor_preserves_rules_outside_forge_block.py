"""Doctor owns only the Forge block in AGENTS.md, in new and previously adopted clients."""
import pytest

from test_doctor_batches_file_checks import _adopted_client
from test_doctor_fix_files import _folder_of, _land, _set, _start_fix

STORY = "fix-agents-block-doctor"
BEGIN, END = b"<!-- forge:begin -->", b"<!-- forge:end -->"


@pytest.mark.parametrize("adoption", ["new init", "previous release"])
@pytest.mark.parametrize("location", ["outside", "inside"])
@pytest.mark.parametrize("state", ["committed", "unstaged", "staged"])
def test_1_doctor_refreshes_only_forge_owned_block_and_keeps_client_rules(
        repo, gh, tmp_path, monkeypatch, adoption, location, state):
    # Existing whole-file protection mistook the required Review rules for Forge edits.
    # Exercise real git history, index and working files; fake only external host tools.
    monkeypatch.setenv("FORGE_NOW", "2026-10-08T09:00:00+00:00")
    client = _adopted_client(repo, gh, tmp_path, monkeypatch, adoption)
    _land(repo, client, "Upgrade Forge", lambda folder: _set(
        folder, "AGENTS.md", "<!-- forge:begin -->\nOld Forge guidance.\n<!-- forge:end -->\n"),
        forge=True)
    folder = client if state == "committed" else _start_fix(repo, client)
    agents = folder / "AGENTS.md"
    prefix = "# Client rules: café\n\n".encode("utf-8")
    suffix = b"\n\n## Review rules\n\n- Keep our API stable.  \n\n"
    if state == "unstaged":
        prefix, suffix = prefix.replace(b"\n", b"\r\n"), suffix.replace(b"\n", b"\r\n")
    block = BEGIN + b"\nOld Forge guidance.\n" + END
    edited = block.replace(b"Old Forge guidance.", b"Our hand-edited Forge guidance.") if location == "inside" else block
    content = prefix + edited + suffix
    if state == "committed":
        if location == "inside":
            _land(repo, client, "Edit Forge guidance", lambda clone: (
                clone / "AGENTS.md").write_bytes(edited + b"\n"))
        # The most recent whole-file commit changes only client-owned lines, even
        # when a prior hand edit inside the block must still hold the file.
        _land(repo, client, "Add our Review rules", lambda clone: (
            clone / "AGENTS.md").write_bytes(content))
    else:
        agents.write_bytes(content)
        if state == "staged":
            repo.git("add", "AGENTS.md", cwd=folder)
            if location == "inside":
                agents.write_bytes(prefix + block + suffix)  # index-only block edit stays held
    before = agents.read_bytes()
    index = repo.git("diff", "--cached", cwd=folder)
    listed = repo.forge("doctor", cwd=folder)
    held = location == "inside"
    reason = "was changed by hand" if state == "committed" else "has changes not committed yet"
    assert (f"AGENTS.md {reason}" in listed.stdout) == held, listed.stdout + listed.stderr
    assert agents.read_bytes() == before

    repaired = repo.forge("doctor", "--fix", cwd=folder)

    assert (f"AGENTS.md {reason}" in repaired.stdout) == held, repaired.stdout + repaired.stderr
    if held:
        assert agents.read_bytes() == before
        assert repo.git("diff", "--cached", cwd=folder) == index
    else:
        if state == "committed":
            assert agents.read_bytes() == before  # default branch repairs in its own fix
            folder = _folder_of(repo, client, "fix/forge-files-20261008-0900")
        result = (folder / "AGENTS.md").read_bytes()
        assert result.startswith(prefix) and result.endswith(suffix), result
        assert b"Old Forge guidance." not in result
        assert b"## Working here with Forge" in result
        checked = repo.forge("doctor", cwd=folder)
        assert "AGENTS.md differs" not in checked.stdout, checked.stdout + checked.stderr
