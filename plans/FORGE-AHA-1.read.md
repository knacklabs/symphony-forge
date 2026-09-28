---
reader: codex (gpt-6-sol)
read_at: 2026-09-28T12:25:42+00:00
read_hash: 4f2103e7a9f965d90e3fd7a1d07f43b3c9e7b8cf
amended_hash: 1470f6a33a6bac1d513139906dde90336daca6bb
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc once, then
run `forge read <doc> --amended`:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options. There is no second read.

1. **Resolve the approved discovery contract before approving this story.**
   Done-when 6 removes `/office-hours`, but the confirmed `docs/specs/fde-discovery.md:31-40` requires it for new projects. No confirmed spec is linked to this story, so items 1–5 also lack a traced success measure. Pin the approved replacement and link it.
   Disposition: cut Done-when 8 now has a decision replace fde-discovery's /office-hours step; the owner chose this on 2026-09-28.

2. **Split: SPEC → preparation and discovery (1, 6); demo through sign-off (3, 4, 5).**
   SPEC covers five Done-when items at `plans/FORGE-AHA-1.md:72`; the task limit is three. Order the edits to the shared skill file.
   Disposition: cut SPEC now covers 1 and 8, a new DEMO task covers 4, 5 and 6, and DEMO follows SPEC for the shared skill file.

3. **Pin the shared discovery format before both tasks use it.**
   SPEC tells the agent to write `## Words they use` and `## Prototype notes`, while TEMPLATES defines those sections; both have `After: none` (`plans/FORGE-AHA-1.md:72-73`). TEMPLATES should pin their format first, with SPEC depending on it.
   Disposition: cut TEMPLATES pins both formats in the Notes, and SPEC waits on it.

4. **Pin the sign-off sequence and the scope of “every assumption.”**
   Done-when 5 names defaults and open must-answer topics, while the customer promise says *every assumption* (`plans/FORGE-AHA-1.md:19,54-58`). State how guesses and deferred topics are read back, when open must-answer topics are resolved, and that the email seeks approval of the reviewed version. The existing sign-off contract requires a fresh review and an accepted decision (`docs/specs/prototype-signoff.md:87-99`).
   Disposition: cut Done-when 6 now says the read-back covers defaults, guesses and later topics, settles open must-answers in that call, and the email is for the reviewed version.

5. **Define a guard the demo-data loader can enforce.**
   `DEMO_DATA=1` and “empty database on the demo host” (`plans/FORGE-AHA-1.md:40-45`) do not say how the app identifies that host or checks emptiness. Pin those checks in the convention so a misconfigured production run cannot insert sample records.
   Disposition: cut the loader runs only with APP_ENV=demo, DEMO_DATA=1 and every app table empty, and otherwise refuses.

6. **Test removal of the old discovery instruction.**
   The proposed tests check that new text exists (`plans/FORGE-AHA-1.md:79-81`). They should also check the generated skill and FDE page for the old `/office-hours` route; otherwise Done-when 6 can pass while the two instructions conflict.
   Disposition: cut Done-when 8 and the Notes add a test that the synced copies no longer mention /office-hours.
