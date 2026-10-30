"""Forge's own Windows workflow uses fast storage and records native timings.

These config contracts apply only to Forge's CI, so client adoption is unchanged.
Native runner speed remains a dispatched-run check.
"""
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.platform

STORY = "FIX-WINDOWS-CI-SPEED"
WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/forge-next.yml"


def test_1_windows_test_repositories_use_the_data_drive():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    windows_steps = [step for step in workflow.split("      - ")
                     if "if: runner.os == 'Windows'" in step]
    setup = next((step for step in windows_steps if 'GITHUB_ENV' in step), "")
    assert re.search(r'New-Item .*D:[/\\]t', setup)
    for variable in ("TEMP", "TMP"):
        assert re.search(rf'{variable}=D:[/\\]t', setup)
    command = next(line for line in workflow.splitlines() if 'pytest @testFiles -q -n auto' in line)
    assert '--basetemp D:/t/pytest' in command


def test_2_windows_caches_the_cache_directory_reported_by_npm():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    steps = workflow.split("      - ")
    discovery = next((step for step in steps if 'npm config get cache' in step), "")
    assert "if: runner.os == 'Windows'" in discovery
    output = re.search(r'([\w-]+)=\$\(npm config get cache\)', discovery)
    assert output and 'GITHUB_OUTPUT' in discovery
    step_id = re.search(r'id: ([\w-]+)', discovery)[1]
    cache = next((step for step in steps if 'uses: actions/cache@' in step
                  and "if: runner.os == 'Windows'" in step), "")
    assert f'path: ${{{{ steps.{step_id}.outputs.{output[1]} }}}}' in cache
    assert re.search(r'key: .*\$\{\{ runner.os \}\}', cache)


def test_3_windows_uploads_each_groups_own_timings_even_after_failure():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    command = next(line for line in workflow.splitlines() if 'pytest @testFiles -q -n auto' in line)
    assert '--durations=30 --store-durations --clean-durations' in command
    # Clean durations exclude the Linux seed and other groups from each artifact.
    timing_path = re.search(r'--durations-path (.+)$', command)[1]
    assert "hashFiles('.test_durations_windows')" in timing_path
    assert "'.test_durations_windows'" in timing_path
    upload = next((step for step in workflow.split('      - ')
                   if 'uses: actions/upload-artifact@' in step), '')
    assert "if: always() && runner.os == 'Windows'" in upload
    assert re.search(r'name: .*Windows.*\$\{\{ matrix.group \}\}', upload)
    assert f'path: {timing_path}' in upload
    assert 'include-hidden-files: true' in upload
