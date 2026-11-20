"""forge close keeps deleted build output and generated file contents out of review input."""
from __future__ import annotations

from test_close import env  # noqa: F401

STORY = "review-skips-deleted-content"


def test_1_close_summarizes_deleted_and_generated_build_content(env):
    deleted = {}
    old_build = env.repo.path / "dist" / "obsolete"
    old_build.mkdir(parents=True)
    for number in range(89):
        name = f"chunk-{number:02d}.js"
        content = f"DELETED_BUILD_CONTENT_{number:02d}_".encode() + b"x" * 24_000 + b"\n"
        (old_build / name).write_bytes(content)
        deleted[f"dist/obsolete/{name}"] = (content, f"DELETED_BUILD_CONTENT_{number:02d}")

    assets = env.repo.path / "dist" / "assets"
    assets.mkdir(parents=True)
    originals = {
        # Short lines keep the suffix rule independent of the long-line rule.
        "bundle.map": "OLD_MAP_CONTENT_\n",
        "app.min.js": "OLD_MIN_JS_CONTENT_\n",
        "app.min.css": "OLD_MIN_CSS_CONTENT_\n",
        # This file was minified at the base and is ordinary text at the new head.
        "transition.js": "OLD_MINIFIED_TRANSITION_" + "t" * 2_000 + "\n",
        "mostly-long.js": "MOSTLY_OLD_CONTENT_" + "l" * 1_200 + "\nshort line\n"
        + "MOSTLY_OLD_TAIL_" + "q" * 1_200 + "\n",
        "exact-half.js": "EXACT_HALF_LONG_LINE_" + "h" * 1_200 + "\nEXACT_HALF_BEFORE\n",
    }
    for name, content in originals.items():
        (assets / name).write_text(content, encoding="utf-8")

    env.repo.git("add", "-A")
    env.repo.git("commit", "-q", "-m", "Track old build output")
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start(
        STORY,
        f"fix/{STORY}",
        f".factory/fixes/{STORY}.json",
        {"kind": "fix", "why": "Remove an obsolete build folder",
         "done_when": "Close reviews a large build-folder deletion",
         "allow_large": "The obsolete build folder has many tracked files"},
        {},
    )

    env.repo.git("rm", "-r", "-q", "--", "dist/obsolete", cwd=where)
    replacements = {
        "bundle.map": "NEW_MAP_CONTENT_\n",
        "app.min.js": "NEW_MIN_JS_CONTENT_\n",
        "app.min.css": "NEW_MIN_CSS_CONTENT_\n",
        "new.map": "ADDED_MAP_CONTENT_\u00e9\n",
        "transition.js": "NEW_ORDINARY_TRANSITION_CONTENT\n",
        "mostly-long.js": "MOSTLY_NEW_CONTENT_" + "n" * 1_200 + "\nshort line\n"
        + "MOSTLY_NEW_TAIL_" + "r" * 1_200 + "\n",
        "exact-half.js": originals["exact-half.js"].replace(
            "EXACT_HALF_BEFORE", "EXACT_HALF_AFTER"),
    }
    for name, content in replacements.items():
        (where / "dist" / "assets" / name).write_text(content, encoding="utf-8")
    env.commit(where, "src/app.py", "ORDINARY_CHANGE_REMAINS_VISIBLE = True\n")

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    call = env.review_calls()[0]
    diff = call["diff"]
    prompt = "\n\n".join(call["prompt_files"].values())
    review_input = diff + "\n" + prompt
    assert len(review_input.encode("utf-8")) < 100_000
    for path, (content, marker) in deleted.items():
        assert marker not in review_input
        assert f"deleted: {path} ({len(content)} bytes)" in prompt
    for name, marker in (
        ("bundle.map", "OLD_MAP_CONTENT_"),
        ("bundle.map", "NEW_MAP_CONTENT_"),
        ("app.min.js", "OLD_MIN_JS_CONTENT_"),
        ("app.min.js", "NEW_MIN_JS_CONTENT_"),
        ("app.min.css", "OLD_MIN_CSS_CONTENT_"),
        ("app.min.css", "NEW_MIN_CSS_CONTENT_"),
        ("new.map", "ADDED_MAP_CONTENT_"),
        ("transition.js", "OLD_MINIFIED_TRANSITION_"),
        ("transition.js", "NEW_ORDINARY_TRANSITION_CONTENT"),
        ("mostly-long.js", "MOSTLY_OLD_CONTENT_"),
        ("mostly-long.js", "MOSTLY_NEW_CONTENT_"),
    ):
        assert marker not in review_input
        size = len(replacements[name].encode("utf-8"))
        assert f"generated: dist/assets/{name} ({size} bytes)" in prompt
    # Exactly half long lines is ordinary content and stays visible to the reviewer.
    assert "+EXACT_HALF_AFTER" in diff
    assert "ORDINARY_CHANGE_REMAINS_VISIBLE" in diff
