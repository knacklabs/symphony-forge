# Previous-release adoption fixture

`forge-v1.2.2.zip` contains the unmodified Forge source and skill inputs from
release v1.2.2, commit `3febf07f414725bdb5028830655f1c83368b5ec0`.
It was created with:

```
git archive --format=zip --output=tests/fixtures/forge-v1.2.2.zip v1.2.2 src .codex/skills .claude/skills
```

The merge-rule regression runs that release's real init command to adopt a client,
then upgrades it through current sync or doctor. In particular, doctor runs without
preparatory sync, leaving the previous release's roadmap-only tracked attributes
and checkout-bound driver in place until the repair. Keeping the release in this
fixture makes the test independent of tags and history in CI's shallow clones.
