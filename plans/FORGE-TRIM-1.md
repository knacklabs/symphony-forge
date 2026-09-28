# Forge sheds dead and duplicated code before it grows again

## What changes for you

- Forge gets smaller without losing anything you use: the stories waiting on its size limit (agent
  merge, one-chat approval) can land.
- Nothing changes in the files `forge sync` writes into your repos, however Forge was installed.
- In Forge's own repo, `forge migrate` now refuses at once: that repo already moved.
- The migration guide lives under `docs/`, and the Forge skill points to the standards page instead
  of repeating it.

## Why

`src/forge` is at 7,961 lines against its 8,000-line ceiling, the check behind Forge's rule that it
shrinks over time. Two read-only audits found what it carries for nothing. This story builds the
confirmed spec `docs/specs/forge-trim.md`.

## Done when

1. `docs/specs/forge-trim.md` is confirmed by the owner and on the roadmap as FORGE-TRIM-1.
2. The test-audit skill, the FDE guidance and the Remote Control skill each have one source copy:
   the package copies under `src/forge/templates/` are gone, and the build bundles the copies
   `forge sync` already writes into this repo at the same package paths; a wheel, a source
   distribution and an editable install each give `forge sync` the same test-audit, FDE and Remote
   Control files as before, byte for byte.
3. In Forge's own repo `forge migrate` refuses before any change, saying the repo moved at the
   switch; the own-repo mode and its tests are gone; a copied-in client migrates as before; the v1
   spec says why.
4. The migration skill text is at `docs/migrate-skill.md`, and the test that reads it follows it.
5. `forge sync` writes the standards page next to the Forge skill for both hosts, and the skill's
   "Build simple" section is a short pointer to it plus its "Finding forms" lines.
6. `src/forge` stays at or under the 8,000-line ceiling by the ceiling test's count, the ceiling stays at 8,000,
   no change joins lines or removes blank lines to save lines, and the full test suite passes.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| SRC-FORGE-IS-AT-ITS-8-000-LINE-CEILING-S | The spec | The confirmed spec and its roadmap item | 1 | `docs/specs/forge-trim.md`, `docs/specs/forge-trim.read.md`, `plans/roadmap.json` | | none | no |
| SKILLS | One source copy | The three package copies removed, the build's forced inclusion of this repo's synced copies at the same package paths, and `sync`'s source lookup for a built package and an editable checkout, with one test that crosses sync and the source lookup | 2 | `pyproject.toml`, `src/forge/templates/skills/`, `src/forge/templates/fde.md`, `src/forge/sync.py`, `tests/test_rules.py` | `tests/test_trim_skills.py` | none | no |
| PACKAGING | Same files from every install | Byte-for-byte checks that a wheel, a source distribution and an editable install give `forge sync` the same test-audit, FDE and Remote Control files as before | 2 | `tests/test_trim_packaging.py`, `tests/test_trim_skills.py` | `tests/test_trim_skills.py` | SKILLS | no |
| MIGRATE | No own-repo migrate | The own-repo mode and its tests removed, the refusal in Forge's own repo, and the v1 spec's passages | 3 | `src/forge/migrate.py`, `tests/test_migrate.py`, `docs/specs/lean-forge-v1.md` | `tests/test_trim_migrate.py` | none | yes |
| GUIDE | The migration guide in docs | The migration skill text moved to `docs/` and its reader test following it | 4 | `src/forge/templates/migrate-skill.md`, `docs/migrate-skill.md`, `tests/test_fix_after_forge_migrate_old_forge_leftovers.py` | `tests/test_trim_guide.py` | none | no |
| STANDARDS | Point to the standards | The standards page synced next to the Forge skill, the "Build simple" pointer, the generated copies, and the size check once every other task has merged | 5, 6 | `src/forge/templates/skill.md`, `src/forge/sync.py`, `.claude/skills/forge/`, `.codex/skills/forge/`, `tests/test_setup.py` | `tests/test_trim_standards.py` | SKILLS, PACKAGING, MIGRATE, GUIDE | yes |

New moving parts: none

## Risks

- The v1 spec is confirmed; MIGRATE edits its body, so its stored confirmation no longer matches
  until it is saved and confirmed again in a fix, which only matters before a `forge spec measure`
  on it.

## Notes

- SKILLS keeps every package path `forge sync` reads (`templates/skills/test-audit/`,
  `templates/fde.md`, `templates/skills/remote-approval/SKILL.md`) working in a built package via
  the build's forced inclusion from `.codex/skills/test-audit/`, `.codex/skills/forge/fde.md` and
  `.claude/skills/remote-approval/SKILL.md`; for an editable install `sync` reads the checked-in
  copies directly.
- MIGRATE's refusal fires on `repo = "forge-source"` before any planning; the client path is
  untouched.
- SKILLS pins `sync`'s file list and its source lookup before STANDARDS adds the standards page to
  it. STANDARDS goes last because it shares `sync.py` with SKILLS and counts the whole result for
  item 6, which needs every other task merged.
- Done-when 2's byte-for-byte promise covers only the test-audit, FDE and Remote Control files;
  STANDARDS changes the Forge skill and adds the standards page on purpose (item 5).
- Each test file starts with `STORY = "FORGE-TRIM-1"`, and its `test_<n>_` names cite the Done-when
  items its task covers.
