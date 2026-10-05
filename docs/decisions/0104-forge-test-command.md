---
status: accepted
confirmed_by: "Ravi Kiran Vemula"
date: 2026-10-05
stories: [FORGE-LANES-1]
supersedes: ""
---

# One Forge command for running tests

## Context

The Python picker must run as the separate Forge tool, outside the client's environment.
The approved machine-split story also needs a command for running tests in the test lane.

## Decision

Use one `forge test` command for both jobs, raising the command ceiling from 20 to 21.
This fix adds `forge test --pytest <base>` as the pytest picker; there is no separate
`forge fasttest` command. The owner chose this command on 2026-10-05.

The approved machine-split story gives bare `forge test` its meaning: run forge.toml's
fast_test, or test when fast_test is unset, in the test lane. Until that story lands,
bare `forge test` refuses in one line naming `--pytest`.

## Consequences

New and upgraded repos get the picker and its guidance. Upgrade preserves their test settings.
When bare `forge test` runs a fast_test that calls `forge test --pytest`, the picker does not
take the test lane again. The machine-split story reuses this command instead of adding another.
