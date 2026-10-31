---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-31T11:01:42.079157+00:00
seconds: 87.667
read_hash: aac9146fd479f3157d2689ccf0d043db000a814d
round: 3
passed: yes
doc_seen: aac9146fd479f3157d2689ccf0d043db000a814d
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 9edc73af7f004b753ba7c9c05ccedf531f038c56
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1916d-4bd7-7ef3-8292-924307ad5fb1
session:
loop_choice:
loop_reason:
---
# Cold read notes

Written by `forge read`. Under every blocking finding, write one disposition line, amend the
doc, then run `forge read <doc>` again until a round has no blocking notes. Notes marked
`Advisory:` are recorded without requiring a disposition or another round:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

A finding inside What counts is cut or deferred. Keep one only when it falls outside that boundary
or is factually wrong or not worth the change, and give as the reason the Leave out line, the
missing Raise line, the cited fact that disproves it, why it is not worth the change, or the
human's `Decided:` line.

Only a genuine trade-off goes to the human, as a question with options.

## Round 1

1. Blocking: Unproven: item 4: another organisation’s admin must not receive a reset link.
   Raise: Security.
   Case: normal use - an admin requests a reset link for an account belonging to another organisation.
   Settled 8 requires an “active member” and an admin role, but does not explicitly require membership in the caller’s organisation. The cases at `plans/FORGE-NOSCREENS-1.md:103` test an ordinary member’s refusal, which would pass even if every admin could reset every account. `src/forge/templates/conventions/security.md:22–26` requires organisation scope in addition to the role check; existing member operations implement it at `src/forge/templates/starter/libs/organisations/server/src/organisations.service.ts:101`. Pin that restriction and its refusal case for both starters.
   Gain 4, Work 2, Harm 4
   Disposition: cut - Settled 8 now limits the reset link to an active member of the admin's own organisation (404 for another organisation's account), and AUTH and AUTHPY carry the case `an admin cannot make a reset link for another organisation's member`.

2. Blocking: Plan gap: required updates to existing tests have no task owner.
   Raise: Plan gap.
   Case: normal use - the starter smoke run executes the existing API and browser checks after the planned changes.
   AUTH excludes `src/forge/templates/starter/apps/api/test/invites.e2e-spec.ts`, which requires identical first and retried answers at line 83 and refuses production invites without email at lines 275–288. AUTHPY excludes the matching `apps/api/tests/test_invites.py`, whose lines 60 and 411–434 assert the same old behaviour. These contradict Settled 8. SCREENS also excludes `tests/test_defaults_organisations.py`, which still requires deleted Members and Join browser flows at lines 55–59. Add these existing test owners to the corresponding task scopes; otherwise the promised green smoke run requires work outside Scope.
   Gain 4, Work 2, Harm 2
   Disposition: cut - `invites.e2e-spec.ts`, `test_invites.py` and `test_defaults_organisations.py` are now in the Scope of AUTH, AUTHPY and SCREENS with the cases to change.

3. Blocking: Unproven: items 2–4: the prescribed fixture does not represent an earlier starter app.
   Raise: Test.
   Case: normal use - the earlier-release cases run after SCREENS removes the starter screens.
   `plans/FORGE-NOSCREENS-1.md:48` requires `_adopted_files_after_sync`. That helper copies the current starter’s organisations, Projects and browser tests at `tests/test_mcp.py:54–56`. It will therefore copy the new rule specs before sync, contradicting item 4’s assertion that their folder is absent. The underlying adopted fixture contains only `AGENTS.md` and `forge.toml`; the helper supplies neither the old `apps/web/src/app.tsx` nor the API setup and lock file needed for item 2. Use a fixed earlier-release app fixture that contains the files these cases promise to preserve.
   Gain 4, Work 2, Harm 2
   Disposition: cut - the earlier-release cases use a new fixed fixture, `tests/fixtures/adopted-noscreens-before/client`, a frozen pre-story starter cut to the promised files with no rule specs; the plan no longer names `_adopted_files_after_sync` for them.

4. Blocking: Unproven: item 4: matching error answers still leave account existence observable through response time.
   Raise: Security.
   Case: normal use - a signed-out caller submits wrong passwords for candidate email addresses.
   `src/forge/templates/starter/libs/auth/server/src/auth.service.ts:144–146` skips password verification when the account does not exist. Python does the same at `src/forge/templates/starter-python/apps/api/app/auth/service.py:263–268`. Existing accounts take the expensive password-hashing path; unknown accounts return immediately. Settled 9 pins equal counters and answers but leaves this distinction intact, and its listed cases do not cover it. The promised “without telling anyone which accounts exist” needs equivalent password-verification work for unknown emails too.
   Gain 4, Work 2, Harm 4
   Disposition: cut - Settled 9 now has `signIn` check the password against a fixed dummy hash for an unknown email, with the case `an unknown email takes about as long to refuse as a wrong password` in both starters.

5. Advisory: Trap: item 6 names a repository setting that Forge rejects.
   Raise: Plan gap.
   Case: normal use - the builder prepares the prescribed Forge-repository test with `repo = "forge"`.
   Settled 16 and `plans/FORGE-NOSCREENS-1.md:117` specify that value. `src/forge/repo.py:573` accepts only `client` and `forge-source`; this checkout uses `forge-source` at `forge.toml:3`. Correct the test setup to use the existing supported value.
   Gain 3, Work 1, Harm 1
   Disposition: cut - the Forge-repository test now uses `repo = "forge-source"`.

## Round 2

6. Blocking: Plan gap: the new fixture creates a circular dependency between FEATURE and SCREENS.
   Raise: Plan gap.
   Case: normal use - FEATURE runs its required earlier-release test before SCREENS builds.
   The repair for finding 3 introduces a new ordering problem: `plans/FORGE-NOSCREENS-1.md:48` assigns fixture creation to SCREENS, while line 130 requires FEATURE to use it and line 131 puts SCREENS after FEATURE. The fixture does not exist, and neither task’s Scope includes its path. FEATURE therefore cannot pass its required test using the prescribed fixture. Starting SCREENS on FEATURE’s branch does not resolve this: `src/forge/task.py:518–521` requires the parent’s changes to have passed review. Assign fixture creation and its path to FEATURE, its first consumer.
   Gain 5, Work 1, Harm 2
   Disposition: cut - FEATURE now creates `tests/fixtures/adopted-noscreens-before/**` (in its Scope) and SCREENS reuses it; the fixed-fixture line no longer says SCREENS creates it.

## Round 3

No findings.
