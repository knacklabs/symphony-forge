"""Sign-off launches both reviews before either finishes.

Test audit: protects overlap and unchanged call count at the decision CLI.
Serial calls fail the socket rendezvous. Existing tests check results, not
overlap. Only the external reviewer is replaced; no production seam is needed.
"""
import socket
from concurrent.futures import ThreadPoolExecutor

import pytest

from test_proto_signoff import _adopted_client, _client, _decision, _request_build

STORY = "client-sign-off-takes-about-an-hour-for"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("setup", [_client, _adopted_client], ids=["new", "adopted"])
def test_1_signoff_checks_overlap_without_extra_model_calls(repo, tmp_path, monkeypatch, setup):
    fix, answers, queue = setup(repo, tmp_path, monkeypatch)
    if setup is _adopted_client:
        _request_build(repo, fix)
    page = _decision(fix, answers)
    reviewer = tmp_path / "autoreview/scripts/autoreview"
    reviewer.write_text(
        "import json, os, socket, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "with socket.create_connection(('127.0.0.1', int(os.environ['REVIEW_PORT']))) as peer:\n"
        "    peer.sendall(b'review')\n"
        "    peer.recv(1)\n"
        "Path(args[args.index('--json-output') + 1]).write_text(json.dumps(\n"
        "    {'review_status': 'scoped-clean', 'findings': []}), encoding='utf-8')\n",
        encoding="utf-8")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        listener.settimeout(10)
        monkeypatch.setenv("REVIEW_PORT", str(listener.getsockname()[1]))

        def rendezvous():
            peers = []
            overlap = False
            try:
                peers.append(listener.accept()[0])
                try:
                    peers.append(listener.accept()[0])
                    overlap = True
                except TimeoutError:
                    pass
            finally:
                for peer in peers:
                    peer.sendall(b'x')
                    peer.close()
            if not overlap:
                with listener.accept()[0] as peer:
                    peer.sendall(b'x')
            listener.settimeout(0.2)
            with pytest.raises(TimeoutError):
                listener.accept()
            return overlap

        with ThreadPoolExecutor(max_workers=1) as pool:
            observed = pool.submit(rendezvous)
            result = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
            overlap = observed.result()
    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: accepted" in page.read_text("utf-8")
    assert overlap, "The second review started only after the first review finished"
