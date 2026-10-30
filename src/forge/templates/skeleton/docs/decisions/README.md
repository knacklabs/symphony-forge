# Decisions

One file per decision the client or the team made, so it is never buried in a chat.

1. `forge decision new <slug>` writes the record: its context, the decision and what follows
   from it.
2. `forge decision accept <slug> --by "<name>"` accepts it after the human confirms it in chat.

Decisions are never deleted; a newer one supersedes an older one. The client's sign-off is a
decision whose slug ends in `client-signoff`, and no story is approved before it is accepted.

Questions still open go under `## To confirm` in the open-question form from the Forge guide.
`forge decision open` lists them; `forge decision answer` records the answers.
