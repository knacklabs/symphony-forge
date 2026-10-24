"""React rules reach workers and reviews on new and earlier-adopted clients.

These are prompt-delivery contracts, not checks of the model's judgement. Only the
worker, Autoreview and GitHub edges are fake. Losing a paragraph during init, sync,
brief generation or close must fail here; existing shadcn tests do not cover these
rules. No production test seam is needed.
"""
import json
import re
from pathlib import Path

import pytest

from test_close import CLEAN, GREEN, blocked, env, finding  # noqa: F401
from test_score_notes import _client_repo as setup_client
from test_shadcn_only import _commit_main
from test_worker import calls, install_claude


STORY = "FORGE-REACTDEFAULTS-1"

MEMO_RULE = (
    "In a React app with React Compiler turned on (`babel-plugin-react-compiler` in a "
    "`package.json`), report a `useMemo`, `useCallback` or `React.memo` that this change adds "
    "as a P1 finding titled `Memo: <the component>`. The compiler memoizes. Code under "
    "`components/ui/` (the shadcn/ui copies) is not a finding, and neither is code the "
    "default branch already has."
)
COMPOSITION_RULE = (
    "In a React app, report a component or prop that this change adds and that breaks the "
    "frontend convention's composition rule as a P1 finding titled `Composition: <the component>`: "
    "layout passes content as `children`; parts that share state are a compound component that "
    "shares it through context; logic with no markup is a custom hook; and no boolean prop "
    "switches a component between modes. Code under `components/ui/` is not a finding, and "
    "neither is code the default branch already has."
)
WORKER_RULE = (
    "In a React app with React Compiler turned on, do not add useMemo, useCallback or React.memo; "
    "the compiler memoizes. Compose components as the frontend convention says: children for "
    "layout, compound components for parts that share state, custom hooks for logic with no "
    "markup, and no boolean prop that switches a component between modes. Review flags new "
    "code that breaks either rule."
)
EXISTING_APP = (
    "These rules apply to code that a change adds. The app's current code stays as it is, and "
    "the review does not flag it. An app without React Compiler keeps its own memoization, "
    "and an app on <BrowserRouter> keeps it."
)


def _fix(env, name, changes):
    state = {"kind": "fix", "why": "Use the React defaults",
             "done_when": "New React code follows the frontend convention"}
    return env.start(name, f"fix/{name}", f".factory/fixes/{name}.json", state, changes)


def _worker_brief(env, item):
    log = install_claude(env.repo)
    worked = env.repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    return calls(log)[-1]["brief"]


def _review_new_code(env, tmp_path, adopted, name, path, code, title, rule):
    setup_client(env, tmp_path, adopted)
    env.repo.write("package.json", json.dumps({
        "devDependencies": {"babel-plugin-react-compiler": "1.0.0"}}))
    _commit_main(env.repo, tmp_path, "Enable React Compiler")
    env.checks(GREEN)
    item, _ = _fix(env, name, {path: code})
    assert WORKER_RULE in " ".join(_worker_brief(env, item).split())
    review_finding = {**finding("P1", title, path),
                      "body": "Gain 4, Work 1, Harm 1\nRaise: Functional\n"
                              "Case: normal use - new React code breaks the frontend rule."}
    env.reviews(blocked(review_finding))
    closed = env.close(item)
    output = closed.stdout + closed.stderr
    assert closed.returncode == 1, output
    # A fix reaches its review limit in round one. The current close contract
    # asks the owner about the P1 instead of sending it to another worker round.
    assert f"Review round 1 of {item} reached the round limit with open findings" in output
    assert "One more round, split or accept?" in output
    assert title in output
    assert "Gain 4, Work 1, Harm 1" in output
    assert rule in " ".join(env.prompt().split())


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_2_review_flags_new_hand_memoization(env, tmp_path, adopted):
    _review_new_code(env, tmp_path, adopted, "memo", "apps/web/src/features/home.tsx",
                     "import { useMemo } from 'react';\n"
                     "export function Home() {\n"
                     "  const title = useMemo(() => 'Home', []);\n"
                     "  return <main>{title}</main>;\n}\n", "Memo: Home", MEMO_RULE)


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_3_review_flags_a_component_that_breaks_the_composition_rule(env, tmp_path, adopted):
    _review_new_code(env, tmp_path, adopted, "composition",
                     "apps/web/src/features/status-card.tsx",
                     "export function StatusCard({ compact }: { compact: boolean }) {\n"
                     "  return compact ? <span>Status</span> : <section>Status details</section>;\n"
                     "}\n", "Composition: StatusCard", COMPOSITION_RULE)


def test_6_an_existing_app_keeps_its_code_and_only_new_code_is_checked(env, tmp_path):
    path = "apps/web/src/features/home.tsx"
    original = (
        b"import { useMemo } from 'react';\n"
        b"export function Home({ compact }: { compact: boolean }) {\n"
        b"  const title = useMemo(() => 'Home', []);\n"
        b"  return compact ? <span>{title}</span> : <main>{title}</main>;\n}\n"
    )
    screen = env.repo.path / path
    screen.parent.mkdir(parents=True, exist_ok=True)
    screen.write_bytes(original)
    setup_client(env, tmp_path, True)
    assert (env.repo.path / path).read_bytes() == original
    env.checks(GREEN)
    item, where = _fix(env, "keep-existing-react", {"app.py": "print('updated')\n"})
    brief = _worker_brief(env, item)
    match = re.search(r"how-to.*?is in `([^`]+)`", brief, re.S)
    assert match, brief
    frontend = (Path(match[1]) / "frontend.md").read_text(encoding="utf-8")
    assert "## In an app set up before this release" in frontend
    assert EXISTING_APP in " ".join(frontend.split())
    env.reviews(CLEAN)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    prompt = " ".join(env.prompt().split())
    assert MEMO_RULE in prompt
    assert COMPOSITION_RULE in prompt
    assert (env.repo.path / path).read_bytes() == original
    assert (where / path).read_bytes() == original
