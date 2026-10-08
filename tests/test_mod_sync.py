"""The real sync and doctor commands honour Claude's plugin CLI and isolation.

Only the external Claude CLI is faked. Existing adapter tests do not exercise
machine-wide plugin delivery; no production seam is needed for these contracts.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys

import pytest

from conftest import ROOT, FORGE_SHIM, _install, patient
from test_mod_install import (mod_reads_real_old_forge_refusal_and_spaced_working_directory,
                              real_claude_sync_installs_from_local_release_tag)
from test_mod_native import run_native_plugin_checks
from test_setup import _autoreview, _on_a_branch_with_forge_toml, _version

STORY = 'FORGE-MOD-1'

CLAUDE = """#!{python}
import json, pathlib, sys
here = pathlib.Path(__file__).resolve().parent
args = sys.argv[1:]
with open(here / 'claude-calls.jsonl', 'a', encoding='utf-8') as log:
    log.write(json.dumps(args) + '\\n')
state = json.loads((here / 'claude-state.json').read_text('utf-8'))
if args == ['--version']:
    print(state['version'] + ' (Claude Code)')
elif args == ['plugin', 'marketplace', 'list', '--json']:
    print(json.dumps([{{'name': 'forge', 'source': {{'source': 'github', 'repo': 'knacklabs/symphony-forge'}}}}] if state['marketplace'] else []))
elif args == ['plugin', 'list', '--json']:
    print(json.dumps([{{'id': 'forge@forge', 'version': state['installed'], 'scope': 'user', 'enabled': True}}] if state['installed'] else []))
elif state['offline']:
    sys.stderr.write('Network unavailable\\nretry later\\n')
    sys.exit(1)
"""


def _claude(repo, *, marketplace=False, installed='', offline=False, version='2.1.291'):
    (repo.bin / 'claude-state.json').write_text(json.dumps({
        'marketplace': marketplace, 'installed': installed,
        'offline': offline, 'version': version}), encoding='utf-8')
    _install(repo.bin, 'claude', CLAUDE.format(python=sys.executable))


def _calls(repo):
    log = repo.bin / 'claude-calls.jsonl'
    return [json.loads(line) for line in log.read_text('utf-8').splitlines()] if log.exists() else []


def _snapshot(top):
    return {path.relative_to(top).as_posix(): path.read_bytes()
            for path in top.rglob('*') if path.is_file() and '.git' not in path.relative_to(top).parts}


def _without_claude(repo, monkeypatch):
    # Never fall through to the developer's real install or settings.
    for name in ('claude', 'claude.cmd'):
        patient(lambda: (repo.bin / name).unlink(missing_ok=True))
    monkeypatch.setenv('PATH', os.pathsep.join(
        folder for folder in os.environ['PATH'].split(os.pathsep)
        if not shutil.which('claude', path=folder)))


def _sync_keeps_the_mod_current_at_user_scope(repo, monkeypatch, marketplace, installed):
    _on_a_branch_with_forge_toml(repo)
    _without_claude(repo, monkeypatch)
    assert repo.forge('sync').returncode == 0
    before = _snapshot(repo.path)
    _claude(repo, marketplace=marketplace,
            installed=_version(repo).removeprefix('v') if installed == 'current' else installed)
    monkeypatch.setenv('PATH', f'{repo.bin}{os.pathsep}{os.environ["PATH"]}')
    done = repo.forge('sync')
    assert done.returncode == 0, done.stderr
    writes = [args for args in _calls(repo) if args[:1] == ['plugin'] and 'list' not in args]
    assert writes == ([['plugin', 'marketplace', 'add', 'knacklabs/symphony-forge']] if not marketplace else []) + [
        ['plugin', 'marketplace', 'update', 'forge'],
        ['plugin', 'update', 'forge@forge', '--scope', 'user'] if installed else
        ['plugin', 'install', 'forge@forge', '--scope', 'user'],
    ]
    assert _snapshot(repo.path) == before  # Codex bytes unchanged; no repo-local mod files


def _sync_reports_plugin_failure_once_and_still_succeeds(repo):
    _on_a_branch_with_forge_toml(repo)
    _claude(repo, marketplace=True, installed='1.0.0', offline=True)
    done = repo.forge('sync')
    assert done.returncode == 0, done.stderr
    warnings = [line for line in (done.stdout + done.stderr).splitlines() if 'Warning:' in line]
    assert len(warnings) == 1, done.stdout + done.stderr
    assert 'Network unavailable' in warnings[0]
    assert 'retry later' not in done.stdout + done.stderr
    assert ['plugin', 'marketplace', 'update', 'forge'] in _calls(repo)
    assert ['plugin', 'update', 'forge@forge', '--scope', 'user'] not in _calls(repo)


def _sync_succeeds_without_claude_and_writes_no_mod_files(repo, monkeypatch):
    _on_a_branch_with_forge_toml(repo)
    _without_claude(repo, monkeypatch)
    done = repo.forge('sync')
    assert done.returncode == 0, done.stderr
    assert not _calls(repo)
    assert not (repo.path / '.claude-plugin').exists()
    assert not (repo.path / '.claude' / 'plugins').exists()
    assert (repo.path / '.codex' / 'config.toml').exists()


def _doctor_warns_about_unsupported_claude_without_failing(repo, gh, tmp_path, monkeypatch, version):
    _on_a_branch_with_forge_toml(repo)
    cfg = repo.path / 'forge.toml'
    cfg.write_text(cfg.read_text('utf-8') + 'workers = "claude"\n', encoding='utf-8')
    _claude(repo)
    assert repo.forge('sync').returncode == 0
    gh.respond('auth', 'status')
    gh.respond('api', 'repos/{owner}/{repo}/branches/main/protection', stdout=json.dumps({
        'required_status_checks': {'contexts': ['tests', 'forge-pr-check']}}))
    _autoreview(tmp_path, monkeypatch)
    home = tmp_path / 'codex-home'
    home.mkdir()
    (home / 'config.toml').write_text(
        f'[projects.{json.dumps(str(repo.path))}]\ntrust_level = "trusted"\n', encoding='utf-8')
    monkeypatch.setenv('CODEX_HOME', str(home))
    baseline = repo.forge('doctor')
    assert baseline.returncode == 0, baseline.stdout + baseline.stderr
    if version is None:
        _without_claude(repo, monkeypatch)
    else:
        _claude(repo, version=version)
    done = repo.forge('doctor')
    assert done.returncode == 0, done.stdout + done.stderr
    warnings = [line for line in done.stdout.splitlines() if 'Warning:' in line and 'Claude' in line]
    assert len(warnings) == (0 if version == '2.1.287' else 1), done.stdout
    if warnings:
        assert '2.1.287' in warnings[0]


def _marketplace_tracks_the_package_release():
    version = re.search(r'__version__\s*=\s*"([^"]+)"',
                        (ROOT / 'src/forge/__init__.py').read_text('utf-8')).group(1)
    manifest = json.loads((ROOT / '.claude-plugin/marketplace.json').read_text('utf-8'))
    assert manifest['name'] == 'forge'
    [plugin] = manifest['plugins']
    assert plugin['name'] == 'forge'
    assert plugin['version'] == version
    assert json.loads((ROOT / 'src/forge/mod/.claude-plugin/plugin.json').read_text('utf-8'))['version'] == version
    assert plugin['source'] == {
        'source': 'git-subdir', 'url': 'https://github.com/knacklabs/symphony-forge.git',
        'path': 'src/forge/mod', 'ref': f'v{version}',
    }


def _previously_adopted_repo_gets_the_mod(repo):
    patient(lambda: shutil.copytree(ROOT / 'tests/fixtures/adopted-v1.2.2/client', repo.path,
                                   dirs_exist_ok=True))
    repo.git('add', '-A')
    repo.git('commit', '-q', '-m', 'Adopt on the earlier release')
    repo.git('checkout', '-q', '-b', 'fix/mod-upgrade')
    cfg = repo.path / 'forge.toml'
    pinned = cfg.read_bytes()
    # uv is the external release transport. Run the actual old release from
    # its text fixture, so its adapter generation cannot be supplied by a fake.
    old = repo.bin.parent / 'old-release'
    patient(lambda: shutil.copytree(ROOT / 'tests/fixtures/forge-v1.2.2', old))
    (old / 'src/forge/cli-py.txt').rename(old / 'src/forge/cli.py')
    _install(repo.bin, 'old-forge', FORGE_SHIM.format(python=sys.executable, src=str(old / 'src')))
    _install(repo.bin, 'uv', f'''#!{sys.executable}
import os, sys
assert sys.argv[1:6] == ['tool', 'run', '--from',
    'git+https://github.com/knacklabs/symphony-forge@v1.2.2', 'forge']
os.execv({json.dumps(sys.executable)}, [{json.dumps(sys.executable)},
    {json.dumps(str(repo.bin / 'old-forge'))}, *sys.argv[6:]])
''')
    _claude(repo)
    done = repo.forge('sync')
    assert done.returncode == 0, done.stdout + done.stderr
    writes = [args for args in _calls(repo) if args[:1] == ['plugin'] and 'list' not in args]
    assert writes == [['plugin', 'marketplace', 'add', 'knacklabs/symphony-forge'],
                      ['plugin', 'marketplace', 'update', 'forge'],
                      ['plugin', 'install', 'forge@forge', '--scope', 'user']]
    assert not (repo.path / '.claude-plugin').exists()
    assert not (repo.path / '.claude' / 'plugins').exists()
    assert 'hooks = true' in (repo.path / '.codex/config.toml').read_text('utf-8')
    assert cfg.read_bytes() == pinned
    assert 'Generated by forge sync for Forge v1.2.2;' in (repo.path / '.forge/hooks.sh').read_text('utf-8')
    # Updating the user installation also works without first upgrading the pin.
    _claude(repo, marketplace=True, installed='1.2.5')
    before = len(_calls(repo))
    done = repo.forge('sync')
    assert done.returncode == 0, done.stdout + done.stderr
    writes = [args for args in _calls(repo)[before:] if 'list' not in args]
    assert writes == [['plugin', 'marketplace', 'update', 'forge'],
                      ['plugin', 'update', 'forge@forge', '--scope', 'user']]
    assert cfg.read_bytes() == pinned


@pytest.mark.parametrize('case', ['fresh-machine', 'already-current', 'older-install', 'no-network',
                                'no-claude', 'doctor-missing', 'doctor-old', 'doctor-supported',
                                'marketplace-version', 'previously-adopted', 'real-local-install',
                                'real-transport', 'native-plugin-checks'])
def test_5_sync_turns_on_the_mod(repo, gh, tmp_path, monkeypatch, case):
    if case in ('fresh-machine', 'already-current', 'older-install'):
        _sync_keeps_the_mod_current_at_user_scope(repo, monkeypatch, case != 'fresh-machine',
                                                {'fresh-machine': '', 'already-current': 'current',
                                                 'older-install': '1.0.0'}[case])
    elif case == 'no-network':
        _sync_reports_plugin_failure_once_and_still_succeeds(repo)
    elif case == 'no-claude':
        _sync_succeeds_without_claude_and_writes_no_mod_files(repo, monkeypatch)
    elif case.startswith('doctor-'):
        _doctor_warns_about_unsupported_claude_without_failing(
            repo, gh, tmp_path, monkeypatch,
            {'doctor-missing': None, 'doctor-old': '2.1.286', 'doctor-supported': '2.1.287'}[case])
    elif case == 'marketplace-version':
        _marketplace_tracks_the_package_release()
    elif case == 'previously-adopted':
        _previously_adopted_repo_gets_the_mod(repo)
    elif case == 'real-local-install':
        real_claude_sync_installs_from_local_release_tag(repo, tmp_path, monkeypatch)
    elif case == 'native-plugin-checks':
        # The native suite owns Machine layout and the separate rolling load-history check.
        run_native_plugin_checks(tmp_path)
    else:
        mod_reads_real_old_forge_refusal_and_spaced_working_directory(repo, tmp_path, monkeypatch)
