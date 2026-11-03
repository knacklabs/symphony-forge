"""The retained API client turns a non-JSON reply into its normal error with the status."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_libs_layout import lint_starter  # noqa: F401 - a module fixture, installed once here

STORY = "the-web-api-client-reads-every-reply-as"
LIVE = os.environ.get("FORGE_STARTER_LIVE") == "1"


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_1_a_non_json_reply_raises_the_normal_request_error_with_its_status(lint_starter):
    if not LIVE:
        pytest.skip("set FORGE_STARTER_LIVE=1 to run the starter Vitest case")
    live, skip_reason = lint_starter
    if live is None:
        pytest.skip(skip_reason)
    folder, env, corepack = live
    test_file = folder / "libs/core/web/src/api-client.test.ts"
    assert not test_file.exists(), test_file
    (folder / "test-results").mkdir(exist_ok=True)
    test_file.write_text(
        """import { afterEach, expect, test, vi } from 'vitest';
import { ApiError, apiRequest } from './api-client';

afterEach(() => vi.unstubAllGlobals());

test('a non-JSON reply raises the normal request error with its status', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
    new Response('<html>Bad Gateway</html>', {
      status: 502,
      headers: { 'content-type': 'text/html' },
    }),
  ));
  const error = await apiRequest('/projects').catch((caught: unknown) => caught);
  expect(error).toBeInstanceOf(ApiError);
  expect(error).toMatchObject({
    status: 502,
    code: 'REQUEST_FAILED',
    message: 'The request failed. Try again.',
  });
});
""",
        encoding="utf-8",
    )
    try:
        result = subprocess.run(
            [corepack, "pnpm", "exec", "vitest", "run", "--config",
             Path("apps") / "web" / "vitest.config.ts", test_file.relative_to(folder)],
            cwd=folder, env=env, capture_output=True, text=True, timeout=180,
            shell=sys.platform == "win32",
        )
    finally:
        test_file.unlink(missing_ok=True)
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
