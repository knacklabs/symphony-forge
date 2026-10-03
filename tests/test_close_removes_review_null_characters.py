"""Review text is safe to save and pass to the next reviewer command."""
import json

from test_close import CLEAN, blocked, env, finding  # noqa: F401 (env is a fixture)

STORY = "a-review-once-returned-a-finding-title-e"


def test_1_close_removes_null_characters_before_saving_review_text(env):
    item, where = env.start_fix()
    answer = blocked(finding("P1", "Greeting is missing\0\0"))
    answer["report"]["findings"][0]["body"] = "Add\0 a greeting.\0"
    answer["report"]["findings"][0]["code_location"]["file_path"] = "app.py\0"
    answer["report"]["overall_correctness"] += "\0"
    answer["report"]["overall_explanation"] += "\0"
    answer["say"] = "autoreview done\0\0"
    env.reviews(answer, CLEAN)

    first = env.close(item)
    assert first.returncode == 1, first.stderr
    saved = json.loads((where / ".factory/fixes/tidy-readme.json").read_text("utf-8"))
    [saved_finding] = saved["review"]["findings"]
    assert saved_finding["title"] == "Greeting is missing"
    assert saved_finding["body"] == "Add a greeting."
    assert saved_finding["file"] == "app.py"
    assert "\0" not in first.stdout + first.stderr

    env.commit(where, "app.py", "print('hello again')\n")
    second = env.close(item)
    assert second.returncode == 0, second.stderr
    assert len(env.review_calls()) == 2
    assert "Greeting is missing" in env.prompt()
    assert "Add a greeting." in env.prompt()
    assert "\0" not in env.prompt()
