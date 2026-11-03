---
name: agents
description: "Agent rules for Forge client apps with a chat agent or in-app assistant. Use before any agent, chat, voice or in-app assistant work: its shape, turn, memory, tools, output, safety, cost and tests."
---

# Agents

These rules apply to a chat agent that a signed-in person uses in the app's own web chat, with optional speech in that same chat (speech to text in, text to speech out). WhatsApp and phone calls are not covered.
They apply to the agent work that a change adds or changes. Never migrate existing agent code to these rules unless a story asks.
Each rule is Must or Should. A review reports a broken Must as a P1 finding and a broken Should as advice. Each rule has a starting default you can tune. Where the app's constitution differs, it wins.
Infrastructure is written for AWS with Postgres as the only moving part: queues, timers, events and memory all live in Postgres tables, with no SQS, SNS or EventBridge. Lines marked LangGraph say how to do it with LangGraph and where it does not do it for you.

## One message, end to end

The chat request is checked against the signed-in session and acknowledged at once; the message goes on the user's ordered queue.
One worker per user takes it. One fast classifier call answers the yes or no questions (safety, controls, does this refer to something earlier, is this image safe), while the profile loads.
Only a yes to "refers to earlier" starts a memory search, and the search gets a short wait. If it misses the wait, the turn goes ahead without it.
The model runs with a fixed prompt order. Before each model call and each action, new messages from the user are folded in.
Code checks the reply, then one reply path delivers it with an idempotency key.
After the turn: cost is logged, the trace is written, and the context size is checked against the summary threshold.

## Agent shape before any code

### Start with the simplest thing that works

**Must.** One model call with good retrieval and examples is often enough. Where the steps are known (change a booking, process a refund), write a workflow: fixed code paths with model calls inside. Use a free agent loop only where the number of steps cannot be known in advance. Add complexity only when a test shows it helps.

Default: workflows for known flows; an agent loop for open conversation; both behind the same turn handler.

### Route by difficulty

**Should.** Classify the turn first and send easy, common requests to a small fast model, and only hard ones to a larger model.

Default: one small model for most turns and every background job; a larger model only for named hard cases.

### Ground truth at every step, a stop, and a human

**Must.** Each step checks the real result of the last one (the tool's answer, the booking system's state), not what the model expected. Every loop has a stopping condition, and the agent hands off to a person when it is stuck rather than looping.

Default: step limit per turn; a hand-off after two failed attempts at the same goal.

### Know what your framework sends

**Must.** If you use a framework, read how it builds the prompt, retries and stores state. Most cache, cost and memory bugs come from defaults nobody looked at.

Default: log the exact request sent to the model for a sample of turns in dev.

LangGraph: check what your model node sends each turn and what each node returns into state; both decide cache hits and history size.

## The turn

### Acknowledge fast, then process in order per user

**Must.** Answer the chat request within a second and do the work after. Put each user's messages on one ordered lane so two messages from the same person never run at the same time.

Default: an inbox table in Postgres; the chat endpoint inserts and returns in under 1 s ; workers claim the next row with FOR UPDATE SKIP LOCKED and hold pg_advisory_xact_lock on the user id, so one user's messages never run at once; NOTIFY wakes a worker instead of polling hard.

LangGraph: one thread_id per user conversation. Open-source LangGraph does not stop two runs on the same thread; the per-user advisory lock on the inbox must, so only one run per thread is ever in flight.

### Steering: new messages join the running turn

**Must.** People send three short messages instead of one. Before every model call, and before any action that changes something, check for messages that arrived during the turn and fold them in, then restart the step. Never merge after a reply has gone out, and never merge button taps, opt-outs or delete requests: those run on their own.

Default: check before each model call and each write action; at most 2 restarts per turn. No fixed "wait for more messages" timer.

LangGraph: not built in. In the model node, read this user's unclaimed inbox rows and add them to state before calling the model; check again in the tool node before a write. Because the advisory lock keeps the next message waiting while a run is in flight, the run itself must look at the inbox; nothing in LangGraph does it for you.

### A speed target, and a holding line only before slow work

**Must.** Set a first-reply target and measure it on every turn. Send a short "one moment" only when slow work starts (a search, a booking call), never as a habit.

Default: chat first message within 7 s for 95% of turns; holding line after 2 s of slow work.

### Show that you are working

**Should.** Show typing while the turn runs, and stream the reply as it is written.

Default: typing indicator for the length of the turn; token streaming.

### Fail once quietly, then honestly

**Must.** Retry a failed turn once without telling the user. If it fails again, send one honest line and log it. Bound the model steps and the provider wait so a turn can never hang.

Default: provider timeout 20 s , 1 retry, 6 model steps per turn.

LangGraph: set recursion_limit in the run config well below the default 25; add a RetryPolicy on the model node; catch the final error outside the graph and send the honest line.

## Fast decisions before the model

### One classifier call answers every yes or no question

**Must.** Before the main model runs, a small, fast classifier with a fixed output schema reads the incoming message and answers the questions you choose. One call answers all of them, so adding a question costs almost nothing. It replaces keyword lists, which break on the first typo, slang word or second language.

Default: a structured-decision endpoint such as OpenAI's Decisions API, or any small model with a fixed schema; about 120 ms median; 1.5 s timeout; keyword lists only as the fallback when it times out. Set each question's threshold on your own labelled examples.

LangGraph: call it before invoking the graph, outside the graph's steps, and pass the verdicts in the run context so every node can read them.

### Whether to search memory

**Must.** Ask "does this message point to something said before this conversation?" ("same hotel as last time", "the issue I reported", "my usual order"). Only a yes starts a memory search, so most turns pay nothing for memory. If the classifier times out, run the search anyway but use only strong matches, where every search word is found: a weak guess is worse than no memory.

Default: question refers_to_earlier ; search on yes only; on timeout, strong matches only.

### Every image, before the main model sees it

**Must.** Check each incoming image for unsafe or explicit content, for text in the image that tries to give the agent instructions, and for sensitive documents (ID cards, bank or card details, boarding passes). A refused image never reaches the main model and is not stored; a sensitive one gets a line asking the user not to share it here.

Default: the image goes to the classifier with three questions (unsafe, instructions inside, sensitive document); kept only as long as the privacy notice says.

### Files and documents, before they are read

**Must.** PDFs and other files are checked for instructions aimed at the agent before any text from them reaches the main model, and that text is always passed as data, never as instructions.

Default: size and page limits first, then the injection question on the extracted text.

### Controls and hand-offs

**Must.** Wants a human, opt-out, delete request, complaint or report. Code acts on these before the model runs. The exact words (STOP, DELETE) act at once; looser phrasing the classifier flags gets one confirm step.

Default: questions wants_human , opt_out , delete_request , complaint .

### Risk, scope, age and language

**Must.** Risk to the user (self-harm, abuse, danger) sends them to real help. A request outside the agent's job gets one friendly redirect. Under-age users follow your policy. The detected language sets the reply language.

Default: questions risk , out_of_scope , under_age , language ; crisis lines only on clear risk, never for a bad day.

### Background checks in one batch

**Should.** When a job checks many items (incoming reviews, applicants, tickets), send one batched classifier call instead of one model call per item.

Default: one batch per job run; log each verdict with its score for calibration.

## Context and the prompt cache

### Fixed prompt order, append-only messages

**Must.** Tools, then the system prompt, then the user's profile and conversation summary, then the messages since the summary, then the current turn. Never use a sliding window: changing the start of the prompt throws the cache away and every reply pays full price.

Default: cache breakpoints after the system prompt, after the profile block and at the end of the previous turn.

LangGraph: build the model input yourself in the model node: system prompt, then the summary from state, then the messages. Do not use trim_messages on every turn: it is a sliding window and breaks the cache. Remove messages only at compaction.

### Summarise and extract memory in parallel near the limit

**Must.** When the conversation reaches a set share of the context budget, start two jobs at once: the conversation summary and memory extraction (the note writer). When the summary finishes, start a new conversation made of the summary plus the messages it does not cover. The user keeps chatting while the jobs run.

Default: trigger at 80% of the context budget, never 100%, so the summary call itself fits; summary capped at about 1,200 tokens.

LangGraph: LangMem's SummarizationNode ( max_tokens_before_summary ) runs inside the turn, so the user waits. To keep the user chatting, run the summary and the memory writer as a separate background run that fans out to both, then apply the result to the thread with graph.update_state : the new summary plus RemoveMessage for every covered message. Keep tool calls and their results together when you cut.

### Do the same before the cache expires

**Must.** Provider caches last minutes to an hour. While the cache is warm, keep the conversation as it is. When the user has gone quiet and the cache is about to expire, run the same summary and memory jobs, so the next message starts on a short, fresh prompt instead of paying full price for a long one.

Default: idle timer set just under the cache lifetime, for example 55 min for a 1 h cache; never compact while the cache is warm and the user is active.

LangGraph: no idle trigger. Keep one row per thread in a Postgres timers table with run_at moved forward on every message; a worker claims due rows with SKIP LOCKED and starts the same background summary run.

### A hard ceiling that loses nothing

**Must.** If a single turn would pass the ceiling before the summary lands, save the turn durably and resume it once the summary is published. Never drop messages to make room.

Default: leave the inbox row unclaimed with state 'waiting' and resume it after the summary is published.

LangGraph: a Postgres checkpointer ( PostgresSaver , call setup() once) already saves every step; leave the incoming message in the inbox until the summary is applied, then run the turn.

### Turn-only context goes last and is never stored

**Must.** Recalled memories and other blocks for this reply go after the conversation, and are removed before the turn is saved, so the cached prefix never changes.

Default: one short block, a few hundred bytes, labelled "for this reply only".

LangGraph: add the block to the model call's input inside the node and do not return it in state; anything returned in messages is checkpointed and becomes history.

## Memory: writing

### One fact per note, typed and sourced

**Must.** Each note is one plain fact with a kind (fact, preference, dislike, plan), whether the user stated it or the model inferred it, the message it came from and when it was saved. Values you filter on (budget, plan tier, home city) go in columns, not notes.

Default: one row per note in Postgres : id, user_id, kind, subject, body, source, source_message_id, saved_at, expires_at, replaces.

LangGraph: the Store ( PostgresStore ) keeps notes as JSON under a namespace such as (user_id, "notes") with put(namespace, key, value) ; put the fields above in value . Notes outlive the thread; checkpoints do not.

### Stated beats inferred; newest stated wins

**Must.** An inferred note never replaces a stated one. A new stated fact replaces the old one instead of sitting beside it. A correction ("that's wrong, I don't like hostels") removes what it contradicts in the same turn.

Default: conflicts checked by subject; the replaced note kept for audit, never searched.

### Four save moments, one set of rules

**Must.** Near the context limit, before the cache expires, after the user goes quiet, and a nightly pass for everyone active that day. Every save uses the same note writer and the same rules, so a note looks the same whichever moment wrote it. Watch the nightly pass: log how many users it covered and alert on any it skipped.

Default: nightly pass started by pg_cron (or a due row in the timers table) using the provider's batch API; idle save after about 30 min of quiet.

### "Remember this" and "forget that" act at once

**Must.** An explicit save is written in the same turn. A forget removes the note from the table and the search index before the next reply.

Default: both run inside the turn, not on the nightly job.

LangGraph: a save tool calls store.put ; a forget tool calls store.delete(namespace, key) , and also removes the row from any search index you keep beside the Store.

### Never saved, and kept only as long as you promised

**Must.** No passwords, card numbers, one-time codes, health details the user did not ask you to keep, or details about other people beyond a first name. Keep notes exactly as long as your privacy notice says.

Default: code refuses those fields before saving and gives the writer the reason and one retry; expiry set from the notice.

## Memory: recall

### Exact search inside one user

**Must.** Search words come from the user's message; the user filter sits inside the query; aliases ("laptop" also searches "notebook") are added to the query only; rank by match, then recency, then stated before inferred; return a few short hits.

Default: Postgres full-text search (tsvector with a GIN index); top 3 hits, about 600 bytes. Add embeddings only for long documents or cross-user matching.

LangGraph: store.search(namespace, query=...) is semantic search and needs an embedding index ; filter= matches fields exactly. For exact keyword recall, query a Postgres full-text column yourself, still scoped to the user's namespace.

### Memory has a wait budget and never delays a reply

**Must.** Start recall the moment the message arrives, in parallel with everything else. Give it a short fixed wait. If it is not ready, the turn goes ahead without memory, and the result is added to the next message's turn if it still applies.

Default: wait 80 ms ; a late result is held on the user's session and injected once into the next turn, then dropped.

LangGraph: parallel branches join before the next step, so a slow recall branch delays the model. Start recall as a task before invoking the graph, wait with asyncio.wait({task}, timeout=0.08) (not wait_for, which cancels the lookup when the wait ends and so loses the late result), pass the result in the run context, and write a late result to a pending_memory state key the next turn reads once.

### Label what was found; ask instead of guessing

**Must.** One clear match: use it. Two or more: name them and ask which ("the March booking or the June one?"). None: ask for the detail.

Default: labels agreed, ambiguous and ask, written by code into the turn block.

## Tool design

### One tool per job, not one per API call

**Must.** Build a few tools around what the user is trying to get done, and put the API calls behind them. "Find a slot and book it" is one tool that calls availability, hold and confirm, not three tools the model has to chain. Fewer tools mean fewer wrong picks. Group related actions into one tool with an action parameter, and prefix names by area when you have many.

Default: about 5 to 15 tools per agent; names like bookings_search , bookings_change ; a targeted search tool instead of a "list everything" tool.

### Descriptions written for a new hire

**Must.** Each description says what the tool does, when to use it and when not to, what every parameter means, and what it does not return. Parameter names leave no doubt ( booking_reference , not ref ). For tools with nested or format-sensitive inputs, add a few worked examples.

Default: at least 3 to 4 sentences per tool description; input_examples for complex inputs; the boundary between two similar tools written in both descriptions.

### Strict schemas in and out

**Must.** Turn on strict tool input so calls always match the schema, and validate every tool result against its own schema before the model sees it. Make mistakes hard to make: enums instead of free text, absolute values instead of relative ones ("2026-11-14", not "next Friday").

Default: strict: true on tool definitions; Zod or Pydantic on the result; dates and money as typed fields.

### Errors in plain words, with a retry decision

**Must.** A failed tool call returns an error flag and a message the model can act on: what went wrong, whether retrying can help, and what to do instead. Never a bare status code, an exception name or a stack trace. Code decides whether a retry can work; the model should not guess.

Default: is_error: true with { message, retryable, retry_after_s, next_step }. "That fare is sold out. Do not retry. Offer the 18:40 flight or another date." beats "409 Conflict". "The airline system is busy. Retry after 30 seconds." beats "503".

### Cap retries in code

**Must.** Left alone, the model retries an invalid call two or three times before giving up. Count tool errors per turn, stop after a fixed number, and give the user an honest line or a hand-off. A retryable error from your own systems is retried by code first, with backoff, before the model ever sees it.

Default: code retries a transient error once with backoff; at most 2 failed calls to the same tool per turn, then stop.

### Return only what the next step needs

**Must.** Return names and meanings, not internal IDs, MIME types or raw API payloads. Keep the IDs the next call needs, drop the rest. Page, filter and truncate long results with sensible defaults, and offer a short or detailed format when both are useful.

Default: results under about 2 KB ; at most 5 items per page; a response_format of concise or detailed.

### Business rules live in the tool

**Must.** A refund limit, a cancellation window or an eligibility check is enforced inside the tool, not only written in the prompt. The prompt explains the rule; the tool refuses with a clear reason when it is broken.

Default: every refusal carries reason, next step and retry kind (none, after more input, later).

### Tool results are untrusted data

**Must.** Emails, web pages, reviews, booking notes and partner API text can carry instructions aimed at the agent. Keep that content inside tool results, never in the system prompt, and never let it change who the agent acts for.

Default: third-party text returned only inside tool results, labelled as data.

### Keep tool definitions stable for the cache

**Should.** Tool definitions are the first thing in the prompt, so any change to them throws the cache away for every user. Change them only in a release, and leave tool choice on auto: forcing a tool skips the model's thinking and changing the choice invalidates cached messages.

Default: tool definitions versioned with the prompt; tool_choice: auto .

### Test tools on real multi-step tasks

**Should.** Write realistic tasks that need several tool calls and have a checkable outcome. Track tool errors, repeated calls, tokens and time per task: repeated calls usually mean a tool returns too little or pages badly.

Default: a held-out set of tasks the tool descriptions were not tuned on.

## Output and side effects

### Identity comes from the signed-in session

**Must.** Every tool that reads or writes a user's data takes the user id from the signed-in session (the signed session token). Never from model output or message text.

Default: tools receive the user id from the turn context; the model cannot pass one.

LangGraph: put the verified user id in the run context ( context_schema , read through Runtime ) or configurable , and read it inside the tool. Never make it a tool argument the model fills in.

### Code owns facts

**Must.** Prices, dates, times, booking references, addresses and links come from your systems, formatted by code. The model never computes or invents one.

Default: tools return formatted fact lines; the model places them, never rewrites them.

### Writes run once, with an expiry and a confirm

**Must.** Every write the user triggers (a booking, a refund, a cancellation) goes through a pending action that expires and runs once, with limits checked in the same transaction. Money and anything irreversible need an explicit confirm.

Default: a pending_actions table with an expiry of about 15 min ; the write and the limit check in one transaction; multi-step writes as a state column advanced by the worker.

LangGraph: call interrupt() before the write; the user's tap resumes it with Command(resume=...) . On resume the whole node runs again from the top, so everything before interrupt() must be safe to repeat, and the write itself needs an idempotency key.

### One reply path with an idempotency key

**Must.** Every outbound message goes through one function that dedupes and applies the chat's rules.

Default: send(user, intent, data) writes an outbox row in the same transaction as the turn, with a unique idempotency key; a worker delivers and retries rows with the same key.

### A strict output contract

**Must.** The model writes its own short messages; code validates them, allows one correction retry, and never splits or rewrites the model's text.

Default: 1 to 3 short messages per turn.

### Limits never break a feature

**Must.** Check the stop reason, retry once, fall back to a fixed line from code, and log the limit hit. Spending caps protect your bill; the user never sees one.

Default: a limit_hit counter with an alert.

## Safety and privacy

### A way to a human, always

**Must.** "Talk to a person" works from any message. The handover carries the conversation summary so the user does not repeat themselves, and the agent stays quiet while a human holds the chat.

Default: a takeover flag per conversation; the agent resumes only when the human hands back.

### Consent before personal questions; opt-out works everywhere

**Must.** Record consent with a timestamp before asking anything personal. STOP pauses proactive messages while still sending what the user needs about something they already booked.

Default: consent row per user; STOP and DELETE handled in code before the model runs.

### Delete means every copy, including traces

**Must.** One tracing provider per environment, never two. A delete erases the user's data everywhere you hold it: database, search index, recordings, transcripts and the active tracing provider. Hash user ids in traces.

Default: a deletion job row in Postgres that works through each store in order, marks each step done so it can resume, and writes an audit row at the end.

LangGraph: include checkpointer.delete_thread(thread_id) for every thread of the user, a store.delete for every key in the user's namespaces, and the trace erase.

### Never take secrets by speech or chat

**Must.** Card numbers, one-time codes and passwords are never collected in conversation. Send the user a secure link or hand off to a payment page instead.

Default: the agent refuses and offers the secure link; transcripts are redacted before storage.

## Spoken chat

These rules apply only when the app turns on speech in the same chat: speech to text for the person's message and text to speech for the reply. It is still the chat agent and the same chat turn. Phone calls and realtime voice agents are not covered.

### A spoken reply has no digits, symbols, links or emoji

**Must.** When text to speech is on, the spoken reply has no digits, symbols, links or emoji: numbers are spoken as words. A link or a table stays in the written reply.

Default: one or two spoken sentences per turn.

### A transcript is a message

**Must.** The text from speech to text follows the same storage, expiry and delete rules as a typed message. Audio is kept only as long as the privacy notice says.

Default: transcripts are redacted before storage, as for secrets.

### Speech calls log their cost

**Must.** Each speech to text and text to speech call records a cost row with the user and the feature, as every paid call does.

Default: the same cost table and the same daily alarm.

## Cost and tracing

### Every model call goes through Mainline

**Must.** Every model call (the language model, speech to text, text to speech) goes through the one Mainline client with the app's `MAINLINE_AI_KEY`. The app never holds a provider key. Which models and voices the app may use comes from the app's Can use list in Mainline. Mainline counts the cost, and the app also logs it per user.

Default: one small module in the app builds the Mainline client; no other file reads an AI key or names a provider; an app turns on LLM, STT and TTS in Mainline only when it needs them.

LangGraph: build the chat model for the model node from that client; never construct a provider client in a node.

### Every paid call logs its cost against the user

**Must.** Model, speech, messaging and classifier calls each record a cost row with the user and the feature, so cost per user and per feature is one query.

Default: store costs in the smallest unit (micro-currency); daily spend alarm per environment.

### Every turn traced with its prompt version

**Must.** Each trace carries the prompt version and hash, the tools called and the timings, so a bad reply leads straight to the prompt that wrote it.

Default: OpenTelemetry to your tracing provider; turn timings (first reply, model, tools, memory) as metrics.

LangGraph: send traces to your tracing provider (LangSmith tracing, or any OpenTelemetry backend such as Langfuse); add the prompt version and a hashed user id as run metadata , never the raw phone number.

## Testing and prompt changes

### Bug first

**Must.** Every bug gets a failing test before its fix: code bugs a unit or integration test, model behaviour a live case, memory a check against an answer key. A bug is closed only when its test is named.

Default: no "known failure" skips without an owner and a date.

### One job per test layer

**Must.** Automated tests on every change; a live set against the real model on every prompt change and nightly; a multi-day persona run with an answer key before each release; people using the real web chat, and the real speech providers when the app has speech, for edge cases only.

Default: a harness that fakes the web chat endpoint and the speech providers.

### A prompt change starts with a case and keeps the size

**Must.** Name the case it fixes or add one, run every suite before merge, hold each prompt to a byte budget, and do not let the total grow. Version every prompt so you can roll back.

Default: system prompt about 12 KB , tool definitions about 10 KB .

### A calibrated judge with a fallback

**Must.** Score quality with a model judge checked against human labels, and keep a second judge for when the first is down or capped.

Default: 80% agreement with human labels before the judge gates a release.

### Test-only code never ships

**Must.** Time travel, fake providers and test commands live in one module included only in non-production builds. Production refuses to start with test settings.

Default: a separate build entry for dev; a startup check on environment flags.

Defaults are starting points, not limits: measure your own latencies and costs and tune from there. Delete a rule only for a stated reason, never by omission. LangGraph references: memory, interrupts. Anthropic references: building effective agents, writing tools for agents, define tools, handle tool calls. Check the current docs before relying on exact APIs.
