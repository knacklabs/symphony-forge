# Specs

One file per capability: what it does and how we know it works, never how it is built.

1. `forge spec save <slug>` saves a draft.
2. `forge read <slug>` gives it one cold read.
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
