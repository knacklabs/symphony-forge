"""forge close keeps deleted build output and generated file contents out of review input."""
from __future__ import annotations

import json
import shutil
import sys

import pytest

from conftest import _install
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
        "becomes-long.js": "BECOMES_LONG_BASE_MARKER\n",
        "exact-half.js": "EXACT_HALF_LONG_LINE_" + "h" * 1_200 + "\nEXACT_HALF_BEFORE\n",
    }
    for name, content in originals.items():
        (assets / name).write_bytes(content.encode("utf-8"))

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
        "head-only-long.js": "HEAD_ONLY_LONG_MARKER_" + "z" * 1_200 + "\nshort line\n"
        + "HEAD_ONLY_LONG_TAIL_" + "y" * 1_200 + "\n",
        "becomes-long.js": "BECOMES_LONG_HEAD_MARKER_" + "b" * 1_200 + "\nshort line\n"
        + "BECOMES_LONG_HEAD_TAIL_" + "c" * 1_200 + "\n",
        "exact-half.js": originals["exact-half.js"].replace(
            "EXACT_HALF_BEFORE", "EXACT_HALF_AFTER"),
    }
    for name, content in replacements.items():
        (where / "dist" / "assets" / name).write_bytes(content.encode("utf-8"))
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
        ("head-only-long.js", "HEAD_ONLY_LONG_MARKER_"),
        ("becomes-long.js", "BECOMES_LONG_BASE_MARKER"),
        ("becomes-long.js", "BECOMES_LONG_HEAD_MARKER_"),
    ):
        assert marker not in review_input
        size = len(replacements[name].encode("utf-8"))
        assert f"generated: dist/assets/{name} ({size} bytes)" in prompt
    # Exactly half long lines is ordinary content and stays visible to the reviewer.
    assert "+EXACT_HALF_AFTER" in diff
    assert "ORDINARY_CHANGE_REMAINS_VISIBLE" in diff


@pytest.mark.parametrize("classification", ["removed attributes", "long lines"])
def test_2_close_omits_generated_content_from_design_context(env, classification):
    settings = (env.repo.path / "forge.toml").read_text(encoding="utf-8")
    env.commit(env.repo.path, "forge.toml", settings + 'stage = "prototype"\n')

    context_paths = (
        "PRODUCT.md", "DESIGN.md", "docs/design/prototype/SCREENS.md",
    )
    if classification == "removed attributes":
        attributes = "assets/* -linguist-generated\n" + "".join(
            f"{path} linguist-generated\n" for path in context_paths)
        base = {
            ".gitattributes": attributes,
            "assets/.gitattributes": "generated.js linguist-generated\n",
            "assets/generated.js": "BASE_ASSET_CONTENT_MARKER\n",
            "PRODUCT.md": "BASE_PRODUCT_CONTEXT_MARKER\n",
            "DESIGN.md": "BASE_DESIGN_CONTEXT_MARKER\n",
            "docs/design/prototype/SCREENS.md": "BASE_SCREENS_CONTEXT_MARKER\n",
        }
        head = {
            ".gitattributes": "",
            "assets/.gitattributes": "",
            "assets/generated.js": "HEAD_ASSET_CONTENT_MARKER\n",
            "PRODUCT.md": "HEAD_PRODUCT_CONTEXT_MARKER\n",
            "DESIGN.md": "HEAD_DESIGN_CONTEXT_MARKER\n",
            "docs/design/prototype/SCREENS.md": "HEAD_SCREENS_CONTEXT_MARKER\n",
        }
        generated_paths = ("assets/generated.js", *context_paths)
    else:
        base = {
            ".gitattributes": "",
            "assets/generated.js": "BASE_ASSET_CONTENT_MARKER\n",
            "PRODUCT.md": "BASE_PRODUCT_CONTEXT_MARKER_" + "b" * 1_200 + "\n",
            "DESIGN.md": "BASE_DESIGN_CONTEXT_MARKER_" + "b" * 1_200 + "\n",
            "docs/design/prototype/SCREENS.md": "BASE_SCREENS_CONTEXT_MARKER_" + "b" * 1_200 + "\n",
        }
        head = {
            ".gitattributes": "",
            "assets/generated.js": "HEAD_ASSET_CONTENT_MARKER\n",
            "PRODUCT.md": "HEAD_PRODUCT_CONTEXT_MARKER_" + "h" * 1_200 + "\n",
            "DESIGN.md": "HEAD_DESIGN_CONTEXT_MARKER_" + "h" * 1_200 + "\n",
            "docs/design/prototype/SCREENS.md": "HEAD_SCREENS_CONTEXT_MARKER_" + "h" * 1_200 + "\n",
        }
        generated_paths = context_paths

    for path, content in base.items():
        env.commit(env.repo.path, path, content)
    env.repo.git("push", "-q", "origin", "main")

    item, where = env.start_fix({"app.py": "ORDINARY_CHANGE_REMAINS_VISIBLE = True\n"})
    for path, content in head.items():
        env.commit(where, path, content)

    # Observe the real Git reader: attribute-marked blobs must never reach Python.
    real_git = shutil.which("git")
    reads = env.tmp / "blob-reads.jsonl"
    _install(env.repo.bin, "git", f'''#!{sys.executable}
import pathlib, subprocess, sys
from json_log import append_json
args = sys.argv[1:]
if args[:1] == ["check-attr"] and any(arg.startswith("--source") for arg in args):
    sys.exit("Git 2.39 does not support check-attr --source")
if args[:2] == ["cat-file", "--batch"]:
    with subprocess.Popen([{json.dumps(real_git)}, *args], stdin=subprocess.PIPE) as child:
        try:
            for request in sys.stdin.buffer:
                append_json(pathlib.Path({json.dumps(reads.as_posix())}), request.decode("utf-8").rstrip("\\n"))
                child.stdin.write(request)
                child.stdin.flush()
        finally:
            child.stdin.close()
        code = child.wait()
else:
    code = subprocess.call([{json.dumps(real_git)}, *args])
sys.exit(code)
''')

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    call = env.review_calls()[0]
    diff = call["diff"]
    prompt = "\n\n".join(call["prompt_files"].values())
    for path, label in zip(context_paths, ("PRODUCT", "DESIGN", "SCREENS")):
        marker = f"HEAD_{label}_CONTEXT_MARKER"
        assert marker not in prompt
        assert marker not in diff
    if classification == "removed attributes":
        requested = [json.loads(line) for line in reads.read_text("utf-8").splitlines()]
        assert not [spec for spec in requested if spec.partition(":")[2] in generated_paths]
        for marker in ("BASE_ASSET_CONTENT_MARKER", "HEAD_ASSET_CONTENT_MARKER"):
            assert marker not in diff + prompt
    else:
        assert "BASE_ASSET_CONTENT_MARKER" in diff
        assert "HEAD_ASSET_CONTENT_MARKER" in diff
    for path in generated_paths:
        content = head[path]
        assert f"generated: {path} ({len(content.encode('utf-8'))} bytes)" in prompt
    assert "ORDINARY_CHANGE_REMAINS_VISIBLE" in diff


@pytest.mark.platform
def test_3_close_keeps_new_files_beneath_a_deleted_file_path_in_the_review(env):
    old_server = "OLD_EXTENSIONLESS_SERVER_MARKER\n"
    env.commit(env.repo.path, "bin/server", old_server)
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix({"app.py": "ORDINARY_CHANGE_REMAINS_VISIBLE = True\n"})

    old_path = where / "bin" / "server"
    old_path.unlink()
    (old_path / "new.py").parent.mkdir(parents=True)
    new_source = "REVIEWED_NEW_SERVER_SOURCE_MARKER = True\n"
    (old_path / "new.py").write_bytes(new_source.encode("utf-8"))
    env.commit(where, "bin/server/new.py", new_source)

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    call = env.review_calls()[0]
    diff = call["diff"]
    prompt = "\n\n".join(call["prompt_files"].values())
    assert "OLD_EXTENSIONLESS_SERVER_MARKER" not in diff + prompt
    assert "REVIEWED_NEW_SERVER_SOURCE_MARKER" in diff
    assert f"deleted: bin/server ({len(old_server.encode('utf-8'))} bytes)" in prompt
