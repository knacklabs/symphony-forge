"""Bare test explains the sample-data skip without hiding a configured command.

Test audit: protect the real command's skip reason and its normal execution path.
The shared reader clears effective commands for sample prototypes, which caused
the false missing-command message. Existing sample tests cover close and merge,
not this message. Reuse their client fixtures without a new production seam.
"""
import pytest

from test_sample_setup import _prepared_client, _settings

STORY = "FIX-TEST-COMMAND-FOUND-ON-WINDOWS"


@pytest.mark.platform
@pytest.mark.parametrize("case,source", [
    ("new client", "setting"),
    ("new client", "sign-off"),
    ("earlier adopted", "sign-off"),
])
def test_1_test_explains_sample_data_and_runs_configured_commands(repo, gh, tmp_path, case, source):
    marker = tmp_path / "configured-test-ran"
    top, config = _prepared_client(repo, gh, tmp_path, case, marker)
    # Exercise test itself, rather than an identical fast_test hiding its absence.
    _settings(config, fast_test="")
    if source == "sign-off":
        config.write_text("\n".join(line for line in config.read_text("utf-8").splitlines()
                                    if not line.startswith("sample_data = ")) + "\n", "utf-8")
        repo.write("docs/decisions/0001-client-signoff.md",
                   "---\nstatus: draft\nsample_data: true\n---\n# Client sign-off\n")
    # CRLF is what Windows tools normally write. A BOM instead causes a separate
    # parse refusal, not the misleading message this regression protects.
    config.write_bytes(config.read_text("utf-8").replace("\n", "\r\n").encode("utf-8"))
    skipped = repo.forge("test")
    assert skipped.returncode == 0, skipped.stdout + skipped.stderr
    assert skipped.stdout == (
        "This is a sample-data prototype, so tests are off until client sign-off.\n"
        "After sign-off, ask the coordinator to set sample_data = false in forge.toml.\n")
    assert not marker.exists()

    # An explicit false overrides even an earlier sign-off's sample-data flag.
    _settings(config, sample_data=False)
    config.write_bytes(config.read_text("utf-8").replace("\n", "\r\n").encode("utf-8"))
    repo.git("update-ref", "refs/remotes/origin/main", "HEAD", cwd=top)
    ran = repo.forge("test")
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert marker.read_text("utf-8") == "ran"
    assert "names no test command" not in ran.stdout

    _settings(config, test="")
    absent = repo.forge("test")
    assert absent.returncode == 0, absent.stdout + absent.stderr
    assert absent.stdout == "forge.toml names no test command, so forge test ran none.\n"
