# Plan-contract review brief — ROLE2-T1

For each contract, emit a verdict — implemented | partial | missing — with file:line evidence, recorded as contract_verdicts in the quality artifact. Then review the diff normally; the contract check does not replace the quality/performance/security lenses.

## Task ROLE2-T1

### Plan contracts

- **ROLE2-C1**
  - Source: plans/active/FORGE-ROLE-2-read-only-rescue-accepts-long-prompts-via-prompt-file.md#technical-approach
  - Statement: The guard admits --prompt-file in the read-only lane only on the task verb, with exactly one value naming a repo-relative existing regular file whose resolved path is contained under the resolved repo root.
- **ROLE2-C2**
  - Source: plans/active/FORGE-ROLE-2-read-only-rescue-accepts-long-prompts-via-prompt-file.md#acceptance-criteria
  - Statement: Absolute, traversal, dangling, directory, externally-resolving-symlink, duplicate-value, and wrong-verb prompt-file shapes are refused, and every pre-existing refusal (shell syntax, wrappers, write flags, --cwd, unknown flags) behaves exactly as before.
- **ROLE2-C3**
  - Source: plans/active/FORGE-ROLE-2-read-only-rescue-accepts-long-prompts-via-prompt-file.md#technical-approach
  - Statement: The guard test matrix covers the admission and each containment refusal at the three named test sites, with the laundering/wrapper/expansion regression tests left unmodified.
- **ROLE2-C4**
  - Source: plans/active/FORGE-ROLE-2-read-only-rescue-accepts-long-prompts-via-prompt-file.md#verify-plan
  - Statement: A multi-paragraph brief reaches Codex through the read-only file route in a live end-to-end run, and the same invocation with a traversal path is refused live.

### Reviewer focus

This loosens a security guard: verify the admission is task-verb-scoped and value-validated with BOTH sides resolved before containment comparison; verify no other refusal got quieter or reordered; verify the containment matrix actually exercises an external symlink and a dangling path, not just lexical traversal; regressions must be diff-untouched.
