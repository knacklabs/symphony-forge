---
reader: codex (gpt-6.1-terra)
read_at: 2026-11-19T10:24:02.668817+00:00
seconds: 603.377
read_hash: 72b9c8389d22500c8b32cfd8bab377caedcc430a
round: 2
passed: no
doc_seen: 72b9c8389d22500c8b32cfd8bab377caedcc430a
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 905810241b8ba1ad385c252c02a33c8eb42b24ca
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1f310-0028-72f3-9e9d-4bbc5e73ad20
session:
loop_choice: more
loop_reason: Owner chose one more round on 19 Nov 2026: save the login at setup, set Windows key permissions directly, drop the refusal link and page
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

1. Blocking: The signed app credential is exposed in process arguments.

   Raise: Security  
   Case: normal use - Forge starts a GitHub app request on a laptop with another local account.  
   [The plan](/plans/FORGE-GHAPP-1.md:92) puts the signed credential in a `gh` argument, and [repo.run](/src/forge/repo.py:252) passes it to the operating system. Another local user can read command arguments and use that credential to make tokens for the app’s installed repositories.  
   Adds work: keep the signed credential out of process arguments; F 1 x H 3 = 3; 2 x C = 4  
   Gain 2, Work 3, Harm 4
   Disposition: keep - fixed: the app's GitHub calls run in Python with urllib, so the JWT is never a process argument; the token reaches gh only as GH_TOKEN in its environment

2. Blocking: Not done: a configured user folder can put the private key inside the repo.

   Raise: Security  
   Case: normal use - A developer sets `XDG_CONFIG_HOME` to a project-local configuration folder.  
   [The plan](/plans/FORGE-GHAPP-1.md:88) uses the existing [config path](/src/forge/machine.py:106) without checking whether it is inside a checkout. The key can then be picked up by an ordinary `git add`, contrary to item 3.  
   Gain 5, Work 2, Harm 4
   Disposition: keep - fixed: setup refuses a key folder inside a git work tree

3. Blocking: Not done: the Windows key location can copy the key to another computer.

   Raise: Security  
   Case: normal use - A company uses Windows roaming profiles or redirects `AppData\Roaming` to a file share.  
   [The plan](/plans/FORGE-GHAPP-1.md:11) promises the key stays on one laptop but stores it under `%APPDATA%`. Windows can copy that profile to a server and other computers. [Microsoft: roaming profiles](https://learn.microsoft.com/en-us/windows-server/storage/folder-redirection/folder-redirection-rup-overview)  
   - Open question: Should Windows keep the key in local, non-roaming app data?
     Touches: The key location.
     Why we ask: The named `%APPDATA%` path can roam.
     Default: Use local app data for the key.
     Why this default: It preserves the promise that the key stays on the laptop.
     If the default stands: The documented Windows path changes.
     Due: 26 Nov 2026
   Gain 5, Work 2, Harm 4
   Disposition: keep - fixed: Windows uses LOCALAPPDATA, which does not roam

4. Blocking: Not done: doctor creates a token covering more than the current repo.

   Raise: Not done  
   Case: normal use - Doctor checks an app installed on selected repositories.  
   [The plan](/plans/FORGE-GHAPP-1.md:96) deliberately creates a metadata token without a repository limit, while its user-facing promise says every token reaches only the current repo. GitHub says an unbounded installation token reaches all repositories in the installation. [GitHub: installation tokens](https://docs.github.com/en/rest/apps/apps#create-an-installation-access-token-for-an-app)  
   - Open question: May doctor use an installation-wide, metadata-only token?
     Touches: Doctor’s warning and the token-scope promise.
     Why we ask: The planned warning needs to list repositories the developer cannot see.
     Default: Allow that token only for doctor’s check.
     Why this default: It retains the warning with limited permissions.
     If the default stands: The one-repo promise has an exception, and a copied doctor token can read metadata across the installation.
     Due: 26 Nov 2026
   Gain 4, Work 2, Harm 3
   Disposition: keep - fixed: doctor's token is for one repo like every other; the selected-repos check is cut

5. Blocking: Not done: doctor skips the wide-access warning when the current repo is not installed.

   Raise: Not done  
   Case: normal use - An app is installed on two selected repos, including one the developer cannot open, and the developer runs doctor in a third repo.  
   [The plan](/plans/FORGE-GHAPP-1.md:96) runs the warning only when the app is installed on the current repo. Item 1 promises the warning for the developer’s app, and the planned test covers only an installation on the current repo.  
   Gain 3, Work 2, Harm 3
   Disposition: cut - doctor now warns only on an install on all repos, which always covers the current repo

6. Blocking: Not done: the documented new-repo command stops before app setup.

   Raise: Not done  
   Case: normal use - A developer runs `forge init --github-app` in a new repo.  
   [The plan and its test](/plans/FORGE-GHAPP-1.md:113) omit `--actions`, but [init](/src/forge/init.py:384) refuses a repo without history when that answer is missing. The test cannot reach the browser step as written.  
   Gain 4, Work 1, Harm 3
   Disposition: keep - fixed: the new-repo command and its test pass --actions

7. Blocking: The app environment function cannot identify the calls it must exempt.

   Raise: Plan gap  
   Case: normal use - Close opens a pull request.  
   [The plan](/plans/FORGE-GHAPP-1.md:93) calls `ghapp.env(cwd)` but also requires that function to inspect `args` and `--body-file`. Those arguments are local to [repo.run](/src/forge/repo.py:222) and are not passed to the function. The owner’s required pull-request author depends on that distinction.  
   Gain 4, Work 1, Harm 3
   Disposition: keep - fixed: the hook is ghapp.env(args, cwd)

8. Blocking: Not done: removing `GH_TOKEN` prevents app authentication for token-only sign-ins.

   Raise: Not done  
   Case: normal use - A developer signs in to `gh` through `GH_TOKEN` and has no stored `gh` credential.  
   [The plan](/plans/FORGE-GHAPP-1.md:92) removes that variable before both app calls. GitHub CLI requires a configured authentication source before running `gh api`, so the explicit authorization header does not provide the CLI sign-in it expects. The stub at [tests/conftest.py:102](/tests/conftest.py:102) does not check that requirement. [GitHub: using the REST API with gh](https://docs.github.com/en/rest/using-the-rest-api/getting-started-with-the-rest-api?tool=cli)  
   Gain 4, Work 2, Harm 3
   Disposition: keep - fixed: the app calls do not use gh, so a GH_TOKEN-only sign-in still works

9. Blocking: Not done: setup uses an unsupported credential for manifest conversion.

   Raise: Not done  
   Case: normal use - A developer follows GitHub CLI’s guidance and uses a fine-grained personal token for sign-in.  
   [The conversion call](/plans/FORGE-GHAPP-1.md:101) inherits the developer’s credential through [repo.run](/src/forge/repo.py:255), but GitHub documents that the conversion endpoint does not work with fine-grained tokens. The planned stub always returns a successful conversion. [GitHub: manifest conversion](https://docs.github.com/en/rest/apps/apps#create-a-github-app-from-a-manifest)  
   Gain 3, Work 2, Harm 3
   Disposition: keep - fixed: the conversion runs through urllib with no credential

10. Blocking: Not done: a refused token during a long command does not fall back.

    Raise: Not done  
    Case: normal use - An organization owner uninstalls or suspends the app while close is waiting for checks.  
    [The fallback rule](/plans/FORGE-GHAPP-1.md:94) covers lookup and token creation, but not a later GitHub call that rejects an already-issued token. [github.run](/src/forge/github.py:109) returns that failure to the caller; the planned test rejects only the token-creation call.  
    Gain 3, Work 2, Harm 3
   Disposition: defer - rare (an uninstall during a running command), and running the command again falls back

11. Blocking: Not done: doctor’s recovery step cannot replace a deleted app.

    Raise: Not done  
    Case: normal use - An owner follows doctor’s instruction to delete an app whose key GitHub refuses.  
    [Doctor](/plans/FORGE-GHAPP-1.md:95) says to delete the app and rerun setup, but [setup](/plans/FORGE-GHAPP-1.md:100) has no rule to remove the saved key and app record. The saved record prevents the “no saved app” creation path, so the stated recovery cannot create a replacement.  
    Gain 3, Work 2, Harm 3
   Disposition: defer - rare; automatic replacement is left out, and doctor now names the two files to delete before setup runs again

12. Blocking: The member role check is not pinned to an API the member can use.

    Raise: Plan gap  
    Case: normal use - An organization member without App Manager runs setup.  
    [The plan](/plans/FORGE-GHAPP-1.md:87) leaves the role read for the builder to discover. GitHub’s documented role-assignment listing requires an organization administrator; the planned member test instead supplies a successful role response. When the read is unavailable, the plan opens GitHub and waits up to 15 minutes before reporting the missing role. [GitHub: organization roles API](https://docs.github.com/en/rest/orgs/organization-roles#list-users-that-are-assigned-to-an-organization-role)  
    Gain 4, Work 2, Harm 3
   Disposition: keep - fixed: no role read; GitHub's page decides, and the local page's /refused link ends the step at once with the role line

13. Blocking: Not done: the role instruction cannot be followed by an outside collaborator.

    Raise: Not done  
    Case: normal use - A client gives a contractor access to a repo without making them an organization member.  
    [Setup](/plans/FORGE-GHAPP-1.md:87) handles only owner and member responses and tells the owner to assign App Manager. GitHub assigns organization roles to members or teams, so the contractor cannot receive that role while remaining an outside collaborator. [GitHub: organization roles](https://docs.github.com/en/organizations/managing-peoples-access-to-your-organization-with-roles/using-organization-roles)  
    - Open question: How should an outside collaborator use Forge here?
      Touches: App setup for organization repos.
      Why we ask: Giving the role requires the client to make the collaborator a member.
      Default: Keep the collaborator on their existing gh sign-in until the client grants membership and the role.
      Why this default: It preserves their current access.
      If the default stands: They do not get a separate app budget until then.
      Due: 26 Nov 2026
    Gain 3, Work 2, Harm 3
   Disposition: defer - rare; a contractor who is not an organization member keeps their gh sign-in

14. Blocking: Not done: an adoption cannot retry app setup from the original checkout.

    Raise: Not done  
    Case: normal use - A developer adopts an existing repo, then app setup stops because they need the App Manager role.  
    [The plan](/plans/FORGE-GHAPP-1.md:99) runs adoption before the app step. Adoption writes `forge.toml` in a [separate worktree](/src/forge/init.py:466), and a rerun from the original checkout reaches the [existing adoption-branch refusal](/src/forge/init.py:445) instead of retrying the app step.  
    Gain 3, Work 2, Harm 3
   Disposition: cut - --github-app refuses during adoption and runs after the adoption merges, so there is no retry path

15. Blocking: Not done: personal-account setup does not verify the browser account.

    Raise: Not done  
    Case: normal use - `gh` is signed in to one GitHub account while the browser is signed in to another.  
    [The personal manifest](/plans/FORGE-GHAPP-1.md:101) creates the private app in the browser’s account, but the plan saves it for the repo owner without checking the owner returned by conversion. A private app owned by the other account cannot be installed on the intended account. [GitHub: installing a private app](https://docs.github.com/en/apps/using-github-apps/installing-your-own-github-app)  
    Gain 3, Work 2, Harm 3
   Disposition: keep - fixed: setup compares the conversion's owner with the expected owner and saves nothing on a mismatch

16. Blocking: Not done: app selection ignores the active developer’s login.

    Raise: Not done  
    Case: normal use - A developer switches between two GitHub sign-ins on the same laptop, with an app for each sign-in installed on the same organization repo.  
    [The saved format](/plans/FORGE-GHAPP-1.md:88) records the login, but [selection](/plans/FORGE-GHAPP-1.md:90) takes the first installed app without comparing it to the current login. Close can use the other identity’s app and budget, while doctor calls it “your app.”  
    Gain 3, Work 2, Harm 3
   Disposition: keep - fixed: the app is chosen by the active gh login and the repo's owner, at most one app

17. Blocking: Token discovery can deadlock while handling a rate limit.

    Raise: Plan gap  
    Case: normal use - GitHub rate-limits an installation lookup while close starts.  
    [App calls](/plans/FORGE-GHAPP-1.md:92) still pass through [github.run](/src/forge/github.py:109). Its quota read holds a [non-reentrant lock](/src/forge/github.py:18), then starts another `gh` call that invokes app discovery again. Another rate-limit response attempts to take the same lock and leaves the command stuck.  
    Adds work: prevent discovery from re-entering the quota read; F 2 x H 2 = 4; 2 x C = 4  
    Gain 3, Work 2, Harm 3
   Disposition: keep - fixed: the app calls bypass github.run, and ghapp.env returns {} while it reads the login and repo

18. Blocking: The planned tests cannot establish the Windows key and token behavior.

    Raise: Test  
    Case: normal use - A developer runs Forge’s tests on Windows without `openssl` on `PATH`.  
    [The plan](/plans/FORGE-GHAPP-1.md:107) requires every new test to create a key with `openssl`, although it identifies Windows laptops without that program. The [Windows CI job](/.github/workflows/forge-next.yml:146) selects platform-marked tests, and the plan does not mark these tests for it.  
    Gain 3, Work 2, Harm 3
   Disposition: keep - the tests are not platform-marked, so they run only where openssl exists; the Windows folder is one line read in review

19. Blocking: The token test mistakes an inherited personal token for the app token.

    Raise: Test  
    Case: normal use - The scheduled full suite runs with its configured `GH_TOKEN`.  
    [The test](/plans/FORGE-GHAPP-1.md:118) requires personal-sign-in calls to carry no `GH_TOKEN`, but [repo.run](/src/forge/repo.py:255) inherits the environment and the [full-suite job](/.github/workflows/forge.yml:210) sets that variable. The test needs to distinguish the personal credential from the app credential.  
    Gain 4, Work 1, Harm 2
   Disposition: keep - fixed: the tests unset GH_TOKEN and check the app tokens by value

20. Blocking: The new browser flow is marked as having no design or user-facing work.

    Raise: Gate  
    Case: normal use - A developer creates an app and an owner installs it.  
    [The plan](/plans/FORGE-GHAPP-1.md:17) says `Design: none`, although setup adds a browser page and flow. It also marks SETUP `user-facing: no` at [the task row](/plans/FORGE-GHAPP-1.md:128), which makes [review](/src/forge/review.py:325) omit the functional check.  
    Gain 4, Work 2, Harm 2
   Disposition: keep - fixed: Design names the local page, and SETUP is user-facing

21. Blocking: TOKEN does not pin the shared setup helpers or own the shared file.

    Raise: Plan gap  
    Case: normal use - SETUP starts after TOKEN and needs to save a key and find an installation.  
    [Both task scopes](/plans/FORGE-GHAPP-1.md:127) own `ghapp.py`, but TOKEN pins no callable names or signatures for the storage and lookup that SETUP uses. The shared-file rule assigns that file and its shared names to the first task.  
    Gain 4, Work 1, Harm 2
   Disposition: keep - fixed: TOKEN pins the ghapp names and signatures that SETUP uses

22. Advisory: The owner’s browser is redirected to a stopped local server after installation.

    Raise: Functional  
    Case: normal use - An App Manager creates the app and an organization owner installs it later from another computer.  
    [The plan](/plans/FORGE-GHAPP-1.md:101) exits the developer’s server without waiting, but registers its localhost address as the setup URL. GitHub sends the owner’s browser to that address after installation, where no server is listening. [GitHub: setup URLs](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/about-the-setup-url)  
    Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)

23. Advisory: The quota cache mixes the personal and app budgets.

    Raise: Functional  
    Case: normal use - Close falls back to the personal sign-in, then another close uses the app within a minute.  
    [The plan](/plans/FORGE-GHAPP-1.md:71) assumes the existing quota read follows the app token, but [the cache](/src/forge/github.py:18) is shared per repo and does not record the identity. A fresh cache can therefore admit or delay app check waits using the personal budget.  
    Adds work: separate cached quotas by identity; F 2 x H 2 = 4; 2 x C = 4  
    Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)

24. Advisory: Doctor’s personal-account warning links to organization settings.

    Raise: Functional  
    Case: normal use - A developer installs their private app on all repos in their personal account.  
    [The warning](/plans/FORGE-GHAPP-1.md:96) always links to `/organizations/<owner>/settings/installations`, including when the owner is a user. GitHub puts personal-account installations under personal settings. [GitHub: modifying installed apps](https://docs.github.com/en/apps/using-github-apps/reviewing-and-modifying-installed-github-apps)  
    Gain 3, Work 1, Harm 2
   Disposition: keep - below the bar (follow-up)

25. Advisory: A limited gh credential can make doctor accuse the user of lacking access.

    Raise: Functional  
    Case: normal use - A developer uses a fine-grained gh token limited to the current repo, while their account can open another selected repo in the browser.  
    [The warning](/plans/FORGE-GHAPP-1.md:96) treats a null result from the token as proof that the developer cannot open the repo. GitHub permits a personal token to cover fewer repositories than its owner can access. [GitHub: fine-grained tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)  
    Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)

26. Advisory: Looking through saved apps exceeds the stated per-run request cost.

    Raise: Scale  
    Case: normal use - A consultant has saved apps for ten client organizations and starts close in the last one checked.  
    [The lookup](/plans/FORGE-GHAPP-1.md:90) makes an installation request for each saved app before making a token, although the [cost statement](/plans/FORGE-GHAPP-1.md:15) says two requests per run. The saved records already contain the owner.  
    Adds work: select saved apps for the repo owner before lookup; F 2 x H 2 = 4; 2 x C = 4  
    Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)

## Round 2

27. Blocking: Disputed keep 16: app selection waits for the exhausted personal budget.

   Raise: Not done  
   Case: normal use - Agents exhaust the developer’s GitHub budget before the developer starts merge.  
   The revised [plan](/plans/FORGE-GHAPP-1.md:86) reads the active login with the personal sign-in before selecting the app. [That read](/src/forge/task.py:323) goes through [GitHub’s rate-limit wait](/src/forge/github.py:109), so Forge waits for the personal budget to reset before it can use the app’s separate budget. This is the main failure the story is meant to remove.  
   Gain 5, Work 3, Harm 3

28. Blocking: The Windows key folder can inherit access for other users.

   Raise: Security  
   Case: normal use - A Windows developer uses a shared local folder for `LOCALAPPDATA` and Python 3.11.9.  
   [The plan](/plans/FORGE-GHAPP-1.md:88) relies on modes `0700` and `0600`, but this [supported Python version](/pyproject.toml:9) does not apply Windows access controls for `0700`; that support began in 3.11.10. The key can inherit the shared folder’s permissions, letting another account read it. [Python](https://docs.python.org/3.11/library/os.html#os.mkdir), [Microsoft](https://learn.microsoft.com/en-us/windows/win32/fileio/file-security-and-access-rights)  
   Gain 5, Work 3, Harm 4

29. Blocking: Disputed keep 12: the new refusal link is left behind by automatic submission.

   Raise: Functional  
   Case: normal use - An organization member without the App Manager role is refused by GitHub.  
   [The new page](/plans/FORGE-GHAPP-1.md:100) submits to GitHub as soon as it loads, taking the developer away from its `/refused` link. The plan gives no instruction to return to that page, so the intended immediate refusal can still take 15 minutes. The [test](/plans/FORGE-GHAPP-1.md:111) calls the link directly and would pass with this browser flow broken.  
   Gain 4, Work 2, Harm 3

30. Blocking: Disputed keep 20: the new refusal interaction still skips the functional check.

   Raise: Gate  
   Case: normal use - A developer needs to use the new refusal link during setup.  
   The revised [plan](/plans/FORGE-GHAPP-1.md:100) adds an interactive local page, but again says [Design: none](/plans/FORGE-GHAPP-1.md:17) and marks [SETUP user-facing: no](/plans/FORGE-GHAPP-1.md:126), contrary to the stated disposition. [Review](/src/forge/review.py:325) therefore omits the functional check for this new interaction.  
   Gain 4, Work 2, Harm 2

31. Advisory: Disputed keep 23: personal pull-request calls consult the app’s quota after a rate-limit error.

   Raise: Functional  
   Case: normal use - The personal budget runs out while Forge creates a pull request, but the app still has requests left.  
   [The plan](/plans/FORGE-GHAPP-1.md:92) exempts pull-request creation from the app token but applies the token to the separate quota read. [The wait](/src/forge/github.py:119) then sees the app’s available budget and retries the rate-limited personal call every minute, even after the cache expires.  
   Adds work: select the quota for the identity that made the failed call; F 2 x H 2 = 4; 2 x C = 4  
   Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)

32. Advisory: Doctor gives one reset time for two separate budgets.

   Raise: Functional  
   Case: normal use - The REST and GraphQL budgets reset at different times.  
   [The planned line](/plans/FORGE-GHAPP-1.md:94) reports both balances followed by one reset time, although GitHub returns a separate reset for each budget. A developer checking when requests will resume can be given the wrong time. [GitHub: rate-limit response](https://docs.github.com/en/rest/rate-limit/rate-limit)  
   Adds work: report each budget’s reset separately; F 2 x H 1 = 2; 2 x C = 2  
   Gain 2, Work 1, Harm 1
   Disposition: keep - below the bar (live with)
