# Second-opinion architectural audit of the cadence repo (READ-ONLY)

Target repo: /Users/dev/Workdir/cadence (absolute path; NOT this workspace).
Read it directly. Do not modify any file anywhere. Return findings only.

A first audit already ran. Your job is to find what it MISSED or got WRONG.
Do not repeat confirmed findings; reference them by number only when you
disagree or extend them. Verify every claim you make against files; cite
paths and line numbers. Run `tsc --noEmit`/tests in read-only fashion if
useful (no file writes; no installs).

## End goal (unchanged)
Cadence = company-wide OBSERVATION system for every KnackLabs developer
laptop: counts-only telemetry (Claude Code/Codex usage; GitHub PR outcomes
via the dev's gh; monthly 4-question pulse; optional symphony-forge read-only
event export where a repo runs the harness). Never code/prompts/chat. Company
devices in scope by policy; third-party-NDA repos are `client-restricted`
(cost/hours only); personal/OSS bucketed as "other work". Coverage tiers per
repo (usage/delivery/factory), never compared across tiers; forge is an
optional add-on. Roles assigned by an admin in-app: leadership (team-level
cross-project delivery health), PM (per-project epic->story pages, factory
tier only), developer (SELF-VIEW ONLY, no leaderboards — decision 0001),
admin (users->roles, projects<->repos, monthly "one change"). Academy
(compass CLI) upskills devs with custom skills and graded exercises; progress
rides the same ingest and shows in self-view + team funnels. Stack decided:
TS CLI; Cloudflare Workers + D1; Next.js on OpenNext with shadcn; Google
OAuth (knacklabs.ai) Worker-owned PKCE; hashed bearer device tokens; six
analytics views as a shared TS module.

## First audit — findings already confirmed (do not repeat)
1. workers/src/enroll.ts:1 imports a deleted supabase/ schema -> Worker does not compile on main.
2. No role model: devs has no role; no projects/project_members/repos tables; auth = DASHBOARD_ADMIN_EMAILS allowlist; non-admins hit /denied; no admin UI.
3. No app shell: layout.tsx is bare; one route; header hardcoded in page.tsx.
4. BRIEF, decision 0018, AGS-27 story, course-platform.md §4 still grant admin per-dev drill-down (contradicts 0001 / self-view-only).
5. Payload/schema carry no repo identity; tiers/classes have nothing to hang on; pr_hash embeds host/owner/repo#n.
6. Views: full-table loads, no dev/project/date predicates, no tier; dead GET /views/<name> + VIEWS_ADMIN_KEY path.
7. pulse friction_text (prose) is shipped and rendered raw to leadership.
8. Academy not wired: no course[] in ingest schema, no course_attempts, no `compass grade --push`, sync:'local' hard-coded; only a tutor skill copied into a scratch workspace; no skill distribution/tracking.
9. Supabase residue in README/skill/error.tsx/workers README/docs; dist/ and prototype/ are committed build output; decisions 0001-0018 all status: proposed.
10. Auth/role tests cover only allowlist parsing and cookie crypto.
11. Risk: path-hash repo identity fragments per clone and can't join pr_hash; recommended hash of normalised origin URL + optional dev alias.

## What to hunt for (go beyond the above)
- Security: session cookie signing/rotation, CSRF on state-changing routes, OAuth state/nonce handling, token hashing salt/pepper, D1 access from the dashboard binding vs Worker boundary, secrets in repo, middleware bypass paths (static assets, API routes), open redirect in callback, rate limiting on ingest/enroll, replay of payloads, device token revocation.
- Data model: idempotency keys and upsert correctness (timezones, UTC Monday weeks, 3-day backfill window), baseline window freezing, revert/hotfix detection correctness, attribution trailer detection edge cases (squash, rebase, co-authors), Codex cost = 0 handling in views, percentile math.
- Collector robustness: ccusage version pinning, Codex session JSONL format drift, gh pagination/rate limits, Windows paths, scheduler registration failure modes, state.json corruption, clock skew, partial pushes, multiple machines per dev.
- Scalability/cost on Cloudflare: D1 row limits, Worker CPU time on full-table view loads, OpenNext cold starts, per-request D1 reads from the dashboard, caching.
- Privacy/compliance: what actually leaves the machine field-by-field (compare README privacy table vs ingest-schema.ts); anything re-identifying; retention/deletion (v1 policy "delete on request") — is deletion implementable?
- Ops: CI coverage for each package (root, workers, dashboard, academy), deploy scripts, env var documentation drift, migrations tooling, rollback.
- Product/measurement: are the six views' metric definitions consistent with docs/specs/impact-metrics.md (ranges not points, 4-week trailing, guardrails beside speed); is anything in the views a leaderboard in disguise; does `cadence me` (src/me.ts) already leak or compare.
- Academy: grading determinism, LLM-judge guardrails as specified vs implemented, catalog versioning, exercise isolation (ports/sqlite), how a "custom skill" would be versioned and whether its usage could be counted at all.
- Harness: anything in the cadence repo's roadmap/decisions/specs that contradicts the newly confirmed docs/specs/role-views-and-coverage-tiers.md or the symphony-forge docs/specs/factory-event-export.md (read it at /Users/dev/Workdir/symphony-forge/docs/specs/factory-event-export.md).

## Deliver (<= 150 lines, blunt)
A. Findings the first audit missed, ranked P0/P1/P2, each: what, where (path:line), why it matters vs the end goal, smallest fix.
B. Findings where you DISAGREE with the first audit (by number) and why.
C. Any change to the proposed sanitise order (cutover+compile -> role model -> app shell -> admin console -> self-view enforcement -> academy wiring -> naming) and why.
D. The single most dangerous thing to leave as-is.
