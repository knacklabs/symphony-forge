# Contributing

Clone this repository, then run `uv sync` and `uv run pytest` to run the tests. The Codex SDK is
not needed for the tests. Start fixes with `forge fix start "<why>" --done "<done when>"` so the
pull request uses a Forge branch; the pull-request check accepts only Forge branches.

Forge's own CI balances its test groups using the committed `.test_durations` file.
Refresh it from the repository root after changes to slow tests:

```sh
uv run --python 3.11 pytest tests -q -n auto -o faulthandler_timeout=120 --timeout=150 --timeout-method=thread --store-durations --clean-durations
```

Commit the refreshed file after the full run passes. Check the latest CI run on all three
platforms: each group, including setup, must finish within seven minutes on Ubuntu and macOS,
and fourteen minutes on Windows (70% of its job limit). These settings affect only Forge's
own repository; new and existing client repositories get no change.
