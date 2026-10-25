---
status: accepted
confirmed_by: "Ravi Kiran Vemula"
date: 2026-10-24
stories: [FORGE-TESTPLACE-1]
supersedes: ""
---

# One test place per repo

## Context

Every change runs its tests on the laptop at close and again in the pull request's CI. Close
also refuses a repo with no named checks. This runs tests twice and stops repos without CI at
close.

## Decision

Each repo chooses one place for change tests: CI or the laptop. The place runs related tests,
lint and type checks once. Existing repos use CI when their checks list is not empty and the
laptop when it is empty. They can set `test_place` to switch places.

New repos answer whether they run GitHub Actions. Yes sets `test_place = "ci"` and keeps the
named checks. No sets `test_place = "local"` with no checks. Repos without GitHub CI can close
and merge on a clean review and passing laptop tests.

The full suite runs nightly on main. A failed full run opens a fix that names the failing tests.
A release or client sign-off waits for a green full run on the current main; everyday merges do
not.

## Consequences

The pull request runs related tests in CI when the repo uses CI. A local repo runs those tests
at close and does not wait for GitHub checks. Close and merge use the selected place, and local
tests that pass are proof for merging.

Supersedes in part: 0092's 'CI is the proof' bullet (close runs tests in one place, CI or the
laptop; the pull request runs related tests; the full suite runs nightly), its 'the full suite
keeps running on every PR as a hard gate', and its consequences that local runs are not proof
and that a repo whose CI runs no tests has no proof. 0092's review loop and the rest stand.
