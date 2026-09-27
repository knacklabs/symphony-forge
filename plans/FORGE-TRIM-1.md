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
2. The test-audit skill, the FDE guidance and the Remote Control skill each have one checked-in
   copy, bundled at their package paths by the build; a wheel, a source distribution and an
   editable install each give `forge sync` the same files as before, byte for byte.
3. In Forge's own repo `forge migrate` refuses before any change, saying the repo moved at the
   switch; the own-repo mode and its tests are gone; a copied-in client migrates as before; the v1
   spec says why.
4. The migration skill text is at `docs/migrate-skill.md`, and the test that reads it follows it.
5. `forge sync` writes the standards page next to the Forge skill for both hosts, and the skill's
   "Build simple" section is a short pointer to it plus its "Finding forms" lines.
6. `src/forge` counts at most 7,561 lines by the ceiling test's count, the ceiling stays at 8,000,
   no change joins lines or removes blank lines to save lines, and the full test suite passes.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| SRC-FORGE-IS-AT-ITS-8-000-LINE-CEILING-S | The spec | The confirmed spec and its roadmap item | 1 | `docs/specs/forge-trim.md`, `docs/specs/forge-trim.read.md`, `plans/roadmap.json` | | none | no |
| SKILLS | One copy of each skill | The package copies of the three skill texts removed, the build bundling the checked-in copies at the same package paths, and a check of wheel, source and editable installs | 2 | `pyproject.toml`, `src/forge/templates/skills/`, `src/forge/templates/fde.md`, `src/forge/sync.py` | `tests/test_trim_skills.py` | none | no |
| MIGRATE | No own-repo migrate | The own-repo mode removed, the refusal in Forge's own repo, the v1 spec's passages, and the migration skill text moved to `docs/` | 3, 4 | `src/forge/migrate.py`, `tests/test_migrate.py`, `docs/specs/lean-forge-v1.md`, `src/forge/templates/migrate-skill.md`, `docs/migrate-skill.md`, `tests/test_fix_after_forge_migrate_old_forge_leftovers.py` | `tests/test_trim_migrate.py` | none | yes |
| STANDARDS | Point to the standards | The standards page synced next to the Forge skill, the "Build simple" pointer, the generated copies, and the size check | 5, 6 | `src/forge/templates/skill.md`, `src/forge/sync.py`, `.claude/skills/forge/`, `.codex/skills/forge/`, `tests/test_setup.py` | `tests/test_trim_standards.py` | SKILLS, MIGRATE | yes |

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
- STANDARDS goes last because it shares `sync.py` with SKILLS and counts the result for item 6.
- Each test file starts with `STORY = "FORGE-TRIM-1"`, and its `test_<n>_` names cite the Done-when
  items its task covers.
