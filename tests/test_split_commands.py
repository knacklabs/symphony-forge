"""FORGE-SPLIT-1 command declarations at the installed command boundary."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import conftest

STORY = "FORGE-SPLIT-1"
SOURCE = Path(__file__).resolve().parents[1] / "src" / "forge"

# forge --help, each group and each command on main before COLLECTOR, with COLUMNS=80.
# The hook group's expected help now includes the handoff command shipped for PreCompact.
# Git's list merger used a Python snippet; its PATH command now appears as merge-roadmap.
# forge land joins the list after merge (FORGE-LAND-1), and forge roadmap retire after add.
# forge upgrade joins after migrate (FORGE-UPGRADECMD-1).
HELP_GOLDEN = {'': 'usage: forge [-h] [--version]\n'
     '             '
     '{init,sync,doctor,migrate,upgrade,next,board,story,read,task,fix,work,ask,close,merge,land,spec,decision,roadmap,hook}\n'
     '             ...\n'
     '\n'
     'Forge takes a story from approval to a merged pull request.\n'
     '\n'
     'options:\n'
     '  -h, --help            show this help message and exit\n'
     "  --version             show program's version number and exit\n"
     '\n'
     'commands:\n'
     '  '
     '{init,sync,doctor,migrate,upgrade,next,board,story,read,task,fix,work,ask,close,merge,land,spec,decision,roadmap,hook}\n'
     '    init                Set up a new repo: forge.toml, the docs skeleton, the\n'
     '                        first commit, then sync\n'
     '    sync                Write the generated adapter files and git hooks for\n'
     '                        the pinned version\n'
     '    doctor              Check tools, versions, hooks, adapter drift and the\n'
     '                        named CI checks\n'
     '    migrate             Move a client from the copied-in Forge to v1 in one\n'
     '                        pull request\n'
     '    upgrade             Upgrade Forge in this repo to a release, or the\n'
     '                        newest, through one fix\n'
     '    next                Say where things stand and give the exact next command\n'
     '    board               Write and open the plain-English board page\n'
     '    story               Start a story, or record its outcome\n'
     '    read                Run a round of the cold read of a story doc or spec\n'
     '    task                Start a task\n'
     '    fix                 Start a fix, let it go over the fix limit, or change\n'
     '                        its done-when\n'
     '    work                Run the configured worker on a task or fix\n'
     '    ask                 Ask Codex a read-only question about this checkout\n'
     '    close               Close a task or fix by the close rule\n'
     '    merge               Merge a ready item when this repo allows it\n'
     '    land                Build, close, fix and merge a task or fix\n'
     '    spec                Save and confirm specs, weigh whether a build pays\n'
     '                        back, and record its result\n'
     '    decision            Write and accept decisions\n'
     '    roadmap             Add and retire roadmap items\n'
     '    hook                Internal: the one entry point that git hooks, host\n'
     '                        hooks and CI call\n',
 'decision': 'usage: forge decision [-h] {new,accept} ...\n'
             '\n'
             'Write and accept decisions\n'
             '\n'
             'options:\n'
             '  -h, --help    show this help message and exit\n'
             '\n'
             'commands:\n'
             '  {new,accept}\n'
             '    new         Write a decision record\n'
             '    accept      Accept a decision after the human confirms in chat\n',
 'fix': 'usage: forge fix [-h] {start,allow-large,amend} ...\n'
        '\n'
        'Start a fix, let it go over the fix limit, or change its done-when\n'
        '\n'
        'options:\n'
        '  -h, --help            show this help message and exit\n'
        '\n'
        'commands:\n'
        '  {start,allow-large,amend}\n'
        '    start               Start a fix in its own branch and worktree, with a\n'
        '                        one-line why and done-when\n'
        "    allow-large         Record the human's permission for this fix to go over\n"
        '                        the fix limit\n'
        "    amend               Replace a fix's done-when, keeping the old text and\n"
        '                        the reason in its record\n',
 'hook': 'usage: forge hook [-h]\n'
         '                  {context,handoff,approval,deny,pre-commit,pre-push,merge-roadmap,pr-check}\n'
         '                  ...\n'
         '\n'
         'Internal: the one entry point that git hooks, host hooks and CI call\n'
         '\n'
         'options:\n'
         '  -h, --help            show this help message and exit\n'
         '\n'
         'commands:\n'
         '  {context,handoff,approval,deny,pre-commit,pre-push,merge-roadmap,pr-check}\n'
         '    context             Session start: print forge next and the story state\n'
         '    handoff             Before compaction: save forge next beside the agent\'s\n'
         '                        decisions and lessons\n'
         '    approval            After a plan or question tool: record approvals and\n'
         '                        count human touches\n'
         '    deny                Before a shell command: block destructive commands,\n'
         '                        --no-verify and gh pr merge\n'
         '    pre-commit          The git pre-commit rules\n'
         '    pre-push            The git pre-push rules\n'
         '    merge-roadmap       Merge the roadmap or spotted list for git\n'
         '    pr-check            The required forge-pr-check, run from the base branch\n',
 'roadmap': 'usage: forge roadmap [-h] {add,retire} ...\n'
            '\n'
            'Add and retire roadmap items\n'
            '\n'
            'options:\n'
            '  -h, --help    show this help message and exit\n'
            '\n'
            'commands:\n'
            '  {add,retire}\n'
            '    add         Add roadmap items from a confirmed spec\n'
            '    retire      Mark a pending roadmap item superseded by the spec that\n'
            '                replaces it\n',
 'spec': 'usage: forge spec [-h] {save,confirm,measure,payback} ...\n'
         '\n'
         'Save and confirm specs, weigh whether a build pays back, and record its result\n'
         '\n'
         'options:\n'
         '  -h, --help            show this help message and exit\n'
         '\n'
         'commands:\n'
         '  {save,confirm,measure,payback}\n'
         '    save                Save a spec as a draft\n'
         '    confirm             Mark a spec confirmed after the human confirms in chat\n'
         "    measure             Record the measured result in a confirmed spec's\n"
         '                        Success measure; it stays confirmed\n'
         '    payback             Say whether a build pays back: build, smallest slice\n'
         "                        first, don't build or find out first\n",
 'story': 'usage: forge story [-h] {new,done} ...\n'
          '\n'
          'Start a story, or record its outcome\n'
          '\n'
          'options:\n'
          '  -h, --help  show this help message and exit\n'
          '\n'
          'commands:\n'
          '  {new,done}\n'
          '    new       Start a story branch, worktree and story doc, or promote a fix\n'
          "    done      Record a finished story's outcome sentence and dates\n",
 'task': 'usage: forge task [-h] {start} ...\n'
         '\n'
         'Start a task\n'
         '\n'
         'options:\n'
         '  -h, --help  show this help message and exit\n'
         '\n'
         'commands:\n'
         '  {start}\n'
         '    start     Start a task in its own branch and worktree\n',
 # FORGE-LIVE-1 adds the answers forge init takes when it adopts a repo with history.
 'init': 'usage: forge init [-h] [--test TEST] [--checks CHECK] [--interfaces GLOB]\n'
         '                  [--approver APPROVER] [--merger MERGER] [--never-touch PATH]\n'
         '\n'
         'Set up a new repo: forge.toml, the docs skeleton, the first commit, then sync\n'
         '\n'
         'options:\n'
         '  -h, --help           show this help message and exit\n'
         '  --test TEST          a repo with history: the test command CI runs\n'
         '  --checks CHECK       a repo with history: a check branch protection requires\n'
         '  --interfaces GLOB    a repo with history: its route or migration folders\n'
         '  --approver APPROVER  a repo with history: who approves stories\n'
         '  --merger MERGER      a repo with history: who merges pull requests\n'
         '  --never-touch PATH   a repo with history: a path agents never change\n',
 'sync': 'usage: forge sync [-h]\n'
         '\n'
         'Write the generated adapter files and git hooks for the pinned version\n'
         '\n'
         'options:\n'
         '  -h, --help  show this help message and exit\n',
 'doctor': 'usage: forge doctor [-h] [--fix]\n'
           '\n'
           'Check tools, versions, hooks, adapter drift and the named CI checks\n'
           '\n'
           'options:\n'
           '  -h, --help  show this help message and exit\n'
           '  --fix       repair what doctor safely can: the pinned Forge, the Codex SDK,\n'
           '              the git hooks, the folders of finished work and the files forge\n'
           '              sync writes\n',
 'migrate': 'usage: forge migrate [-h] [--dry-run]\n'
            '\n'
            'Move a client from the copied-in Forge to v1 in one pull request\n'
            '\n'
            'options:\n'
            '  -h, --help  show this help message and exit\n'
            '  --dry-run   print the full plan and change nothing\n',
 'upgrade': 'usage: forge upgrade [-h] [release]\n'
            '\n'
            'Upgrade Forge in this repo to a release, or the newest, through one fix\n'
            '\n'
            'positional arguments:\n'
            '  release     such as v1.3.0; the newest when left out\n'
            '\n'
            'options:\n'
            '  -h, --help  show this help message and exit\n',
 'next': 'usage: forge next [-h]\n'
         '\n'
         'Say where things stand and give the exact next command\n'
         '\n'
         'options:\n'
         '  -h, --help  show this help message and exit\n',
 'board': 'usage: forge board [-h] [--out PATH]\n'
          '\n'
          'Write and open the plain-English board page\n'
          '\n'
          'options:\n'
          '  -h, --help  show this help message and exit\n'
          '  --out PATH  write the page here instead of .git/forge/board.html\n',
 'story new': 'usage: forge story new [-h] [--from-fix FIX] key [title]\n'
              '\n'
              'Start a story branch, worktree and story doc, or promote a fix\n'
              '\n'
              'positional arguments:\n'
              '  key\n'
              '  title\n'
              '\n'
              'options:\n'
              '  -h, --help      show this help message and exit\n'
              '  --from-fix FIX\n',
 'story done': 'usage: forge story done [-h] key outcome\n'
               '\n'
               "Record a finished story's outcome sentence and dates\n"
               '\n'
               'positional arguments:\n'
               '  key\n'
               '  outcome\n'
               '\n'
               'options:\n'
               '  -h, --help  show this help message and exit\n',
 'read': 'usage: forge read [-h] target\n'
         '\n'
         'Run a round of the cold read of a story doc or spec\n'
         '\n'
         'positional arguments:\n'
         '  target      a story key or a spec slug\n'
         '\n'
         'options:\n'
         '  -h, --help  show this help message and exit\n',
 'task start': 'usage: forge task start [-h] KEY/TASK\n'
               '\n'
               'Start a task in its own branch and worktree\n'
               '\n'
               'positional arguments:\n'
               '  KEY/TASK\n'
               '\n'
               'options:\n'
               '  -h, --help  show this help message and exit\n',
 'fix start': 'usage: forge fix start [-h] --done DONE_WHEN [--slug NAME] why\n'
              '\n'
              'Start a fix in its own branch and worktree, with a one-line why and done-when\n'
              '\n'
              'positional arguments:\n'
              '  why\n'
              '\n'
              'options:\n'
              '  -h, --help        show this help message and exit\n'
              '  --done DONE_WHEN\n'
              "  --slug NAME       the fix's name, instead of one cut from the why\n",
 'fix allow-large': 'usage: forge fix allow-large [-h] reason\n'
                    '\n'
                    "Record the human's permission for this fix to go over the fix limit\n"
                    '\n'
                    'positional arguments:\n'
                    '  reason\n'
                    '\n'
                    'options:\n'
                    '  -h, --help  show this help message and exit\n',
 'fix amend': 'usage: forge fix amend [-h] --done DONE_WHEN --because WHY FIX\n'
              '\n'
              "Replace a fix's done-when, keeping the old text and the reason in its record\n"
              '\n'
              'positional arguments:\n'
              '  FIX\n'
              '\n'
              'options:\n'
              '  -h, --help        show this help message and exit\n'
              '  --done DONE_WHEN\n'
              '  --because WHY\n',
 'work': 'usage: forge work [-h] [--note TEXT] item\n'
         '\n'
         'Run the configured worker on a task or fix\n'
         '\n'
         'positional arguments:\n'
         '  item\n'
         '\n'
         'options:\n'
         '  -h, --help   show this help message and exit\n'
         '  --note TEXT  guide this round of work\n',
 'ask': 'usage: forge ask [-h] [--model MODEL] [--effort EFFORT] question\n'
        '\n'
        'Ask Codex a read-only question about this checkout\n'
        '\n'
        'positional arguments:\n'
        '  question\n'
        '\n'
        'options:\n'
        '  -h, --help       show this help message and exit\n'
        '  --model MODEL    Codex model for this answer\n'
        '  --effort EFFORT  reasoning effort for this answer\n',
 'close': 'usage: forge close [-h] [--dismiss N] [--because FILE:LINE_REASON] item\n'
          '\n'
          'Close a task or fix by the close rule\n'
          '\n'
          'positional arguments:\n'
          '  item\n'
          '\n'
          'options:\n'
          '  -h, --help            show this help message and exit\n'
          '  --dismiss N\n'
          '  --because FILE:LINE_REASON\n',
 'merge': 'usage: forge merge [-h] [--outcome OUTCOME] item\n'
          '\n'
          'Merge a ready item when this repo allows it\n'
          '\n'
          'positional arguments:\n'
          '  item\n'
          '\n'
          'options:\n'
          '  -h, --help         show this help message and exit\n'
          '  --outcome OUTCOME  outcome for a story\'s last task; defaults to its title\n',
 'spec save': 'usage: forge spec save [-h] slug\n'
              '\n'
              'Save a spec as a draft\n'
              '\n'
              'positional arguments:\n'
              '  slug\n'
              '\n'
              'options:\n'
              '  -h, --help  show this help message and exit\n',
 'spec confirm': 'usage: forge spec confirm [-h] --by NAME slug\n'
                 '\n'
                 'Mark a spec confirmed after the human confirms in chat\n'
                 '\n'
                 'positional arguments:\n'
                 '  slug\n'
                 '\n'
                 'options:\n'
                 '  -h, --help  show this help message and exit\n'
                 '  --by NAME\n',
 'spec measure': 'usage: forge spec measure [-h] --result TEXT slug\n'
                 '\n'
                 "Record the measured result in a confirmed spec's Success measure; it stays\n"
                 'confirmed\n'
                 '\n'
                 'positional arguments:\n'
                 '  slug\n'
                 '\n'
                 'options:\n'
                 '  -h, --help     show this help message and exit\n'
                 '  --result TEXT\n',
 'spec payback': 'usage: forge spec payback [-h] [--build-days DAYS] [--day-rate AMOUNT]\n'
                 '                          [--hours-per-month HOURS] [--people COUNT]\n'
                 '                          [--hourly-rate AMOUNT] [--revenue-per-month AMOUNT]\n'
                 '                          [--incident-cost AMOUNT] [--incident-chance CHANCE]\n'
                 '                          [--confidence {measured,estimated,guessed}]\n'
                 '\n'
                 "Say whether a build pays back: build, smallest slice first, don't build or\n"
                 'find out first\n'
                 '\n'
                 'options:\n'
                 '  -h, --help            show this help message and exit\n'
                 '  --build-days DAYS\n'
                 '  --day-rate AMOUNT\n'
                 '  --hours-per-month HOURS\n'
                 '                        hours saved per person each month\n'
                 '  --people COUNT\n'
                 '  --hourly-rate AMOUNT\n'
                 '  --revenue-per-month AMOUNT\n'
                 '  --incident-cost AMOUNT\n'
                 '  --incident-chance CHANCE\n'
                 '                        the chance each month, from 0 to 1\n'
                 '  --confidence {measured,estimated,guessed}\n'
                 '                        weighs the value by 1, 1/2 or 1/5 (default: guessed)\n',
 'decision new': 'usage: forge decision new [-h] slug\n'
                 '\n'
                 'Write a decision record\n'
                 '\n'
                 'positional arguments:\n'
                 '  slug\n'
                 '\n'
                 'options:\n'
                 '  -h, --help  show this help message and exit\n',
 'decision accept': 'usage: forge decision accept [-h] --by NAME slug\n'
                    '\n'
                    'Accept a decision after the human confirms in chat\n'
                    '\n'
                    'positional arguments:\n'
                    '  slug\n'
                    '\n'
                    'options:\n'
                    '  -h, --help  show this help message and exit\n'
                    '  --by NAME\n',
 'roadmap add': 'usage: forge roadmap add [-h] spec\n'
                '\n'
                'Add roadmap items from a confirmed spec\n'
                '\n'
                'positional arguments:\n'
                '  spec\n'
                '\n'
                'options:\n'
                '  -h, --help  show this help message and exit\n',
 'roadmap retire': 'usage: forge roadmap retire [-h] --by SPEC key\n'
                   '\n'
                   'Mark a pending roadmap item superseded by the spec that replaces it\n'
                   '\n'
                   'positional arguments:\n'
                   '  key\n'
                   '\n'
                   'options:\n'
                   '  -h, --help  show this help message and exit\n'
                   '  --by SPEC\n',
 'hook context': 'usage: forge hook context [-h]\n'
                 '\n'
                 'Session start: print forge next and the story state\n'
                 '\n'
                 'options:\n'
                 '  -h, --help  show this help message and exit\n',
 'hook approval': 'usage: forge hook approval [-h]\n'
                  '\n'
                  'After a plan or question tool: record approvals and count human touches\n'
                  '\n'
                  'options:\n'
                  '  -h, --help  show this help message and exit\n',
 'hook deny': 'usage: forge hook deny [-h]\n'
              '\n'
              'Before a shell command: block destructive commands, --no-verify and gh pr\n'
              'merge\n'
              '\n'
              'options:\n'
              '  -h, --help  show this help message and exit\n',
 'hook pre-commit': 'usage: forge hook pre-commit [-h]\n'
                    '\n'
                    'The git pre-commit rules\n'
                    '\n'
                    'options:\n'
                    '  -h, --help  show this help message and exit\n',
 'hook pre-push': 'usage: forge hook pre-push [-h]\n'
                  '\n'
                  'The git pre-push rules\n'
                  '\n'
                  'options:\n'
                  '  -h, --help  show this help message and exit\n',
 'hook pr-check': 'usage: forge hook pr-check [-h]\n'
                  '\n'
                  'The required forge-pr-check, run from the base branch\n'
                  '\n'
                  'options:\n'
                  '  -h, --help  show this help message and exit\n'}


def _copy_forge(repo, tmp_path):
    package = tmp_path / "plugged" / "forge"
    shutil.copytree(SOURCE, package)
    (repo.bin / "forge").write_text(
        conftest.FORGE_SHIM.format(python=sys.executable, src=str(package.parent)),
        encoding="utf-8",
    )
    return package


def commands_keep_their_help_and_discover_a_new_owner(repo, tmp_path, monkeypatch):
    monkeypatch.setenv("COLUMNS", "80")
    for words, expected in HELP_GOLDEN.items():
        result = repo.forge(*words.split(), "--help")
        assert (result.returncode, result.stdout, result.stderr) == (0, expected, ""), words

    package = _copy_forge(repo, tmp_path)
    owner = package / "probe.py"
    owner.write_text(
        'def probe(args):\n    print(f"{type(args.dismiss[0]).__name__}:{args.dismiss}")\n'
        'COMMANDS = [{"words": "probe", "run": "probe", "changes_state": False, '
        '"help": "A newly owned command", '
        '"args": [(("--dismiss",), {"type": int, "action": "append", "metavar": "N"})], '
        '"position": 15, '
        '"listing": "| `forge probe` | A newly owned command |"}]\n',
        encoding="utf-8",
    )
    assert "probe" in repo.forge("--help").stdout
    assert repo.forge("probe", "--dismiss", "7", "--dismiss", "8").stdout == "int:[7, 8]\n"
    assert "invalid int value" in repo.forge("probe", "--dismiss", "seven").stderr
    owner.write_text(
        'def run(args):\n    print("group command ran")\n'
        'COMMANDS = [{"words": "probe run", "run": "run", "changes_state": False, '
        '"help": "Run the probe", "args": [], "position": 15, '
        '"listing": "| `forge probe run` | Run the probe |"}]\n',
        encoding="utf-8",
    )
    assert "group help missing: probe" in repo.forge("--help").stderr
    with owner.open("a", encoding="utf-8") as file:
        file.write('GROUP_HELP = {"probe": "Probe commands"}\n')
    assert repo.forge("probe", "run").stdout == "group command ran\n"
    (package / "other.py").write_text('GROUP_HELP = {"probe": "Duplicate"}\n',
                                      encoding="utf-8")
    assert "group help declared twice: probe" in repo.forge("--help").stderr
