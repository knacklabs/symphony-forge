import json
import subprocess
import sys
from pathlib import Path


def test_junit_reports_become_pytest_split_durations(tmp_path):
    repo = tmp_path / "repo"
    (repo / "factory" / "tests").mkdir(parents=True)
    (repo / "factory" / "tests" / "test_sample.py").write_text("")
    first = repo / "first.xml"
    second = repo / "second.xml"
    first.write_text(
        '<testsuite><testcase classname="factory.tests.test_sample" '
        'name="test_plain" time="1.25"/></testsuite>'
    )
    second.write_text(
        '<testsuite><testcase classname="factory.tests.test_sample.TestGroup" '
        'name="test_param[value]" time="2.5"/></testsuite>'
    )
    output = repo / ".test_durations"
    script = Path(__file__).resolve().parents[1] / "scripts" / "junit_to_durations.py"

    subprocess.run(
        [sys.executable, str(script), str(output), str(first), str(second)],
        cwd=repo,
        check=True,
    )

    assert json.loads(output.read_text()) == {
        "factory/tests/test_sample.py::TestGroup::test_param[value]": 2.5,
        "factory/tests/test_sample.py::test_plain": 1.25,
    }
