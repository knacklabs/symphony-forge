from pathlib import Path


STORY = "forge-s-code-sits-at-its-8-000-line-ceil"
ROOT = Path(__file__).resolve().parents[1]


def test_1_forge_has_room_for_the_open_work(repo):
    assert repo.forge("--help").returncode == 0
    files = [path for path in (ROOT / "src" / "forge").rglob("*")
             if path.is_file() and "__pycache__" not in path.parts]
    lines = sum(path.read_bytes().count(b"\n") for path in files)
    assert lines <= 7850, f"src/forge has {lines} lines; the open work needs room below 7,850"
