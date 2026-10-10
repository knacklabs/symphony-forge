These are the unchanged close, review and PR-check modules and review template from the default branch at
5e99b7c93fe57137080441d74cf46136ddb55baf (Forge v1.2.4), before branch-diff review reuse.
The command test runs these real modules with the other Forge libraries. Those
libraries were identical in that base and this fix when the fixture was captured.
This pins the checker that CI installs from the PR base, rather than the new checker.

The review template is pinned with its renderer: current templates can require inputs the
old renderer does not supply.

The checks module is pinned with close: current check waiting requires the pull request's
branch, which this earlier close does not supply.

ponytail: only these owners are pinned because the other libraries match this base;
if a later refactor changes an API these old modules call, pin that dependency from
the same base here as well, rather than changing the old checker to fit new code.
