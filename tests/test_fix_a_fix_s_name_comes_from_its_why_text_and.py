"""A fix can be named with --slug, and its Done-when can be replaced with a reason on record."""
from pathlib import Path

from test_close import CLEAN, blocked, env, finding  # noqa: F401  (env is a fixture)

STORY = "a-fix-s-name-comes-from-its-why-text-and"

WHY = "The readme greets nobody, so new readers leave before they find the install steps"


def _start(env, *extra):
    result = env.repo.forge("fix", "start", WHY, "--done", "The readme opens with a greeting", *extra)
    assert result.returncode == 0, result.stderr
    return result, Path(result.stdout.splitlines()[0].rsplit(" in ", 1)[1])


def test_1_fix_start_takes_a_slug_to_name_the_fix(env):
    result, where = _start(env, "--slug", "greet-readers")

    assert result.stdout.splitlines()[0].startswith("Started fix greet-readers on fix/greet-readers")
    assert "Next: forge work greet-readers" in result.stdout
    assert env.repo.git("branch", "--show-current", cwd=where) == "fix/greet-readers"
    assert (where / ".factory/fixes/greet-readers.json").is_file()

    refused = env.repo.forge("fix", "start", WHY, "--done", "Done", "--slug", "Greet Readers")
    assert refused.returncode == 1
    assert ("'Greet Readers' is not a fix name; a fix name is lowercase words joined by hyphens."
            in refused.stderr)
    assert "--slug <name>" in refused.stderr


def test_2_fix_amend_replaces_done_when_and_the_next_review_judges_it(env):
    old, new = "The readme opens with a greeting", "The readme opens with the install steps"
    because = "the greeting moved to the docs fix"
    _, where = _start(env, "--slug", "greet-readers")
    env.commit(where, "README.md", "Install with uv.\n")
    env.reviews(blocked(finding("P1", f"Not done: {old}", "README.md")), CLEAN)
    assert env.close("greet-readers").returncode == 1
    assert f"Done when: {old}" in env.prompt()

    amended = env.repo.forge("fix", "amend", "greet-readers", "--done", new, "--because", because)

    assert amended.returncode == 0, amended.stderr
    assert "Next: forge close greet-readers" in amended.stdout
    record = env.repo.git("show", "HEAD:.factory/fixes/greet-readers.json", cwd=where)
    assert old in record and because in record and new in record
    closed = env.close("greet-readers")
    assert closed.returncode == 0, closed.stderr
    assert len(env.review_calls()) == 2
    prompt = env.prompt()
    assert f"Done when: {new}" in prompt and f"`Not done: {new}`" in prompt
    assert f"Done when: {old}" not in prompt and f"`Not done: {old}`" not in prompt
    assert f'Ruling: Done-when changed from "{old}" to "{new}" because {because}' in prompt

    refused = env.repo.forge("fix", "amend", "greet-readers", "--done", new, "--because", " ")
    assert refused.returncode == 1
    assert "A new done-when needs one line of text and a one-line reason." in refused.stderr
    missing = env.repo.forge("fix", "amend", "no-such-fix", "--done", new, "--because", because)
    assert missing.returncode == 1 and "has not started no-such-fix" in missing.stderr
