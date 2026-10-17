"""Close reviews binary additions, changes and deletions without bundling their contents."""
import pytest

from test_close import GREEN, env  # noqa: F401
from test_close_always_tests import adopt_earlier
from test_close_reviews_screenshots import png
from test_fix_review_bundles_include_generated_files_s import _record_bundles
from test_setup import _fresh_client

STORY = "review-image-deletes"


@pytest.mark.parametrize("adopted", [False, True], ids=["init", "earlier-adoption-upgrade"])
def test_1_close_reviews_deleted_and_changed_images_as_names_only(env, adopted):
    if adopted:
        adopt_earlier(env)
        env.repo.git("switch", "-q", "main")
        env.repo.git("merge", "-q", "--ff-only", "fix/adopt")
    else:
        client, initialized = _fresh_client(env.repo, env.gh, env.tmp)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        env.repo.path = client
        env.checks(GREEN)
    for path in ("removed image.png", "changed.png"):
        (env.repo.path / path).write_bytes(png())
    env.repo.git("add", "-A")
    # Seed the pre-existing assets, as if their earlier pull request had merged.
    env.repo.git("-c", "core.hooksPath=/dev/null", "commit", "-qm", "Add original images")
    env.repo.git("-c", "core.hooksPath=/dev/null", "push", "-q", "origin", "main")
    _record_bundles(env)
    item, where = env.start_fix(done_when="Images can be removed or changed")
    (where / "removed image.png").unlink()
    (where / "changed.png").write_bytes(png() + b"changed")
    (where / "added.png").write_bytes(png())
    (where / "asset.dat").write_bytes(b"binary\0asset")
    env.repo.git("add", "-A", cwd=where)
    env.repo.git("commit", "-qm", "Change binary assets", cwd=where)

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    diff = (env.tmp / "reviews.json.diff").read_text("utf-8")
    assert "+print('hello')" in diff
    for path in ("removed image.png", "changed.png", "added.png", "asset.dat"):
        assert path not in diff
        assert f"{path}: - added, - removed" in env.prompt()
    # Filtering affects only the review copy; the real branch keeps the intended changes.
    assert not (where / "removed image.png").exists()
    assert (where / "changed.png").read_bytes() == png() + b"changed"
    assert (where / "added.png").read_bytes() == png()
    assert len(env.review_calls()) == 1
