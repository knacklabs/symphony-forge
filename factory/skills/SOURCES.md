# Vendored skills

`grilling/` and `ponytail/` are copied verbatim from Matt Pocock's skills pack
(https://github.com/mattpocock/skills). They ship with the harness so every
clone, runner and worker gets the same text: the launcher loads `ponytail`
into every write launch, and `forge grill run` inlines `grilling`. Neither
depends on a per-machine install.

Refresh: `npx -y skills add mattpocock/skills -g --copy --all`, then copy
`~/.claude/skills/<name>/SKILL.md` over the file here.
