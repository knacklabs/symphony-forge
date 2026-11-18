"""forge land <item> <item> merges just those items in one merge train and leaves the rest alone."""
from test_close import env  # noqa: F401
from test_queue_land_all import _fix, _number, client  # noqa: F401
from test_train_land_all import _merge_heads, _ready, train  # noqa: F401

STORY = "FIX-FORGE-LAND-ALL-TAKES-EVERY-ITEM-IN-CLOSE"


def test_1_two_named_items_are_tested_together_once_and_the_third_is_left_alone(train, monkeypatch):
    env = train
    heads = _ready(env, monkeypatch, ("aa", "bb", "cc"))
    unknown = env.repo.forge("land", "aa", "nope")
    assert unknown.returncode == 1 and "nope" in unknown.stderr, unknown.stdout + unknown.stderr
    assert not env.gh_calls("pr", "merge")
    done = env.repo.forge("land", "aa", "bb", timeout=600)
    lines = done.stdout.splitlines()
    text = done.stdout + done.stderr
    assert done.returncode == 0, text
    assert "Train: testing 2 ready changes together: aa, bb." in lines, text
    assert "Train: the combined check passed. Forge merges 2 changes in order." in lines, text
    assert not any(f"{slug}: Closing {slug}." in lines for slug in ("aa", "bb")), text  # no re-test per merge
    assert _merge_heads(env) == [(_number(f"fix/{slug}"), heads[slug]) for slug in ("aa", "bb")], text
    assert not any("cc" in line for line in lines if line.startswith(("Starting", "Train:"))), text
