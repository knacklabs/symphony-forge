# Specs

One file per capability: what it does and how we know it works, never how it is built.

1. `forge spec save <slug>` saves a draft.
2. `forge read <slug>` gives it one cold read.
3. `forge spec confirm <slug> --by "<name>"` marks it confirmed after the human confirms it.
4. `forge roadmap add <slug>` adds its stories to `plans/roadmap.json`.
