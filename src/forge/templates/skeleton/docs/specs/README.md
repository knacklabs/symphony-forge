# Specs

One file per capability: what it does and how we know it works, never how it is built.

1. `forge spec save <slug>` saves a draft.
2. `forge read <slug>` gives it a cold read; answer blocking findings and run it again until no
   notes block building. Advisory notes are recorded and do not need another round.
3. `forge spec confirm <slug> --by "<name>"` marks it confirmed after the human confirms it.
4. `forge roadmap add <slug>` adds its stories to `plans/roadmap.json`.
5. Once every story from it is done and its check date has passed, `forge next` asks for the
   check: measure, then `forge spec measure <slug> --result "<text>"` records the result.

Every spec says how success will be measured, or save and confirm refuse it:

```markdown
## Success measure

- Metric: what you will count.
- Baseline: what it is today.
- Target: what it should become.
- Check date: YYYY-MM-DD
```

A field may wrap onto indented lines.

State each rule once, on one line with an ID, under `## Behaviour`. Validation (VAL), UAT and
acceptance (AC) lines name the rule that they check by its ID and say how it is checked. They
do not say the rule again:

```markdown
## Behaviour

- R-1: An invoice goes out by email when it is issued.

## Acceptance criteria

- AC-1 checks R-1: issue a test invoice; the client's inbox has it within a minute.
```

A decision that changes a rule names its ID. `forge decision accept` then lists every spec
line that names that ID, so you update them in the same change.
