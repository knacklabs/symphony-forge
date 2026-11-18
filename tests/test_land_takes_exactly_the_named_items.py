"""forge land <item> <item> merges just those items in one merge train and leaves the rest alone."""
import pytest

from test_close import env  # noqa: F401
from test_fix_when_the_installed_forge_differs_from_th import _calls, _uv
from test_upgrade_pending import OLD, _pin_old
from test_queue_land_all import _fix, _number, client  # noqa: F401
from test_train_land_all import _merge_heads, _ready, train  # noqa: F401

STORY = "FIX-FORGE-LAND-ALL-TAKES-EVERY-ITEM-IN-CLOSE"
pytestmark = pytest.mark.platform


def test_1_two_named_items_are_tested_together_once_and_the_third_is_left_alone(train, monkeypatch):
    env = train
    heads = _ready(env, monkeypatch, ("aa", "bb", "cc"))
    unknown = env.repo.forge("land", "aa", "nope")
    assert unknown.returncode == 1 and "nope" in unknown.stderr, unknown.stdout + unknown.stderr
    assert not env.gh_calls("pr", "merge")
    before = len(env.gh_calls("pr", "create"))
    done = env.repo.forge("land", "aa", "bb", timeout=600)
    lines = done.stdout.splitlines()
    text = done.stdout + done.stderr
    assert done.returncode == 0, text
    assert "Train: testing 2 ready changes together: aa, bb." in lines, text
    assert "Train: the combined check passed. Forge merges 2 changes in order." in lines, text
    assert not any(f"{slug}: Closing {slug}." in lines for slug in ("aa", "bb")), text  # no re-test per merge
    assert _merge_heads(env) == [(_number(f"fix/{slug}"), heads[slug]) for slug in ("aa", "bb")], text
    assert not any("cc" in line for line in lines if line.startswith(("Starting", "Train:"))), text
    created = [call for call in env.gh_calls("pr", "create")[before:] if "forge-merge-train/" in " ".join(call)]
    assert len(created) == 1, text  # one combined check, not a second train
    assert not [call for call in env.gh.calls() if call[:2] in (["run", "rerun"], ["workflow", "run"])
                or call[:1] == ["api"] and "POST" in call], text


def test_2_named_items_run_the_pinned_release(repo):
    log = _uv(repo)
    version = _pin_old(repo)
    ran = repo.forge("land", "aa", "bb")
    assert ran.stderr == f"Forge {version} is installed, but this repo pins {OLD}, so {OLD} runs through uv.\n"
    assert [call["args"][-3:] for call in _calls(log)] == [["land", "aa", "bb"]]


def test_3_a_named_batch_skips_an_earlier_merge_and_lands_the_remaining_item(train, monkeypatch):
    env = train
    heads = _ready(env, monkeypatch, ("aa",))
    merged = env.repo.forge("merge", "aa")
    assert merged.returncode == 0, merged.stdout + merged.stderr
    assert not env.repo.git("branch", "--list", "fix/aa")
    heads.update(_ready(env, monkeypatch, ("bb",), first=2))

    done = env.repo.forge("land", "aa", "bb", timeout=600)
    text = done.stdout + done.stderr
    assert done.returncode == 0, text
    assert "Left out aa: its pull request already merged." in done.stdout.splitlines(), text
    assert "bb merged." in done.stdout.splitlines(), text
    assert _merge_heads(env) == [(_number(f"fix/{slug}"), heads[slug]) for slug in ("aa", "bb")], text
