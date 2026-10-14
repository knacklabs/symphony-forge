---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-14T14:16:14.707605+00:00
seconds: 51.037
read_hash: 20104295eba2311e0514492057d9c2581987908f
round: 42
passed: yes
doc_seen: 20104295eba2311e0514492057d9c2581987908f
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: f33a7dc8665ca61b0d8b265cf29e5844d8440ba3
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a138d9-664f-7b40-bb0e-9a66ddfe7a00
session:
blocked_rounds: 0
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
or is factually wrong, and give as the reason the Leave out line, the missing Raise line, the
cited fact that disproves it, or the human's `Decided:` line.

Only a genuine trade-off goes to the human, as a question with options.

## Round 1

1. Blocking: Provider-key setup does not define a safe secret-storage boundary.
   Raise: Security. [The spec](/docs/specs/sandbox-runs.md:59) puts provider account/key setup in a `forge.toml` fix without distinguishing a secret reference from the credential itself. `forge.toml` is tracked, and the sandbox receives the branch. A literal implementation therefore commits and distributes the provider key. The spec needs to forbid storing credentials in committed settings.
   Gain 5, Work 2, Harm 4
   Disposition: cut

2. Blocking: Remote admission is undefined when both the laptop and sandbox cap are full.
   Raise: Plan gap. [Behaviour item 4](/docs/specs/sandbox-runs.md:56) requires overflow instead of waiting and introduces a remote cap; acceptance criterion 2 repeats the unconditional remote start. Parallel starts exceeding both caps are the feature's normal workload, but the spec chooses neither waiting nor refusal in that state. Existing admission explicitly queues excess runs in [machine.py](/src/forge/machine.py:174).
   Gain 4, Work 2, Harm 3
   Disposition: cut

3. Blocking: The remote handback does not define how pending worker questions reach local close.
   Raise: Plan gap. [The transport contract](/docs/specs/sandbox-runs.md:63) specifies streamed output and a commit bundle, but no terminal-result handback. Workers normally record trailing questions in [worker.py](/src/forge/worker.py:332); that record lives outside committed files in [codex.py](/src/forge/codex.py:797). Local [close.py](/src/forge/close.py:141) checks it before proceeding. A remote worker asking a security or scope question can therefore return commits without establishing the required local pause.
   Gain 4, Work 2, Harm 3
   Disposition: cut

## Round 2

4. Blocking: Acceptance criterion 7 would disable an opted-in repo on its next sync or upgrade.
   Raise: Plan gap. [Criterion 7](/docs/specs/sandbox-runs.md:104) says existing repos get sandbox runs turned off on upgrade and sync, without limiting this to repos that have never opted in. This conflicts with the persistent setting described at lines 64–66. Current configuration preserves explicit settings over defaults in [repo.py](/src/forge/repo.py:556), and upgrades preserve settings in [upgrade.py](/src/forge/upgrade.py:136). The criterion must distinguish default-off adoption from preserving an existing opt-in.
   Gain 4, Work 1, Harm 3
   Disposition: cut

## Round 3

No findings.

## Round 4

5. Blocking: Uploading the whole ignored working folder contradicts the credential exclusions.
   Raise: Security. [Lines 73–79](/docs/specs/sandbox-runs.md:73) require copying `.env` and its real keys while keeping provider and GitHub credentials off the sandbox. A developer can normally keep either credential alongside test settings in `.env`; [`.gitignore`](/.gitignore:2) permits that file locally. Approving its filename does not resolve which contents must be excluded or when transfer must refuse.
   Gain 5, Work 2, Harm 4
   Disposition: cut

6. Blocking: Automatic local fallback can start a second worker while the disconnected remote worker still runs.
   Raise: Plan gap. [Lines 112–117](/docs/specs/sandbox-runs.md:112) require local retry when the provider is unreachable and separately allow remote execution to survive a disconnected laptop. Losing connectivity therefore does not establish that the remote round stopped. The spec supplies neither confirmed termination before retry nor a rule rejecting its later result. Current [worker.py](/src/forge/worker.py:145) explicitly permits only one round per item.
   Gain 4, Work 2, Harm 3
   Disposition: cut

7. Blocking: Turning sandbox runs off can delete the only copy of outstanding worker commits.
   Raise: Data loss. [Lines 115–119](/docs/specs/sandbox-runs.md:115) retain uncollected results at the provider but require deleting all repo sandboxes and disks when disabled. Disabling while a round is running or awaiting collection is normal use. No rule requires collecting completed commits before deletion or settling what happens to active rounds. Unlike this deletion, local [stop](/src/forge/machine.py:388) terminates processes without erasing their working folders.
   Gain 5, Work 2, Harm 4
   Disposition: cut

8. Advisory: Simpler: Claude Agent SDK → the existing headless Claude Code command.
   Raise: Plan gap. [Lines 82–83](/docs/specs/sandbox-runs.md:82) describe the Claude Agent SDK as the driver Forge already uses locally. Current [worker.py](/src/forge/worker.py:628) invokes `claude -p` with streamed JSON. The SDK introduces a separate integration where the existing command already provides the stated worker and output behaviour.
   Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)

## Round 5

9. Blocking: Acceptance criterion 3 forbids the Git metadata needed for remote commits.
   Raise: Plan gap. [Criterion 3](/docs/specs/sandbox-runs.md:139) says the sandbox never holds a `.git` folder, while behaviour item 1 requires the remote worker to commit and return a bundle. The reused [Codex driver](/src/forge/codex.py:546) also requires a working Git repository. Excluding the laptop’s `.git` from uploads is compatible with this; forbidding a fresh remote `.git` is not. The criterion must distinguish those two.
   Gain 4, Work 1, Harm 3
   Disposition: cut

## Round 6

10. Blocking: The branch-only bundle leaves the remote worker unable to run `forge test`.
    Raise: Plan gap. [The new bootstrap rule](/docs/specs/sandbox-runs.md:75) supplies only the item’s branch history, with no remote. [fasttest.py](/src/forge/fasttest.py:262) requires `origin/<default branch>` and otherwise refuses with “Fetch … first: run git fetch origin, then forge test.” This affects the required worker tests, including Forge’s own first rollout. The bootstrap contract must also supply the pinned default-branch reference and its history locally, without adding credentials or a remote connection.
    Gain 4, Work 2, Harm 3
    Disposition: cut

## Round 7

No findings.

## Round 8

11. Blocking: Trap: E2B’s default expiry destroys results awaiting collection.
    Raise: Data loss. [The new provider choice](/docs/specs/sandbox-runs.md:75) adds E2B without a lifetime or retention rule. Its [creation API](https://docs.e2b.dev/api-reference/sandboxes/create-sandbox-v2) defaults to a 300-second lifetime with auto-pause disabled; [expiry kills the sandbox](https://docs.e2b.dev/sandbox/persistence). If a round finishes while the laptop sleeps for ten minutes, its uncollected commits and result can disappear before wake-up. Keeping the worker alive through Forge’s relay does not prevent provider expiry. E2B needs an explicit non-destructive expiry policy and a runtime policy that covers disconnected rounds.
    Gain 5, Work 2, Harm 4
    Disposition: cut

## Round 9

12. Blocking: The new 14-day cutoff permits losing commits that acceptance criterion 7 promises to collect.
    Raise: Data loss. [Lines 127–129](/docs/specs/sandbox-runs.md:127) end retention after 14 days and report the round lost. A developer returning after two weeks away can therefore lose uncollected worker commits. [Criterion 7](/docs/specs/sandbox-runs.md:150) still promises that results wait and are collected on wake, without that exception. This is a new deliberate loss policy, distinct from the provider’s default expiry in finding 11; its deletion and recovery behaviour must agree with the acceptance criterion.
    Gain 4, Work 2, Harm 4
    Disposition: cut

## Round 10

No findings.

## Round 11

13. Blocking: Close’s overflow trigger does not distinguish the test lane from the agent lane.
    Raise: Plan gap. [Criterion 2](/docs/specs/sandbox-runs.md:157) refers to “the laptop’s line,” while behaviour item 4 still uses agent capacity. Forge has [separate agent and test lanes](/src/forge/machine.py:300), and close tests join the [test lane](/src/forge/review.py:426). When tests fill their lane but agent places remain free, the routing rule does not establish whether close overflows—the newly named main case. It also leaves whether tests and review move together unresolved.
    Gain 4, Work 2, Harm 3
    Disposition: cut

14. Blocking: Committed-only dispatch leaves dirty worker retries without a rule.
    Raise: Plan gap. [Lines 81–85](/docs/specs/sandbox-runs.md:81) now transfer committed code only. A failed worker can leave tracked edits and new files uncommitted; current continuation explicitly includes those changes in [worker.py](/src/forge/worker.py:418). If its retry overflows remotely, the bundle omits that working state. The spec defines neither preserving it nor keeping/refusing that retry locally until it is committed.
    Gain 3, Work 2, Harm 3
    Disposition: cut

15. Blocking: Ready images have no refresh rule when dependencies or test setup change.
    Raise: Plan gap. [Lines 94–96](/docs/specs/sandbox-runs.md:94) say the image is built once from lockfiles and test setup. After a local worker commits a dependency upgrade, remote close can receive the new code with the old installed dependencies. A valid client command such as `npm test` performs no installation; [review.py](/src/forge/review.py:454) executes the configured command directly. The image needs a refresh or dependency reconciliation rule before checking changed inputs.
    Gain 4, Work 2, Harm 3
    Disposition: cut

## Round 12

16. Blocking: The relay’s unconditional leftover commit has no rule for a refused commit.
    Raise: Plan gap. [The new rule](/docs/specs/sandbox-runs.md:90) promises to commit stopped or stuck work. A fix can be stuck because its edits exceed the five-file limit or touch an interface; [the hooks](/src/forge/githooks.py:189) refuse those changes at commit and push. The spec does not establish how that work reaches the next round without bypassing the refusal.
    Gain 3, Work 2, Harm 3
    Disposition: cut

17. Blocking: Mainline setup does not bind a repository to the team that pays for its runs.
    Raise: Plan gap. [Setup](/docs/specs/sandbox-runs.md:130) signs in a laptop and asks teammates to join “the team,” while [configuration](/docs/specs/sandbox-runs.md:99) names only capacity and secrets. A developer working for two client teams needs a persistent rule selecting which team owns each repo’s sandboxes and receives its charges. Current [configuration](/src/forge/repo.py:437) supplies no existing account binding to reuse.
    Gain 4, Work 2, Harm 3
    Disposition: cut

18. Blocking: The promised small overdraft has no spending bound.
    Raise: Scale. [The credit rule](/docs/specs/sandbox-runs.md:145) lets running rounds finish after credits reach zero, but specifies neither a maximum charge nor runtime limit. Four active workers continuing overnight can keep accruing charges despite the dashboard’s spending limit. The reused [Claude runner](/src/forge/worker.py:635) waits for completion without an overall deadline. Admission and overdraft limits need a rule consistent with allowing those rounds to finish.
    Gain 4, Work 2, Harm 3
    Disposition: cut

## Round 13

19. Blocking: The new one-hour stop rule contradicts the acceptance criterion’s completion guarantee.
    Raise: Plan gap. [The credit rule](/docs/specs/sandbox-runs.md:150) now stops unfinished rounds one hour after credits run out, but [criterion 2](/docs/specs/sandbox-runs.md:178) still requires running rounds to finish. A long build can hit this case: the reused [worker runner](/src/forge/worker.py:642) has no overall deadline. The criterion must reflect the chosen stop-and-collect behaviour so implementation and acceptance agree.
    Gain 3, Work 1, Harm 3
    Disposition: cut

## Round 14

20. Blocking: Criterion 2 now applies the credit-exhaustion timeout to Mainline outages too.
    Raise: Plan gap. [The amended criterion](/docs/specs/sandbox-runs.md:178) requires stopping running rounds after one hour when Mainline is down **or** credits are exhausted. [The failure behaviour](/docs/specs/sandbox-runs.md:154) instead waits for confirmed termination or collection after connectivity loss; only credit exhaustion imposes the deadline. An API outage while a long worker still has credits therefore has conflicting rules. The reused [runner](/src/forge/worker.py:642) supplies no existing one-hour timeout. The criterion must distinguish these triggers.
    Gain 3, Work 1, Harm 3
    Disposition: cut

## Round 15

No findings.

## Round 16

21. Blocking: The shared Mainline vault has no boundary between sandbox and deployment secrets.
    Raise: Security. [The new vault rule](/docs/specs/sandbox-runs.md:99) uses the deployed apps’ secret store and writes entries by name, without an environment namespace or overwrite rule. A deployed client app and its tests normally both use `DATABASE_URL`: [deployment guidance](/src/forge/templates/conventions/deploy.md:15) supplies that variable, while [test guidance](/src/forge/templates/conventions/testing.md:14) requires a fresh test database. Importing the developer’s test value must not replace the deployed value, and sandbox runs must not inherit deployment credentials. The spec pins neither separation.
    Gain 5, Work 2, Harm 4
    Disposition: cut

## Round 17

No findings.

## Round 18

No findings.

## Round 19

22. Blocking: Borrowed capacity cannot be returned immediately without a rule for running borrowers.
    Raise: Plan gap. [The new fairness rule](/docs/specs/sandbox-runs.md:68) promises immediate return of lent places. With a team cap of two, one developer can occupy both places before another requests their share. The spec does not choose whether to interrupt the borrower or wait for completion. Existing [admission](/src/forge/machine.py:174) waits for occupied places; it supplies no reclamation behaviour. The fairness rule must settle this normal case.
    Gain 4, Work 2, Harm 3
    Disposition: cut

23. Blocking: Local-only teammates cannot supply the promised live team feed under the onboarding rule.
    Raise: Plan gap. [The new team view](/docs/specs/sandbox-runs.md:153) requires every laptop’s runs, but [teammate onboarding](/docs/specs/sandbox-runs.md:159) defers Mainline sign-in until that laptop fills. A teammate whose runs remain local therefore has neither authenticated publication nor a sandbox relay forwarding output. Current [board data](/src/forge/board.py:694) reads that machine’s lanes. The spec needs a consistent sign-in and publication rule for participating local laptops.
    Gain 4, Work 2, Harm 3
    Disposition: cut

## Round 20

No findings.

## Round 21

24. Blocking: Ready images do not prevent the configured test command from reinstalling dependencies.
    Raise: Plan gap. [The new startup rule](/docs/specs/sandbox-runs.md:168) promises that runs never install dependencies again. Forge’s [shipped client test command](/src/forge/templates/conventions/testing.md:20) begins with `npm ci` and a Playwright installation, and [the test runner](/src/forge/review.py:454) executes the configured command unchanged. Those supported repos reinstall on every remote test run despite the ready image. The spec must reconcile the startup promise with preserving the configured test behaviour.
    Gain 3, Work 2, Harm 3
    Disposition: cut

## Round 22

No findings.

## Round 23

25. Blocking: Periodic commit bundles do not preserve uncommitted work within the promised five-minute loss bound.
    Raise: Data loss. [The new checkpoint rule](/docs/specs/sandbox-runs.md:147) uploads a bundle every five minutes but snapshots uncommitted changes only on reclamation notice. Workers normally [test before committing at round end](/src/forge/templates/brief.md:48). If a worker edits for fifteen minutes without committing and the sandbox disappears without notice, every uploaded bundle still contains the old HEAD and all fifteen minutes are lost. Periodic checkpoints must preserve tracked edits and new files too, as local continuation already does in [worker.py](/src/forge/worker.py:418).
    Gain 5, Work 2, Harm 4
    Disposition: cut

## Round 24

No findings.

## Round 25

26. Blocking: The Docker exception leaves remote build rounds without a worker-test rule.
    Raise: Plan gap. [The new exception](/docs/specs/sandbox-runs.md:124) keeps Docker-dependent close runs local, but build rounds still overflow remotely and must run their tests there. Forge’s [standard database-client test command](/src/forge/templates/conventions/testing.md:20) uses Docker Compose, and [workers must complete those tests](/src/forge/templates/brief.md:48). The spec must establish how Docker-dependent build rounds remain eligible or stay local.
    Gain 4, Work 2, Harm 3
    Disposition: cut

27. Blocking: Owner stop permission contradicts the only-starter acceptance rule.
    Raise: Plan gap. [The changed authorization rule](/docs/specs/sandbox-runs.md:87) permits the starter or an Owner to stop a run, while [criterion 8](/docs/specs/sandbox-runs.md:222) still permits only the starter. An Owner stopping another developer’s run therefore requires opposite acceptance outcomes. Current [stop handling](/src/forge/machine.py:370) has no Mainline role rule resolving this.
    Gain 3, Work 1, Harm 3
    Disposition: cut

## Round 26

No findings.

## Round 27

28. Blocking: The confirmation hash does not match the revised spec.
    Raise: Gate. [The new frontmatter](/docs/specs/sandbox-runs.md:7) records a hash beginning `1a46cac9`, but the current body’s SHA-256 begins `8fedd79f`. [Roadmap admission](/src/forge/records.py:318) therefore refuses this spec, preventing its new third phase from being added. Confirmation must cover the revised body.
    Gain 4, Work 1, Harm 3
    Disposition: cut

## Round 28

No findings.

## Round 29

No findings.

## Round 30

No findings.

## Round 31

29. Blocking: Turning sandbox runs off cannot complete after Mainline refuses a bundle.
    Raise: Plan gap. [The new bundle rule](/docs/specs/sandbox-runs.md:64) retains refused results without pushing them—for example, a round changing `.github/workflows`. But [turning it off](/docs/specs/sandbox-runs.md:219) now waits until Mainline has pushed every finished round. That refusal can never satisfy the cleanup condition. The spec needs a recovery path for refused results that also permits shutdown.
    Gain 3, Work 1, Harm 3
    Disposition: cut

## Round 32

30. Blocking: Criterion 7 forbids the new discard path for refused results.
    Raise: Plan gap. [The new recovery rule](/docs/specs/sandbox-runs.md:65) lets the developer discard a refused bundle and clear its result. But [criterion 7](/docs/specs/sandbox-runs.md:239) permits deletion only after a successful push and fetch. Discarding a refused round therefore has conflicting acceptance outcomes. The criterion needs the new refused-result exception.
    Gain 3, Work 1, Harm 3
    Disposition: cut

## Round 33

No findings.

## Round 34

31. Blocking: Mainline’s Claude token vault conflicts with Anthropic’s credential restrictions.
    Raise: Plan gap. [The new rule](/docs/specs/sandbox-runs.md:71) makes Mainline store and distribute developers’ Claude OAuth tokens. [Anthropic’s policy](https://code.claude.com/docs/en/legal-and-compliance#authentication-and-credential-use) permits users to authenticate inside hosted, unmodified Claude Code, but expressly prohibits third-party developers from collecting or storing Claude session tokens. Switching from the SDK to the CLI does not resolve that separate storage restriction.
    Gain 4, Work 2, Harm 3
    Disposition: cut

32. Blocking: Event-based CI waiting has no catch-up or missed-delivery rule.
    Raise: Plan gap. [The new CI rule](/docs/specs/sandbox-runs.md:175) only forwards events and waits. CI can finish before close starts or while the laptop sleeps; GitHub also [does not automatically redeliver failed webhooks](https://docs.github.com/en/webhooks/using-webhooks/handling-failed-webhook-deliveries). Unlike the current [commit-specific snapshot](/src/forge/checks.py:204), this supplies no way to recover those completed checks. Close needs an initial snapshot or replay and missed-delivery reconciliation.
    Gain 4, Work 2, Harm 3
    Disposition: cut

33. Blocking: Reclamation can leave the vault holding an unusable Codex login.
    Raise: Plan gap. [The new authentication rule](/docs/specs/sandbox-runs.md:79) writes refreshed credentials back only when the run ends. If Codex rotates its token and the sandbox disappears without notice, the vault retains the consumed token; the code checkpoint does not preserve credentials. [OpenAI’s recovery guidance](https://learn.chatgpt.com/docs/auth/ci-cd-auth#what-to-do-when-refresh-stops-working) requires reseeding after a failed write-back restores stale credentials. The spec needs a rule for invalidating that login and recovering or replacing it before another round borrows it.
    Gain 4, Work 2, Harm 3
    Disposition: cut

## Round 35

No findings.

## Round 36

No findings.

## Round 37

34. Blocking: Criterion 5 still permits the API-key fallback that the new rule forbids.
    Raise: Plan gap. [The new model-access rule](/docs/specs/sandbox-runs.md:78) requires sandbox rounds to use plan logins only, with local execution or waiting when none is free. But [criterion 5](/docs/specs/sandbox-runs.md:265) still permits using the team’s API key. A second Codex round with the first login occupied therefore has conflicting acceptance outcomes. Remove the stale API-key fallback from the criterion.
    Gain 3, Work 1, Harm 3
    Disposition: cut

## Round 38

No findings.

## Round 39

35. Blocking: The credential-scrubbing variable has the wrong name.
    Raise: Security. [The new rule](/docs/specs/sandbox-runs.md:81) sets `CLAUDE_CODE_SCRUB_SUBPROC_ENV=1`, but [Anthropic’s security documentation](https://github.com/anthropics/claude-code-action/blob/main/docs/security.md) names `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB`. The installed Claude executable likewise recognizes only the latter. Implementing the specified variable leaves ordinary Bash and hook subprocesses inheriting the developer’s OAuth token, contradicting the promised separation even without Docker root access. Use the supported variable.
    Gain 4, Work 1, Harm 4
    Disposition: cut

## Round 40

No findings.

## Round 41

No findings.

## Round 42

No findings.
