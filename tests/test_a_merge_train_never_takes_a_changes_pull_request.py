"""The fake gh gives a merge train's pull request a number no change has, even when the raw numbers meet."""
from test_close import env  # noqa: F401
from test_queue_land_all import _number, client  # noqa: F401
from test_train_land_all import _all, _merge_heads, _ready, train  # noqa: F401

STORY = "FIX-TRAIN-TESTS-RUN-OUT-OF-TIME"


def test_2_a_train_whose_raw_number_is_a_changes_number_still_merges_the_changes_together(train, monkeypatch):
    env = train
    heads = _ready(env, monkeypatch, ("aa", "bb", "cc"))
    (env.repo.bin / "train-crc-of").write_text("fix/aa", "utf-8")  # the train's raw number is aa's number
    done = _all(env)
    lines = done.stdout.splitlines()
    text = done.stdout + done.stderr
    assert done.returncode == 0, text
    assert "Train: the combined check passed. Forge merges 3 changes in order." in lines, text
    assert not any("changed after the combined check" in line for line in lines), text
    assert not any(f"{slug}: Closing {slug}." in lines for slug in heads), text  # nobody went one at a time
    assert _merge_heads(env) == [(_number(f"fix/{slug}"), heads[slug]) for slug in ("aa", "bb", "cc")], text
