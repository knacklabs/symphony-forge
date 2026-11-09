This workflow is the independent baseline for a client without `test_runner`.

It uses `tests/fixtures/adopted-v1.2.2/client/forge.toml`, with only its version
changed to v1.2.33. The workflow came from the pre-change `repo.py` and
`prcheck.py` at ee01d391b, through `prcheck.ships` with the real settings loader.
The test compares only job machine labels. Other workflow steps can change
without a change to this baseline.
