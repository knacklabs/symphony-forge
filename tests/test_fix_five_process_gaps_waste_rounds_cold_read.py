"""Command-level regressions for the five process gaps fix."""
import hashlib
import json

from test_close import CLEAN, GREEN, env as close_env
from test_setup import _fresh_client
from test_story import DOC, setup, worktree
from test_worker import calls, install_claude

STORY = "FIX-FIVE-PROCESS-GAPS-WASTE-ROUNDS-COLD-READ"


def test_1_read_shows_confirmed_spec_on_promoted_task_branch(repo):
    setup(repo)
    started = repo.forge("fix", "start", "Recover the saved basket", "--done", "Saved baskets return")
    assert started.returncode == 0, started.stderr
    fix = worktree(repo, "fix/recover-the-saved-basket")
    body = "# Basket spec\n\n## Why\n\nA saved basket gets lost.\n\n## Roadmap\n\n- BASKET: Recover baskets\n"
    digest = hashlib.sha256(body.encode()).hexdigest()
    spec = f'---\nstatus: confirmed\nconfirmed_hash: "{digest}"\n---\n{body}'
    path = fix / "docs/specs/baskets.md"
    path.parent.mkdir(parents=True)
    path.write_text(spec, encoding="utf-8")
    repo.git("add", "-A", cwd=fix)
    repo.git("commit", "-q", "-m", "Confirm the basket spec", cwd=fix)
    made = repo.forge("story", "new", "BASKET", "Recover baskets", "--from-fix", "recover-the-saved-basket")
    assert made.returncode == 0, made.stderr
    story = worktree(repo, "story/BASKET")
    (story / "plans/BASKET.md").write_text(DOC, encoding="utf-8")
    read = repo.forge("read", "BASKET")
    assert read.returncode == 0, read.stderr
    prompt = json.loads((repo.bin / "claude-calls.jsonl").read_text("utf-8").splitlines()[-1])["prompt"]
    assert "docs/specs/baskets.md" in prompt
    assert "A saved basket gets lost." in prompt
    assert "check the confirmed spec before calling it missing" in prompt


def test_2_review_stales_when_story_notes_or_roadmap_entry_changes(close_env):
    env = close_env
    env.reviews(CLEAN)
    env.checks(GREEN)
    item, where = env.start_approved_task(env.repo.path.joinpath("plans/SHOP.md").read_text("utf-8"))
    assert env.close(item).returncode == 0
    assert len(env.review_calls()) == 1
    doc = (where / "plans/SHOP.md").read_text("utf-8")
    env.commit(where, "plans/SHOP.md", doc + "\n## Notes\n\nOnly signed-in shoppers use this.\n")
    assert env.close(item).returncode == 0
    assert len(env.review_calls()) == 2
    roadmap = json.loads((where / "plans/roadmap.json").read_text("utf-8"))
    next(entry for entry in roadmap["items"] if entry["key"] == "SHOP")["title"] = "Save baskets for signed-in shoppers"
    env.commit(where, "plans/roadmap.json", json.dumps(roadmap))
    assert env.close(item).returncode == 0
    assert len(env.review_calls()) == 3
    roadmap["items"].append({"key": "OTHER", "title": "An unrelated story"})
    env.commit(where, "plans/roadmap.json", json.dumps(roadmap))
    assert env.close(item).returncode == 0
    assert len(env.review_calls()) == 3


def test_3_fix_work_brief_states_limit_interfaces_and_allowance(repo):
    log = install_claude(repo)
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nworkers = "claude"\n'
               'stage = "prototype"\n'
               'interfaces = ["**/routes/**", "**/*.schema.*"]\n'
               'models.lite = { model = "sonnet", effort = "medium" }\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Configure Forge")
    repo.git("push", "-q", "origin", "main")
    assert repo.forge("fix", "start", "Clarify the fix boundary", "--done", "Workers see the boundary").returncode == 0
    fix = worktree(repo, "fix/clarify-the-fix-boundary")
    assert repo.forge("work", "clarify-the-fix-boundary").returncode == 0
    brief = calls(log)[-1]["brief"]
    assert "at most five code files" in brief
    assert "**/routes/**" in brief and "**/*.schema.*" in brief
    assert "Prototype before sign-off" in brief
    assert repo.forge("fix", "allow-large", "The client approved the wider repair", cwd=fix).returncode == 0
    assert repo.forge("work", "clarify-the-fix-boundary").returncode == 0
    assert "The client approved the wider repair" in calls(log)[-1]["brief"]


def test_5_init_skill_names_input_exclusions_and_amendment(repo, gh, tmp_path):
    client, result = _fresh_client(repo, gh, tmp_path)
    assert result.returncode == 0, result.stderr
    skill = (client / ".codex/skills/forge/SKILL.md").read_text("utf-8")
    assert "Done-when or Notes names supported inputs and exclusions" in skill
    assert "A dismissal that narrows those" in skill
    assert "inputs needs an amendment to the story doc" in skill
    assert "Before building a fix, check its brief for the five-code-file limit" in skill
