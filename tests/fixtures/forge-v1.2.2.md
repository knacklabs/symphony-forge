# Previous-release adoption fixture

`forge-v1.2.2/` contains only the ordinary text files needed to run that
release's real adoption command: its imported modules, generated-file owners,
adapter template, Forge skill, standards, and supporting skill files.
Their contents are unmodified from release v1.2.2, commit
`5ccbbecf22ff7fba28fea17e65191b3bb91c8d18` (annotated tag object
`3febf07f414725bdb5028830655f1c83368b5ec0`).

The fixture's `src/forge/cli-py.txt` is the old CLI source. The test copies the
folder and renames that file to `cli.py` before running it; the fixture is test
data rather than a change to Forge's CLI. No source content is rewritten.
Unused commands, the Codex turn runner, board HTML, prototype skeleton,
conventions, review and worker templates, and duplicate generated skills are
omitted. Command discovery imports the remaining modules and their dependencies;
adoption reads the remaining templates and skills.

The merge-rule regression runs that release's real init command to adopt a client,
then upgrades it through current sync or doctor. In particular, doctor runs without
preparatory sync, leaving the previous release's roadmap-only tracked attributes
and checkout-bound driver in place until the repair. Keeping the release in this
text fixture makes the test independent of tags and history in CI's shallow clones
and readable by the review tool.
