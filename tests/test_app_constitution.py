"""Constitution gates and guide through Forge's command and client-init boundaries."""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import pytest

from conftest import FORGE_SHIM, ROOT, _install
from test_close import CLEAN, GREEN, STORY_DOC, blocked, env  # noqa: F401
from test_merge_command import _merge_at_github, _ready
from test_setup import _fresh_client
from test_score_notes import _client_repo as setup_client, _scored
from test_story import DESIGN_IMAGE, DOC, READER, new_story, setup, worktree
from test_tools_session_hold import Session

STORY = "FORGE-CONSTITUTION-1"

CONSTITUTION_REFUSAL = (
    "New stories wait for this app's approved constitution in docs/product/CONSTITUTION.md."
)
CONSTITUTION_STEP = (
    'Next: forge fix start "Write the app constitution" --done '
    '"The owner approved docs/product/CONSTITUTION.md"'
)
GUIDE_SENTENCES = (
    "Write the answers in docs/product/BRIEF.md under ## Summary, ## Users and ## Things it "
    "keeps track of.",
    "Make each architecture choice yourself, from the answers and the code, and write it as one "
    "plain line with its reason and its decision record.",
    "A live app answers both halves at adoption: ask only what the code cannot answer.",
    "No new story starts until the owner approves the constitution.",
)


def _fixture_git(repo, tmp_path, *args, cwd=None):
    no_hooks = tmp_path / "fixture-no-hooks"
    no_hooks.mkdir(exist_ok=True)
    return repo.git("-c", f"core.hooksPath={no_hooks}", *args, cwd=cwd)


@pytest.mark.parametrize("case", [
    "new prototype", "new after sign-off", "adopted", "adopted story already started",
])
def test_1_a_new_story_waits_for_the_approved_constitution(repo, gh, tmp_path, monkeypatch, case):
    if case == "new prototype" or case == "new after sign-off":
        top, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = top
        if case == "new prototype":
            started = repo.forge("fix", "start", "Build storage", "--done", "Storage works",
                                 "--kind", "backend")
            assert started.returncode == 0, started.stdout + started.stderr
            assert "constitution" not in (started.stdout + started.stderr).lower()
            return

        # This gate reads an earlier accepted sign-off; it does not test canvas acceptance.
        signoff = repo.path / "docs/decisions/0001-client-signoff.md"
        signoff.parent.mkdir(parents=True, exist_ok=True)
        signoff.write_text("---\nstatus: accepted\n---\n\n# Client sign-off\n", encoding="utf-8")
        repo.git("add", "docs/decisions/0001-client-signoff.md")
        _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Record client sign-off")
        _fixture_git(repo, tmp_path, "push", "-q", "origin", "main")
    elif case == "adopted story already started":
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        setup(repo, kind="client")
        for path in ((repo.path / "docs/product/CONSTITUTION.md"),
                     *repo.path.glob("docs/decisions/*-app-constitution.md"),
                     *repo.path.glob("docs/decisions/*-postgres-storage.md")):
            path.unlink(missing_ok=True)
        repo.git("add", "-A")
        _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Remove the unapproved constitution")
        _fixture_git(repo, tmp_path, "push", "-q", "origin", "main")
        earlier = tmp_path / "earlier-release/src"
        shutil.copytree(ROOT / "src/forge", earlier / "forge",
                        ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("story.py", "approval.py"):
            shutil.copyfile(ROOT / "tests/fixtures/forge-v1.2.2/src/forge" / name,
                            earlier / "forge" / name)
        _install(repo.bin, "forge", FORGE_SHIM.format(python=sys.executable, src=earlier.as_posix()))
        started = repo.forge("story", "new", "SHOP", "Shoppers can save a basket")
        assert started.returncode == 0, started.stdout + started.stderr
        story = worktree(repo, "story/SHOP")
        (story / "plans/SHOP.md").write_text(DOC, encoding="utf-8")
        _install(repo.bin, "forge", FORGE_SHIM.format(python=sys.executable, src=(ROOT / "src").as_posix()))
        read = repo.forge("read", "SHOP")
        assert read.returncode == 0, read.stdout + read.stderr
        assert "constitution" not in read.stderr.lower()
        return
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        version = repo.forge("--version").stdout.split()[-1]
        config = repo.path / "forge.toml"
        config.write_text(config.read_text("utf-8").replace('"v1.2.2"', json.dumps(version)),
                          encoding="utf-8")
        repo.git("add", "-A")
        _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Adopt the earlier client")
        _fixture_git(repo, tmp_path, "push", "-q", "origin", "main")

    refused = repo.forge("story", "new", "SHOP", "Shoppers can save a basket")
    assert refused.returncode == 1
    assert CONSTITUTION_REFUSAL in refused.stderr
    assert CONSTITUTION_STEP in refused.stderr
    shown = repo.forge("next")
    assert shown.returncode == 0, shown.stdout + shown.stderr
    assert "Before its next story, this app needs its approved constitution." in shown.stdout
    assert CONSTITUTION_STEP in shown.stdout

    if case == "new after sign-off":
        monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
        monkeypatch.setenv("CLAUDECODE", "1")
        monkeypatch.setenv("CLAUDE_SESSION_ID", "constitution-intake")
        owner = Session(repo, tmp_path / "constitution-intake-owner", "claude-intake-session")
        try:
            offered = owner.forge("start", "Let shoppers save baskets")
            assert offered.returncode == 0, offered.stdout + offered.stderr
            request = json.loads(offered.stdout)
            reply = ("Lane: plan\nReason: Shoppers need to save baskets.\nKey: START\n"
                     "Title: Save baskets\nChange: Shoppers can save a basket.\n"
                     "Problem: Shoppers lose baskets when they leave.\n"
                     "Done: A shopper can save and reopen a basket.")
            started = owner.forge("handback", request["target"], "--round", str(request["round"]),
                                  "--subagent", "idea-explorer", "--text", reply)
            assert started.returncode == 1
            assert CONSTITUTION_REFUSAL in started.stderr
            assert CONSTITUTION_STEP in started.stderr
        finally:
            owner.close()

    fix_started = repo.forge("fix", "start", "Write the app constitution", "--done",
                             "The owner approved docs/product/CONSTITUTION.md", "--kind", "mechanical")
    assert fix_started.returncode == 0, fix_started.stdout + fix_started.stderr
    work_line = next(line for line in fix_started.stdout.splitlines() if line.startswith("Next: "))
    machine_next = json.loads(repo.forge("next", "--json").stdout)
    assert machine_next["next"]["command"] == work_line.removeprefix("Next: ")
    assert "Before its next story, this app needs its approved constitution." in repo.forge("next").stdout
    fix = Path(re.search(r" in (.+)\n", fix_started.stdout)[1])
    promoted = repo.forge("story", "new", "SHOP", "Shoppers can save a basket",
                          "--from-fix", "write-app-constitution")
    assert promoted.returncode == 1
    assert CONSTITUTION_REFUSAL in promoted.stderr
    assert CONSTITUTION_STEP in promoted.stderr

    brief = fix / "docs/product/BRIEF.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text(
        "# Product brief\n\n## Summary\nShoppers save baskets for later.\n\n"
        "## Users\nShoppers use the app.\n\n## Things it keeps track of\n"
        "A basket has items and a saved time.\n\n## Answers\n"
        "- Personal data: no private or regulated data (client, 2026-10-22)\n",
        encoding="utf-8")
    choice_started = repo.forge("decision", "new", "postgres-storage", cwd=fix)
    assert choice_started.returncode == 0, choice_started.stdout + choice_started.stderr
    choice_path = next((fix / "docs/decisions").glob("*-postgres-storage.md"))
    choice_path.write_text(
        '---\nstatus: proposed\n---\n\n# Store app data in Postgres\n\n'
        "## Context\nThe app needs durable storage.\n\n"
        "## Decision\nStore app data in Postgres.\n\n"
        "## Consequences\nThe app uses a relational database.\n",
        encoding="utf-8")
    accepted_choice = repo.forge("decision", "accept", "postgres-storage", "--by", "Ravi",
                                 cwd=fix)
    assert accepted_choice.returncode == 0, accepted_choice.stdout + accepted_choice.stderr
    app_started = repo.forge("decision", "new", "app-constitution", cwd=fix)
    assert app_started.returncode == 0, app_started.stdout + app_started.stderr
    app_path = next((fix / "docs/decisions").glob("*-app-constitution.md"))
    app_path.write_text(
        '---\nstatus: proposed\n---\n\n# App constitution\n\n'
        "## Context\nThe owner needs a record of the app's architecture.\n\n"
        "## Decision\nApprove the app constitution.\n\n"
        "## Consequences\nThe app follows the accepted defaults and choices.\n",
        encoding="utf-8")
    constitution = fix / "docs/product/CONSTITUTION.md"
    constitution.parent.mkdir(parents=True, exist_ok=True)
    constitution.write_text(
        "# App constitution\n\n## Defaults\nUse the secure defaults listed in the guide.\n\n"
        "## Architecture choices\n"
        f"- Store app data in Postgres: docs/decisions/{choice_path.name}.\n",
        encoding="utf-8")
    accepted_app = repo.forge("decision", "accept", "app-constitution", "--by", "Ravi", cwd=fix)
    assert accepted_app.returncode == 0, accepted_app.stdout + accepted_app.stderr
    local = repo.forge("story", "new", "SHOP", "Shoppers can save a basket", cwd=fix)
    assert local.returncode == 1
    assert CONSTITUTION_REFUSAL in local.stderr

    repo.git("add", "-A", cwd=fix)
    repo.git("commit", "-q", "-m", "Approve the app constitution", cwd=fix)
    branch = repo.git("branch", "--show-current", cwd=fix)
    repo.git("merge", "--ff-only", branch, cwd=repo.path)
    _fixture_git(repo, tmp_path, "push", "-q", "origin", "main")
    created = repo.forge("story", "new", "SHOP", "Shoppers can save a basket")
    assert created.returncode == 0, created.stdout + created.stderr
    next_step = repo.forge("next")
    assert next_step.returncode == 0, next_step.stdout + next_step.stderr
    assert "Before its next story, this app needs its approved constitution." not in next_step.stdout
    assert CONSTITUTION_STEP not in next_step.stdout


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_2_the_constitution_is_approved_only_when_complete(repo, tmp_path, gh, adopted):
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        version = repo.forge("--version").stdout.split()[-1]
        config = repo.path / "forge.toml"
        config.write_text(config.read_text("utf-8").replace('"v1.2.2"', json.dumps(version)),
                          encoding="utf-8")
        repo.git("add", "-A")
        _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Adopt the earlier client")
        _fixture_git(repo, tmp_path, "push", "-q", "origin", "main")
        top = repo.path
    else:
        top, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = top
        repo.write("docs/decisions/0001-client-signoff.md", "---\nstatus: accepted\n---\n")
        repo.git("add", "docs/decisions/0001-client-signoff.md")
        _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Record client sign-off")
        _fixture_git(repo, tmp_path, "push", "-q", "origin", "main")

    started = repo.forge("fix", "start", "Write the app constitution", "--done",
                         "The owner approved docs/product/CONSTITUTION.md", "--kind", "mechanical")
    assert started.returncode == 0, started.stdout + started.stderr
    fix = Path(re.search(r" in (.+)\n", started.stdout)[1])
    created_record = repo.forge("decision", "new", "app-constitution", cwd=fix)
    assert created_record.returncode == 0, created_record.stdout + created_record.stderr
    app_record = next((fix / "docs/decisions").glob("*-app-constitution.md"))
    app_record.write_text(
        '---\nstatus: proposed\n---\n\n# App constitution\n\n'
        "## Context\nThe owner needs a record of the app's architecture.\n\n"
        "## Decision\nApprove the app constitution.\n\n"
        "## Consequences\nThe app follows the accepted defaults and choices.\n",
        encoding="utf-8")

    brief = fix / "docs/product/BRIEF.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text(
        "# Product brief\n\n## Summary\nShoppers save baskets for later.\n\n"
        "## Users\nShoppers use the app.\n\n## Things it keeps track of\n"
        "A basket has items and a saved time.\n\n## Answers\n"
        "- Personal data: no private or regulated data (client, 2026-10-22)\n",
        encoding="utf-8")
    missing_constitution = repo.forge("decision", "accept", "app-constitution", "--by", "Ravi",
                                     cwd=fix)
    assert missing_constitution.returncode == 1
    assert "The app constitution can't be approved yet:" in missing_constitution.stderr
    assert "docs/product/CONSTITUTION.md" in missing_constitution.stderr
    assert "status: proposed" in app_record.read_text("utf-8")

    constitution = fix / "docs/product/CONSTITUTION.md"
    constitution.parent.mkdir(parents=True, exist_ok=True)
    storage_started = repo.forge("decision", "new", "postgres-storage", cwd=fix)
    assert storage_started.returncode == 0, storage_started.stdout + storage_started.stderr
    storage = next((fix / "docs/decisions").glob("*-postgres-storage.md"))
    storage.write_text(
        '---\nstatus: proposed\n---\n\n# Store app data in Postgres\n\n'
        "## Context\nThe app needs durable storage.\n\n"
        "## Decision\nStore app data in Postgres.\n\n"
        "## Consequences\nThe app uses a relational database.\n",
        encoding="utf-8")
    accepted_storage = repo.forge("decision", "accept", "postgres-storage", "--by", "Ravi",
                                  cwd=fix)
    assert accepted_storage.returncode == 0, accepted_storage.stdout + accepted_storage.stderr
    constitution.write_text(
        "# App constitution\n\n## Defaults\n<!-- Add defaults here. -->\n\n"
        "## Architecture choices\n"
        f"- Storage: Postgres, see docs/decisions/{storage.name}.\n",
        encoding="utf-8")
    empty_defaults = repo.forge("decision", "accept", "app-constitution", "--by", "Ravi", cwd=fix)
    assert empty_defaults.returncode == 1
    assert "## Defaults" in empty_defaults.stderr

    constitution.write_text(
        "# App constitution\n\n## Defaults\nUse the secure defaults listed in the guide.\n\n"
        "## Architecture choices\n- Store data safely.\n",
        encoding="utf-8")
    unlinked = repo.forge("decision", "accept", "app-constitution", "--by", "Ravi", cwd=fix)
    assert unlinked.returncode == 1
    assert 'architecture choice "- Store data safely." names no decision record' in unlinked.stderr

    constitution.write_text(
        "# App constitution\n\n## Defaults\nUse the secure defaults listed in the guide.\n\n"
        "## Architecture choices\n"
        "- Store data safely: docs/decisions/9999-not-present.md.\n",
        encoding="utf-8")
    missing_record = repo.forge("decision", "accept", "app-constitution", "--by", "Ravi", cwd=fix)
    assert missing_record.returncode == 1
    assert "docs/decisions/9999-not-present.md" in missing_record.stderr
    assert 'forge decision accept not-present --by "Ravi"' in missing_record.stderr

    constitution.write_text(
        "# App constitution\n\n## Defaults\nUse the secure defaults listed in the guide.\n\n"
        "## Architecture choices\n<!-- Add choices here. -->\n",
        encoding="utf-8")
    empty_choices = repo.forge("decision", "accept", "app-constitution", "--by", "Ravi", cwd=fix)
    assert empty_choices.returncode == 1
    assert "## Architecture choices" in empty_choices.stderr

    proposed_start = repo.forge("decision", "new", "user-sign-in", cwd=fix)
    assert proposed_start.returncode == 0, proposed_start.stdout + proposed_start.stderr
    proposed = next((fix / "docs/decisions").glob("*-user-sign-in.md"))
    proposed.write_text(
        '---\nstatus: proposed\n---\n\n# Require sign-in\n\n'
        "## Context\nThe app has private customer data.\n\n"
        "## Decision\nRequire an account before use.\n\n"
        "## Consequences\nCustomers must sign in.\n",
        encoding="utf-8")
    constitution.write_text(
        "# App constitution\n\n## Defaults\nUse the secure defaults listed in the guide.\n\n"
        "## Architecture choices\n"
        f"- Sign-in: Require an account, see docs/decisions/{proposed.name}.\n",
        encoding="utf-8")
    proposed_choice = repo.forge("decision", "accept", "app-constitution", "--by", "Ravi", cwd=fix)
    assert proposed_choice.returncode == 1
    assert f"docs/decisions/{proposed.name}" in proposed_choice.stderr
    assert 'forge decision accept user-sign-in --by "Ravi"' in proposed_choice.stderr

    accepted_choice = repo.forge("decision", "accept", "user-sign-in", "--by", "Ravi", cwd=fix)
    assert accepted_choice.returncode == 0, accepted_choice.stdout + accepted_choice.stderr
    old_brief = brief.read_text("utf-8")

    brief.write_text(old_brief.replace(
        "## Summary\nShoppers save baskets for later.\n\n",
        "## Summary\n<!-- Add a summary. -->\n\n"), encoding="utf-8")
    missing_summary = repo.forge("decision", "accept", "app-constitution", "--by", "Ravi",
                                 cwd=fix)
    assert missing_summary.returncode == 1
    assert "docs/product/BRIEF.md needs ## Summary" in missing_summary.stderr

    brief.write_text(old_brief.replace("## Users\nShoppers use the app.\n\n", ""),
                     encoding="utf-8")
    missing_users = repo.forge("decision", "accept", "app-constitution", "--by", "Ravi", cwd=fix)
    assert missing_users.returncode == 1
    assert "docs/product/BRIEF.md needs ## Users" in missing_users.stderr

    brief.write_text(old_brief.replace("## Things it keeps track of\nA basket has items and a saved time.\n\n", ""),
                     encoding="utf-8")
    missing_things = repo.forge("decision", "accept", "app-constitution", "--by", "Ravi", cwd=fix)
    assert missing_things.returncode == 1
    assert "## Things it keeps track of" in missing_things.stderr
    for answer in (None, "no private or regulated data", "ask the client", "later, when scope is known"):
        if answer is None:
            text = old_brief.replace(
                "- Personal data: no private or regulated data (client, 2026-10-22)\n", "")
        elif answer == "no private or regulated data":
            text = old_brief.replace("(client, 2026-10-22)", "(client, not-a-date)")
        elif answer == "later, when scope is known":
            text = old_brief.replace(
                "- Personal data: no private or regulated data (client, 2026-10-22)",
                "- Personal data: later, when scope is known")
        else:
            text = old_brief.replace("no private or regulated data", answer)
        brief.write_text(text, encoding="utf-8")
        open_personal_data = repo.forge("decision", "accept", "app-constitution", "--by", "Ravi",
                                        cwd=fix)
        assert open_personal_data.returncode == 1
        assert "Personal data" in open_personal_data.stderr

    brief.write_text(old_brief, encoding="utf-8")
    accepted = repo.forge("decision", "accept", "app-constitution", "--by", "Ravi", cwd=fix)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert "Accepted docs/decisions/" in accepted.stdout
    assert "status: accepted" in app_record.read_text("utf-8")


@pytest.mark.parametrize("adopted,case", [
    (False, "fix"), (True, "fix"), (False, "part"), (False, "documents"),
    (False, "proposed"), (False, "absent"), (False, "read"), (False, "read later"),
])
def test_3_reviews_and_reads_hold_work_against_the_constitution(env, tmp_path, monkeypatch, adopted, case):
    # Commands own prompt selection and verdicts; only external readers are faked.
    # Previously low model scores let constitution violations pass.
    setup_client(env, tmp_path, adopted)
    env.checks(GREEN)  # Init's branch-protection replies are not CI check results.
    repo = env.repo
    constitution = (repo.path / "docs/product/CONSTITUTION.md").read_text("utf-8")
    record = next(repo.path.glob("docs/decisions/*-app-constitution.md"))

    def approval(accepted):
        text = record.read_text("utf-8")
        record.write_text(re.sub(r"status: (accepted|proposed)",
                                 "status: accepted" if accepted else "status: proposed", text),
                          encoding="utf-8")
        repo.git("add", "-A")
        _fixture_git(repo, tmp_path, "commit", "-qm", "Change constitution approval")
        _fixture_git(repo, tmp_path, "push", "-q", "origin", "main")

    if case.startswith("read"):
        _install(repo.bin, "claude", READER.format(python=sys.executable))
        shop = new_story(repo, "SHOP")
        (shop / "plans/SHOP.md").write_text(DOC, encoding="utf-8")
        if case == "read later":
            approval(False)
            (repo.bin / "claude-says.md").write_text(
                "1. Blocking: The storage task is missing.\n   Gain 4, Work 1, Harm 1\n",
                encoding="utf-8")
            first = repo.forge("read", "SHOP")
            assert first.returncode == 0, first.stdout + first.stderr
            call = json.loads((repo.bin / "claude-calls.jsonl").read_text("utf-8").splitlines()[-1])
            assert "This app's approved constitution" not in call["prompt"]
            notes = shop / "plans/SHOP.read.md"
            notes.write_text(notes.read_text("utf-8") + "\n   Disposition: cut - storage task added\n",
                             encoding="utf-8")
            approval(True)
        number = 2 if case == "read later" else 1
        label = "Advisory" if case == "read later" else "Blocking"
        (repo.bin / "claude-says.md").write_text(
            f"{number}. {label}: Constitution: The plan adds MySQL\n"
            "   The approved storage choice requires Postgres.\n   Gain 2, Work 1, Harm 1\n"
            f"{number + 1}. Advisory: Constitution: A rare storage path adds MySQL\n"
            "   Case: rare\n   Gain 2, Work 1, Harm 1\n", encoding="utf-8")
        read = repo.forge("read", "SHOP")
        assert read.returncode == (1 if case == "read later" else 0), read.stdout + read.stderr
        if case == "read later":
            assert "Round 2 of the cold read of SHOP stopped with open notes" in read.stderr
        prompt = json.loads((repo.bin / "claude-calls.jsonl").read_text("utf-8").splitlines()[-1])["prompt"]
        assert ("This app's approved constitution, from the default branch, follows. In any round, "
                "report a plan that goes against it as a note titled "
                "`Constitution: <the line it breaks>`; this is not limited to P0.") in prompt
        assert constitution in prompt
        notes = (shop / "plans/SHOP.read.md").read_text("utf-8")
        assert "passed: no\n" in notes
        held = notes.split(f"{number}. {label}: Constitution:", 1)[1].split(f"{number + 1}.", 1)[0]
        assert "Gain 4, Work 1, Harm 1 (floor: constitution)" in held
        assert "below the bar" not in held
        assert "Disposition: keep - below the bar (follow-up)" in notes
        next_step = repo.forge("next").stdout
        assert ("Constitution: The plan adds MySQL" if case == "read later"
                else f"give finding {number}") in next_step
        return

    if case in {"proposed", "absent"}:
        approval(False)
        if case == "absent":
            record.unlink()
            repo.git("add", "-A")
            _fixture_git(repo, tmp_path, "commit", "-qm", "Remove constitution approval")
            _fixture_git(repo, tmp_path, "push", "-q", "origin", "main")
    path = "docs/storage.md" if case == "documents" else "app.py"
    if case == "part":
        repo.write("plans/SHOP.md", STORY_DOC)
        repo.write("docs/design/baskets/screen.svg", DESIGN_IMAGE)
        repo.git("add", "plans/SHOP.md", "docs/design/baskets/screen.svg")
        _fixture_git(repo, tmp_path, "commit", "-qm", "Record the existing story")
        _fixture_git(repo, tmp_path, "push", "-q", "origin", "main")
        item, where = env.start_task()
    else:
        item, where = env.start_fix(changes={path: "Use MySQL instead of Postgres.\n"})
    if case == "fix":
        env.commit(where, "docs/product/CONSTITUTION.md", "# Branch-only constitution: use MySQL\n")
    env.reviews(blocked(_scored("P1", "Constitution: The app uses Postgres",
                               "Gain 3, Work 4, Harm 1\nThe change uses MySQL.", path)))
    if case in {"proposed", "absent"}:
        env.reviews(CLEAN)
    trace = tmp_path / "review-git-packets.txt"
    with monkeypatch.context() as tracing:
        tracing.setenv("GIT_TRACE_PACKET", trace.as_posix())
        closed = env.close(item)
    assert env.review_calls(), closed.stdout + closed.stderr
    if case == "fix":
        # The review snapshot must use Git's transport while sibling work can
        # repack the source object store. A local filesystem copy races that work.
        assert re.search(r"\bclone>\s+want [0-9a-f]+", trace.read_text("utf-8"))
    prompt = env.prompt()
    if case in {"proposed", "absent"}:
        assert "## This app's constitution" not in prompt
        assert closed.returncode == 0, closed.stdout + closed.stderr
        return
    assert "## This app's constitution" in prompt
    assert ("The app's approved constitution, on the default branch, follows. Report work that goes "
            "against it as a finding titled `Constitution: <the line it breaks>`, quoting the line. "
            "Where it differs from Forge's convention pages, it wins.") in prompt
    assert constitution in prompt
    assert "Branch-only constitution" not in prompt
    assert "Gain 4, Work 2, Harm 1 (floor: constitution)" in closed.stdout
    if case == "documents":
        assert closed.returncode == 0, closed.stdout + closed.stderr
    else:
        assert closed.returncode == 1, closed.stdout + closed.stderr
        if case == "part":
            assert "The review left serious findings open" in closed.stderr
        else:
            assert "reached the round limit with open findings" in closed.stderr
            assert "Constitution: The app uses Postgres" in closed.stderr


@pytest.mark.parametrize("adoption", ["new init", "previous release upgrade and sync"])
def test_4_clients_get_the_constitution_guide(repo, gh, tmp_path, adoption):
    if adoption == "new init":
        top, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        version = repo.forge("--version").stdout.split()[-1]
        config = repo.path / "forge.toml"
        config.write_text(config.read_text("utf-8").replace('"v1.2.2"', json.dumps(version)),
                          encoding="utf-8")
        repo.git("add", "-A")
        _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Adopt the earlier client")
        _fixture_git(repo, tmp_path, "push", "-q", "origin", "main")
        fix_started = repo.forge("fix", "start", "Sync the constitution guide", "--done",
                                 "The guide is current", "--kind", "mechanical")
        assert fix_started.returncode == 0, fix_started.stdout + fix_started.stderr
        top = Path(re.search(r" in (.+)\n", fix_started.stdout)[1])
        synced = repo.forge("sync", cwd=top)
        assert synced.returncode == 0, synced.stdout + synced.stderr

    for host in (".claude", ".codex"):
        skills = top / host / "skills/forge"
        guide = " ".join((skills / "SKILL.md").read_text("utf-8").split())
        for sentence in GUIDE_SENTENCES:
            assert " ".join(sentence.split()) in guide
        assert "## Constitution defaults" in (skills / "fde.md").read_text("utf-8")
    if adoption == "new init":
        brief = (top / "docs/product/BRIEF.md").read_text("utf-8")
        assert "## Things it keeps track of" in brief


@pytest.mark.platform
def test_5_cleanup_defers_the_constitution_reminder_until_the_worktree_is_removed(env):
    item, where = _ready(env)
    env.gh.respond("pr", "view", stdout=json.dumps({
        "number": 7, "state": "OPEN", "baseRefName": "main", "isDraft": False,
        "headRefName": f"fix/{item}", "headRefOid": env.repo.git("rev-parse", "HEAD", cwd=where),
        "title": "Tidy readme"}))
    (where / "unsaved.txt").write_text("Keep this work\n", encoding="utf-8")
    _merge_at_github(env)
    merged = env.repo.forge("merge", item)
    assert merged.returncode == 0, merged.stdout + merged.stderr
    env.gh.respond("pr", "list", "--state", "merged",
                   stdout=json.dumps([{"headRefName": f"fix/{item}"}]))
    # An earlier merge left no local cleanup receipt, while the dirty worktree survived.
    (env.repo.path / ".git/forge/ready" / f"{item}.json").unlink()
    waiting = env.repo.forge("next")
    assert waiting.returncode == 0, waiting.stdout + waiting.stderr
    assert "Next: git worktree remove " in waiting.stdout
    assert "constitution" not in waiting.stdout.lower()
    (where / "unsaved.txt").unlink()
    env.repo.git("worktree", "remove", str(where))
    after = env.repo.forge("next")
    assert after.returncode == 0, after.stdout + after.stderr
    assert "Before its next story, this app needs its approved constitution." in after.stdout
    assert CONSTITUTION_STEP in after.stdout
