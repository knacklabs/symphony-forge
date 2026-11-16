# Can a plug-in raise the effort of a continued Claude subagent?

Answer: Yes, it looks like it. A `turn.step` hook can raise effort for a continued subagent. Claude Code accepts the change for both the first request and the continued request. The proof is indirect, because Claude Code does not record the effort it sent.

## What I ran

Claude Code 2.1.325, model haiku (claude-haiku-5-5), real runs, `claude -p`. I used the real home folder for sign-in, so the isolated home of `tests/test_pane_session.py` did not apply. The main agent started one subagent at effort low, then continued it once with SendMessage. Four runs: a baseline (no change) and a raise run, for two tiny tasks.

```
claude -p "<prompt>" --model haiku --plugin-dir <mod> --output-format json --max-turns 8
```

The mod logs each request's `agentId`, `effort` and `messageCount`. A marker file turns the raise on, so the same mod serves both runs.

## Numbers

Effort the hook saw on each subagent request, and what it sent on:

| Run | Request | Messages | Hook saw | Sent on |
|---|---|---|---|---|
| baseline | first | 14 | low | low |
| baseline | after continue | 23 | low | low |
| raise | first | 14 | low | high |
| raise | after continue | 23 | low | high |

The hook saw `low` on the continued request too. So a continue keeps the spawn effort, as the docs say. The hook can change it on each request.

Output tokens of the subagent (the thinking text is hidden in the transcript, so I use output tokens):

| Task | Run | First request | After continue |
|---|---|---|---|
| say "one" / "two" | baseline | 118 | 118 |
| say "one" / "two" | raise | 121 | 243 |
| count primes below 150 / 300 | baseline | 200 | 145 |
| count primes below 150 / 300 | raise | 224 | 317 |

After the continue, the raise runs wrote about twice as many tokens (243 vs 118, 317 vs 145). The first request changed little (121 vs 118, 224 vs 200). Each cell is one sample, so this is a hint and not a measurement.

## Limits

- The debug log (`--debug-file`) and the transcript have no effort field. I could not see what the API received. The token counts are the only outside sign.
- `TurnStepResult` has no effort. The response shows nothing about it.
- A rewrite does not carry to later steps. On a model that takes effort per message, a new level on a step whose input is only tool results is not sent. A level on a step with new input (a continue message) is sent. The hook must raise on every request of the subagent.
- Effort may be capped by the model or by `maxEffortLevel`. A model with no effort setting is sent none. I only tested haiku.
- The hook needs to find the right subagent. `agentId` is new for each spawn, so the hook cannot know it in advance. A marker file or the spawn prompt would have to name it.
- A mod loads only in an interactive session or with `--plugin-dir`. Forge's SDK workers would need the plug-in loaded.

## What Forge could do next

- Try the same test with the real builder model (Sonnet 5.5) and compare thinking tokens on a harder task.
- If it holds, add a small mod that raises effort for a subagent when Forge writes a marker file before a repair round.
- Otherwise start a new subagent with `effort` set in the Agent call, which is documented.

## The throwaway mod (not shipped)

Files: `.claude-plugin/plugin.json`, `hooks/hooks.json` (`{ "modules": ["./register.ts"] }`), and `hooks/register.ts`:

```ts
import type { Register } from 'claude-code'

const DIR = '/private/tmp/claude-501/-Users-ravikiranvemula-Workdir-symphony-forge/c01a489d-c76f-41c1-8371-d6f0052b027c/scratchpad/probe'
const lines: string[] = []

export const register: Register = on => {
  on('turn.step', async function* ($, e, next) {
    const raise = await $.fs.exists(`${DIR}/raise`)
    const doRaise = raise && e.agentId !== undefined
    const sent = doRaise ? { ...e, effort: 'high' as const } : e
    const r = yield* next(sent)
    lines.push(JSON.stringify({
      agent: e.agentId ?? 'main', index: e.index, model: e.model, msgs: e.messageCount,
      effortIn: e.effort ?? null, raised: doRaise, effortSent: sent.effort ?? null,
      resultKeys: Object.keys(r), resultEffort: (r as { effort?: unknown }).effort ?? null,
    }))
    await $.fs.write(`${DIR}/steps.jsonl`, lines.join('\n') + '\n')
    return r
  })
}
```
