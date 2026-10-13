"""The pane's Board tab and /forge text read as plain lines a person can act on.

`forge board --json` and the board JSON contract (tests/fixtures/board.json and the older
release's board-previous.json) are fed to the shipped summary.ts through Node, and to the
shipped hooks' mounted Board tab with only the host's drawing table stubbed.
"""
import copy
import json
import sys

import pytest

from conftest import ROOT
from test_machine_views import github, state, view
from test_mod_plugin import HOST, node_run
from test_close import env  # noqa: F401
from test_run_records import configure
from test_story import setup, worktree

STORY = "pane-grouped-board"
NOW = "2026-10-13T12:00:00Z"
RESOLVE = 'forge close ASK/PERIOD --resolve <narrow|split|accept> --reason "<human\'s choice>"'
FIXTURE = json.loads((ROOT / "tests/fixtures/board.json").read_text("utf-8"))
PREVIOUS = json.loads((ROOT / "tests/fixtures/board-previous.json").read_text("utf-8"))


def row(base, **values):
    return {**copy.deepcopy(base), "children": [], **values}


def lines(tmp_path, board, error=None):
    summary = (ROOT / "src/forge/mod/hooks/summary.ts").as_uri()
    return node_run(tmp_path, f"""
const {{ text }} = await import({json.dumps(summary)});
const data = {{ board: {json.dumps(board)}, next: {json.dumps(FIXTURE["next"])}, lanes: null,
  error: {json.dumps(error)}, refreshedAt: 0 }};
console.log(JSON.stringify(text(data, Date.parse({json.dumps(NOW)}))));
""")


def board_tab(tmp_path, repo=None, canned=None, press=None):
    """The mounted Board tab's lines, from real forge commands in `repo` or `canned` views, after
    pressing the button keyed `press`."""
    register = (ROOT / "src/forge/mod/hooks/register.ts").as_uri()
    root = str(repo.path) if repo else "/repo"
    forge = [sys.executable, str(repo.bin / "forge")] if repo else None
    return node_run(tmp_path, HOST + f"""
const mod = await import({json.dumps(register)});
const canned = {json.dumps(canned)}, forge = {json.dumps(forge)};
const element = type => props => ({{ type, props, children: props.children == null ? [] : [props.children].flat() }});
const table = Object.fromEntries(['Box', 'Text', 'Button', 'Markdown', 'Svg'].map(type => [type, element(type)]));
const api = {{
  session: {{cwd: async () => {json.dumps(root)}}},
  clock: {{now: async () => Date.parse({json.dumps(NOW)}), every: () => ({{cancel() {{}}}})}},
  command: {{register: async () => {{}}}},
  env: {{get: async () => '1'}},
  ui: {{invalidate() {{}}, open: async () => ({{isPlaced: false}}), resolve: () => table}},
  process: {{run: async (argv, init) => {{
    if (canned) return canned[argv[1]] ? {{exitCode: 0, stderr: '', stdout: JSON.stringify(canned[argv[1]])}}
      : {{exitCode: 2, stdout: '', stderr: "invalid choice: 'lanes'"}};
    try {{
      return {{exitCode: 0, stderr: '', stdout: execFileSync(forge[0], [forge[1], ...argv.slice(1)],
        {{cwd: init.cwd, encoding: 'utf8', timeout: init.timeoutMs}})}};
    }} catch (e) {{ return {{exitCode: e.status ?? 1, stdout: String(e.stdout ?? ''), stderr: String(e.stderr ?? '')}} }}
  }}}},
}};
mod.register(on);
await fire('session.start', {{cwd: {json.dumps(root)}, surface: 'terminal', isInteractive: true}}, api);
const draw = () => fire('ui.render', {{component: 'Pane', requestId: 'forge', surface: 'terminal',
  props: {{title: 'Forge', isFocused: true, bodyColumns: 80, placement: 'inline', scroll: {{offset: 0, bodyRows: 40}}, view: {{}}}}}}, api);
let tree = await draw();
const find = (n, key) => typeof n === 'string' ? undefined : n.props.key === key ? n : n.children.map(c => find(c, key)).find(Boolean);
if ({json.dumps(press)}) {{ find(tree, {json.dumps(press)}).props.onPress(); tree = await draw(); }}
const inline = n => typeof n === 'string' ? n : n.type === 'Button' ? n.props.label : n.children.map(inline).join('');
const lines = n => typeof n === 'string' || n.type !== 'Box' ? [inline(n)] : n.children.flatMap(lines);
console.log(JSON.stringify(lines(tree).join('\\n')));
""")


def team_board():
    board = copy.deepcopy(FIXTURE["board"])
    ready, story = board["items"]
    stages = copy.deepcopy(ready["stages"])
    stages[2].update(status="running", started_at="2026-10-13T11:48:00Z")
    ask = row(ready, id="ASK/PERIOD", kind="task", title="Ask asks for the comparison period",
              stage="building", state="in progress", findings={"count": 3, "titles": [], "items": [
                  {"title": "Input lost", "priority": "P1"}], "dismissed": 2},
              gates={**ready["gates"], "review": {"status": "blocked", "count": 3}},
              needs_person=True, next={"command": None, "line": "Close stopped the part.", "step": RESOLVE})
    stuck = row(ready, id="AVB/PERIOD", kind="task", title="Actual-versus-Budget answers ask for the period",
                stage="building", state="in progress", stalled=True, idle_since="2026-10-05T11:02:00+00:00",
                next={"command": "forge work AVB/PERIOD", "line": "Build it.", "step": "forge work AVB/PERIOD"})
    moving = row(ready, id="counts", kind="fix", title="Board counts", stage="building", state="in progress",
                 activity={"status": "running", "action": "review"}, stages=stages, round=None,
                 next={"command": None, "line": "Review is running.",
                       "step": "wait for the review, then forge close counts"})
    green = row(ready, id="trust", title="Codex trust fix", pr={"number": 9, "checks": "pass", "failures": []})
    done = row(ready, id="old", title="An old finished fix", stage="done", state="done")
    board["items"] = [
        row(story, id="ASK", title="Ask story", stage="building", state="building", children=[ask]),
        row(story, id="AVB", title="Budget story", stage="building", state="building", children=[stuck]),
        moving, green, ready, story, done,
    ]
    team = board["team"]
    team["counts"]["parts"]["in progress"] = 2
    team["counts"]["fixes"]["in progress"] = 1
    team["go_live"] = {"status": "range", "earliest": "2026-10-18", "latest": "2026-10-20",
                       "remaining_parts": 4, "no_plan": {"count": 0, "titles": []}}
    return board


def groups_in_plain_words(_request, tmp_path):
    shown = lines(tmp_path, team_board())
    assert shown == f"""\
3 in progress · 1 needs you · 1 stuck · go-live Oct 18 – Oct 20

NEEDS YOU
  Ask asks for the comparison period  ASK
    Review found 3 problems. The builder is stuck.
    → decide: {RESOLVE}

STUCK (no progress 8 days)
  Actual-versus-Budget answers ask for the period  AVB
    Building · last activity Oct 5
    → forge work AVB/PERIOD

MOVING
  Board counts
    Review running · 12 min
    → wait for the review, then forge close counts

READY TO MERGE
  Codex trust fix
    Ready to merge · checks green
    → merge its pull request, then forge next
  Polish the guide
    Ready to merge
    → merge its pull request, then forge next

WAITING OR NOT STARTED (1) · forge board for all"""
    for hidden in ("unknown", "T11:", "P1", "dismissed", " 0 ", "Build → Tests", "round"):
        assert hidden not in shown


def zero_counts_unknown_go_live_and_failures_stay_hidden(_request, tmp_path):
    board = team_board()
    board["team"]["counts"]["parts"]["in progress"] = 0
    board["team"]["counts"]["fixes"]["in progress"] = 0
    board["team"]["go_live"]["status"] = "not enough history"
    shown = lines(tmp_path, board, error="offline")
    assert shown.splitlines()[0] == "1 needs you · 1 stuck"
    assert shown.endswith("\n\nCouldn't refresh: offline")
    board["items"] = []
    board["team"] = FIXTURE["board"]["team"]
    assert lines(tmp_path, board) == "Nothing in progress."


def an_older_forge_board_draws_rows_and_no_team_line(_request, tmp_path):
    assert lines(tmp_path, PREVIOUS["board"]) == """\
READY TO MERGE
  Polish the guide
    Ready to merge
    → Polish the guide is ready and waiting for someone to merge it.

WAITING OR NOT STARTED (1) · forge board for all"""


def a_review_stop_needs_you_with_the_step_forge_next_prints(request, tmp_path):
    repo, gh = request.getfixturevalue("repo"), request.getfixturevalue("gh")
    setup(repo, keys=())
    made = repo.forge("fix", "start", "Polish the guide", "--done", "The guide reads clearly", "--slug", "polish")
    assert made.returncode == 0, made.stderr
    state(worktree(repo, "fix/polish") / ".factory/fixes/polish.json",
          stop={"question": "Keep the old wording or rewrite the guide?"})
    github(gh, [])
    step = next(line for line in repo.forge("next").stdout.splitlines() if line.startswith("Next: "))
    board = view(repo, "board")
    polish = next(row for row in board["items"] if row["id"] == "polish")
    assert polish["needs_person"] is True
    assert polish["next"]["command"] is None
    assert polish["next"]["step"] == step.removeprefix("Next: ")
    shown = lines(tmp_path, board)
    assert f"NEEDS YOU\n  Polish the guide\n    The builder is stuck.\n    → decide: {polish['next']['step']}" in shown


def a_worker_question_needs_you_with_its_answer_step(request, tmp_path):
    env = request.getfixturevalue("env")
    repo = configure(env)
    item, _ = env.start_fix()
    stub = repo.bin / "claude"
    stub.write_text(stub.read_text("utf-8").replace(
        'print("stub claude: built it")', 'print("\\n\\nQuestion: May I reuse the parser?")'), "utf-8")
    assert repo.forge("work", item).returncode == 0
    step = next(line for line in repo.forge("next").stdout.splitlines() if line.startswith("Next: "))
    assert step == f'Next: forge work {item} --note "<answer>"'
    shown = board_tab(tmp_path, repo)
    assert f"NEEDS YOU\nReadme greets new readers\nThe builder asked a question.\n→ decide: {step.removeprefix('Next: ')}" in shown, shown


def opened_waiting_rows_and_a_remote_ready_row_show_their_state_and_step(_request, tmp_path):
    board = copy.deepcopy(PREVIOUS["board"])
    board["items"][0]["next"] = {"command": None, "step": None,
                                 "line": "Polish the guide is ready to merge; Forge Test merges it from their machine."}
    board["items"][1]["next"]["step"] = "forge read WAIT"
    shown = board_tab(tmp_path, canned={"board": board, "next": FIXTURE["next"]}, press="waiting")
    assert ("READY TO MERGE\nPolish the guide\nReady to merge\n"
            "→ Polish the guide is ready to merge; Forge Test merges it from their machine.") in shown, shown
    assert ("Hide waiting or not started (1)\nBoard shows each story in plain English  WAIT\n"
            "Planning\n→ forge read WAIT") in shown, shown
    assert "merge its pull request" not in shown


def a_ready_row_with_unknown_checks_still_says_ready_and_its_step(_request, tmp_path):
    board = copy.deepcopy(PREVIOUS["board"])
    board["items"][0]["next"] = {"command": None}
    shown = board_tab(tmp_path, canned={"board": board, "next": FIXTURE["next"]})
    assert "READY TO MERGE\nPolish the guide\nReady to merge\n→ see forge next" in shown, shown


@pytest.mark.parametrize("case", [a_worker_question_needs_you_with_its_answer_step,
                                  a_ready_row_with_unknown_checks_still_says_ready_and_its_step,
                                  opened_waiting_rows_and_a_remote_ready_row_show_their_state_and_step,
                                  a_review_stop_needs_you_with_the_step_forge_next_prints, groups_in_plain_words, zero_counts_unknown_go_live_and_failures_stay_hidden,
                                  an_older_forge_board_draws_rows_and_no_team_line])
def test_1_the_board_tab_and_forge_text_read_in_plain_words(request, tmp_path, case):
    case(request, tmp_path)
