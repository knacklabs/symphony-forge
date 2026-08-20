# Task Plan: upgrade-doc-contract-safety

Story: `upgrade-preserves-doc-contracts` · Plan: `plans/active/upgrade-preserves-doc-contracts-upgrade-preserves-and-truthfully-reports-doc-contract-overwrites.md`

## Objective

`cmd_upgrade` detects and truthfully reports doc-contract overwrites: it names
each replaced contract, qualifies the "Untouched (project-owned)" dirs, and warns
when a client's contract file differs from the new template (pointing at `git
diff`). No backup file is written — a clean tree is required, so git holds the
prior content.

## Changes

### `factory/scripts/forge_cli/upgrade.py`

1. **DOC_CONTRACTS loop** (currently ~527-533): before each `copy2(src, dst)`,
   collect `replaced_contracts.append(dst_rel)`, and when `dst.is_file() and not
   dst.is_symlink()` and `dst.read_bytes() != src.read_bytes()`, collect
   `diverged_contracts.append(dst_rel)`. The `is_file()/not is_symlink()` guard
   precedes `read_bytes()` (a symlink read would escape the target —
   `repository-escape` recurring class, decision 0028). No write is added.
2. **Report** (currently ~712-717):
   - Drop `", doc contracts"` from the generic "Replaced" line; print
     `Replaced doc contracts: <sorted replaced_contracts>`.
   - Append to the "Untouched (project-owned)" line a qualifier, e.g.
     `(doc-contract files in these dirs are harness-owned — see "Replaced doc
     contracts" above)`, so a replaced contract's dir is not presented as
     untouched.
   - If `diverged_contracts`: print a `WARNING:` naming each and directing the
     operator to `git diff <path>` before committing (prior content is in git;
     move project-specific content to a project-owned sibling file).

### `factory/tests/test_gates.py`

Add `test_upgrade_names_diverged_doc_contracts_and_writes_no_backup`: build a
`tmp_path` client (a real dir, never monkeypatching `os.name`) with two doc
contracts — one whose README differs from the harness template (appended project
content) and one byte-identical to it; run the upgrade path; capture the report;
assert:
- both contracts appear under "Replaced doc contracts";
- the "Untouched (project-owned)" line no longer presents a replaced contract's
  directory as unqualified untouched (AC1b);
- the divergence WARNING names the edited contract and not the identical one;
- no `.orig` file exists anywhere under the client.

## Verification

- `python3 -m pytest factory/tests/test_gates.py::test_upgrade_names_diverged_doc_contracts_and_writes_no_backup -q`
- `python3 factory/scripts/verify.py`
- `python3 factory/scripts/check_dual_runtime.py`

## Out of scope

`.orig`/backup files, marked-block merge, agent reconciliation, and any change to
the `DOC_CONTRACTS` set (all rejected in the requirements/plan grills).
