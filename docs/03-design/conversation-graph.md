# Sheldon's conversation: turn phases, graph driver and background replies

How one message to Sheldon is answered, what changed in stage 7, and what is still to do.

## Summary

| Change | Effect |
|---|---|
| The 515-line message handler is split into four phases | Each phase has one job and can be read and tested separately |
| The phases can be driven by a LangGraph graph | Same structure as the run graph; one setting switches it on |
| A message can be answered in the background | The browser no longer waits on one long request, so a slow reply does not end in "fetch aborted" |

## The four phases of a turn

All four are in `src/app/api/projects/conversation.py`. The code inside each phase is unchanged from the former `_post_project_conversation_message_inner`.

| Phase | Function | What it does | Ends the turn when |
|---|---|---|---|
| receive | `_turn_receive` | Checks access, stores the user's message, answers obvious greetings, starts the run when the user says "go" | Greeting or acknowledgement on a new conversation; "go" with a plan available |
| understand | `_turn_understand` | Builds the working instruction from the history; extracts discovery answers (rules, model, project wiki) | A "redo" request with nothing to redo |
| route | `_turn_route` | Loads project context, asks the router what this turn is, settles the output types | The request is out of scope |
| respond | `_turn_respond` | Asks discovery questions, continues the storyline, answers conversationally, or proposes a plan | Always (it is the last phase) |

A phase returns the reply when it ends the turn, or `None` to continue. The phases share a `Turn` object (project, request, user, database session, and a dictionary of working variables).

## The driver

`src/workflows/conversation_graph.py`, function `run_turn`.

A LangGraph graph: one node per phase, and after each node an edge to the next phase or to the end if there is a reply. The earlier plain loop and the `CONVERSATION_ORCHESTRATOR` setting were removed on 2026-10-06. Each turn is one trace (`conversation.turn`) with one span per phase.

Nothing is checkpointed. A turn lives inside one request or one worker thread, and the conversation's lasting state (state name, slots, pending questions) is already stored on the conversation row. The conversation has the same shape as the run graph, which is what the items under "Not done yet" build on.

## Background replies

`src/app/api/projects/conversation_turns.py`

| Call | Result |
|---|---|
| `POST /api/projects/{pid}/conversation/messages?background=true` (also `/decisions` and `/outline`) | Returns at once with `turn_id`, `status: running` |
| `GET /api/projects/{pid}/conversation/turns/{turn_id}` | `status` (`running`, `done`, `failed`), `phase`, `phase_label`, and when finished `status_code` and `response` (the same body the direct call returns, or the error) |

- Without `?background=true` the endpoint behaves exactly as before.
- The turn is recorded in the new table `conversation_turns` (migration `021_conversation_turns`), so any API process can answer the poll.
- The reply is produced on a worker thread (up to 8 at a time per API process) with its own database session.
- Progress (`phase`) is kept in memory in the process that is answering. It is not written to the database during the turn, because on SQLite a second writer waits on the turn's own transaction. A poll that reaches another API process shows "Starting" until the reply is ready.
- A turn still running 15 minutes after it started is reported as failed ("The reply was interrupted"). This covers a server restart during a turn.
- Only the user who sent the message can read the turn.

### Frontend

`frontend/lib/conversationTurn.ts` (`sendConversationMessage`, `postConversationInBackground`) starts the turn and polls every 1.5 seconds. Both chat hooks use it for messages, plan decisions and outline changes (`hooks/useProjectStudio.ts`, `hooks/useRunStudio.tsx`). While Sheldon is working, the classic page and the guided view show the current step, for example "Sheldon: Writing the reply…".

## How it was verified

- All unit and integration tests pass through the graph. The existing tests that propose and confirm a plan go through all four phases.
- `tests/unit/test_conversation_graph.py`: phase order, early stop, an error reaching the caller unchanged, a plan proposed through the graph, a background turn started and polled, a failed turn, access and validation.
- `frontend/lib/conversationTurn.test.ts` (4 tests): polling, failed turn, rejected message, a dropped poll.
- Live check on a scratch server with the graph driver and real worker threads: the start call returned in 0.01 seconds and the poll returned Sheldon's reply. This check found and fixed a "database is locked" error that the in-process test could not show.
- **Not done:** a turn with a real model through the browser. The model was not configured in the live check, so Sheldon's fallback replies were used.

## Not done yet

| Item | Why it matters |
|---|---|
| Replies streamed word by word | Left out on purpose for now: through the Claude CLI bridge the model's text arrives in one piece, so streaming would show nothing extra. Worth doing when the app runs on a provider that streams (API key) |
| `/confirm` in the background | It does not call the model, so it answers directly |
| Plan confirmation as a graph interrupt | Would join the conversation graph to the run graph (see `langgraph-run-graph.md`) |
| Finer nodes inside respond | Respond still holds discovery, storyline, slide negotiation and plan proposal (`_handle_collaborative_building` is 370 lines) |
| Moving the phases out of the API folder | They belong in `src/agents/conversation/`; they stay in the API module for now because they share helpers with the run endpoints |
| Clean-up of old `conversation_turns` rows | Rows are small but are never deleted |
| Making `langgraph` the default | Decide after a full conversation with a real model under the graph driver |
