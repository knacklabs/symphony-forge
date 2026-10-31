"""Sign-off overlaps independent review parts without extra model calls.

Test audit: protects concurrency, ordered results and model-call count through
the decision CLI. Existing whole-review fakes cannot expose the pinned helper's
serial pass loop. This external contract fixture replaces only the provider
behind that pass interface. No production test seam is needed.
"""
import socket
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from test_proto_signoff import _adopted_client, _client, _decision, _request_build

STORY = "client-sign-off-takes-about-an-hour-for"
pytestmark = pytest.mark.platform

HELPER = '''
import argparse, json, subprocess, sys
from pathlib import Path

def run_reviewer(args, repo, prompt, changed_paths, required, evidence=None):
    subprocess.run([args.launcher, 'exec', '--json', '-C', str(repo), '-'],
                   input=str(prompt), text=True, capture_output=True, check=True)
    return prompt

# The pinned helper's pass interface and serial scheduling.
def run_review_passes(args, reviewers, repo, prompts, changed_paths, evidence=None):
    args.review_usage = reviewers[0].review_usage = []
    return [(f'chunk {index}/{len(prompts)}',
             run_reviewer(reviewers[0], repo, prompt, changed_paths, [], evidence))
            for index, prompt in enumerate(prompts, 1)]

def sanitized_main():
    argv = sys.argv[1:]
    args = argparse.Namespace(launcher=argv[argv.index('--codex-bin') + 1])
    prompts = [str(index) for index in range(13)]
    results = run_review_passes(args, [args], Path.cwd(), prompts, set())
    assert [label for label, result in results] == [f'chunk {i}/13' for i in range(1, 14)]
    assert [result for label, result in results] == prompts
    Path(argv[argv.index('--json-output') + 1]).write_text(json.dumps(
        {'review_status': 'scoped-clean', 'findings': []}), encoding='utf-8')
    return 0

if __name__ == '__main__':
    raise SystemExit(sanitized_main())
'''

PROVIDER = '''
import json, os, socket, sys
sys.stdin.read()
print(json.dumps({'type': 'thread.started', 'thread_id': str(os.getpid())}), flush=True)
with socket.create_connection(('127.0.0.1', int(os.environ['REVIEW_PORT']))) as peer:
    peer.sendall(b'x')
    peer.recv(1)
print(json.dumps({'type': 'turn.completed', 'usage': {
    'input_tokens': 1, 'cached_input_tokens': 0, 'output_tokens': 1}}), flush=True)
'''


@pytest.mark.parametrize("setup", [_client, _adopted_client], ids=["new", "adopted"])
def test_1_signoff_review_parts_overlap_without_extra_model_calls(repo, tmp_path, monkeypatch, setup):
    fix, answers, _ = setup(repo, tmp_path, monkeypatch)
    if setup is _adopted_client:
        _request_build(repo, fix)
    page = _decision(fix, answers)
    (tmp_path / "autoreview/scripts/autoreview").write_text(HELPER, encoding="utf-8")
    (tmp_path / "codex-stub").write_text(f"#!{sys.executable}\n" + PROVIDER, encoding="utf-8")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        listener.settimeout(10)
        monkeypatch.setenv("REVIEW_PORT", str(listener.getsockname()[1]))

        def rendezvous():
            overlaps = []
            for _ in range(2):  # Canvas and product each have thirteen calls.
                peers = []
                try:
                    peers.append(listener.accept()[0])
                    try:
                        for _ in range(12):
                            peers.append(listener.accept()[0])
                    except TimeoutError:
                        pass
                finally:
                    for peer in peers:
                        with peer:
                            assert peer.recv(1) == b'x'
                            peer.sendall(b'x')
                overlaps.append(len(peers))
                # Also release serial calls so the pre-fix command can finish.
                for _ in range(13 - len(peers)):
                    with listener.accept()[0] as peer:
                        assert peer.recv(1) == b'x'
                        peer.sendall(b'x')
            listener.settimeout(0.2)
            with pytest.raises(TimeoutError):
                listener.accept()
            return overlaps

        with ThreadPoolExecutor(max_workers=1) as pool:
            observed = pool.submit(rendezvous)
            result = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
            overlaps = observed.result()
    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: accepted" in page.read_text("utf-8")
    assert overlaps == [13, 13], "Independent parts waited for earlier parts to finish"
