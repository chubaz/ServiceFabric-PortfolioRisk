# Studio–Codex gateway contract

Status: first development adapter implemented for Agent Studio; broader Studio reuse and automated worktree creation remain subsequent slices.

## Implemented bootstrap slice

Agent Studio now uses a provider boundary backed by the installed local Codex
app-server.  It persists an immutable blueprint/build proposal, requires a
recorded human authorization, then runs planning, `workspaceWrite`
implementation, verification and independent review as one asynchronous job. The browser
submits proposal, session, turn and approval identities; it never submits shell
commands, credentials, writable roots or sandbox policy.

The job pauses only when Codex emits a typed command or file-change permission
request. Final Registry admission remains a separate human decision. Read-only
planning and review jobs may run concurrently; mutable turns that share the
same development worktree are queued and serialized to prevent conflicting
edits. Several sessions remain independently observable and selectable.

The review surface polls retained app-server receipts and renders agent
messages, concise reasoning summaries, plans, commands, file changes, approval
requests, diffs, completion and reviewer output.  Corrections resume the same
thread.  Planning and independent review are read-only; implementation and
correction turns are limited to the current development worktree with network
access disabled.

This bootstrap deliberately reuses the already selected development worktree.
Creating, merging and removing a dedicated worktree from the web application is
not yet enabled.  Registry admission, activation and merge remain separate
human-owned lifecycle decisions.

Agent engineering turns are pinned to `gpt-5.6-terra` with `high` reasoning.
The automatic handoff prepares a proposal and autonomous job route; the human
must still authorize the proposal and start the Codex thread. The proposal
declares four narrow skills: build, configuration review, bounded testing and
Agent Graph design. Planning loads the review skill, implementation loads the
build skill, and the other skills remain explicit supporting instructions for
the relevant later turn.

## Verified local surface

- The installed `codex` executable is available and reports `codex-cli 0.146.0`.
- `codex app-server --stdio` starts successfully and was kept active during this qualification.
- The optional `openai-codex` Python package is not installed and is not required for the first adapter.
- The managed daemon command requires a separate standalone Codex installation that is not present. ServiceFabric must not install it implicitly.

The first adapter therefore owns one local `codex app-server --stdio` child process. The later Python SDK migration may replace this transport without changing Studio contracts.

## Supported protocol

The gateway uses the documented Codex app-server JSONL protocol:

1. start the local app-server process;
2. send `initialize` with ServiceFabric client metadata;
3. send `initialized`;
4. check `account/read` without exposing credentials to the browser;
5. call `thread/start` or `thread/resume` for a persistent thread;
6. call `turn/start` with the approved Studio build brief;
7. stream item, command, file-change, approval and agent-message events;
8. finish only after `turn/completed`;
9. retain the thread id, turn id, instruction sources, event receipts, diff and verification result.

Authoritative references:

- [Codex app-server](https://learn.chatgpt.com/docs/app-server)
- [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk)
- [Codex non-interactive permissions](https://learn.chatgpt.com/docs/non-interactive-mode#permissions-and-safety)

## Authorization boundary

The browser never submits a terminal command. It submits a typed, approved Studio proposal id. The backend resolves that immutable proposal and compiles the prompt, working directory, skill, permissions and verification contract.

A Codex thread may start only when:

- the design discussion reached recorded consensus;
- the blueprint was explicitly approved by a human;
- the proposal is `ready_for_studio_codex`;
- the target is the development worktree, never production;
- `AGENTS.md`, the relevant skill and workplan are present;
- writable roots are limited to the exact worktree;
- external financial effects and licensed-database writes remain denied.

Use `workspaceWrite`, never full access. Approval policy must preserve review for commands outside trusted project rules. Network access is off by default and may be enabled only by a reviewed provider-specific task.

## Knowledge pack

Every thread receives references rather than a repository dump:

1. root and nearest `AGENTS.md` files;
2. current workplan and the target Studio contract;
3. the approved proposal and compiled blueprint;
4. relevant canonical contract and Registry identities;
5. the selected object-building skill;
6. exact allowed and forbidden paths;
7. representative, failure and adversarial fixtures;
8. verification commands and expected handoff fields.

The app-server returns `instructionSources`; the gateway must display and persist them so the user can verify which durable instructions were actually loaded.

## Session lifecycle

```text
approved proposal
  -> prepare Studio–Codex brief
  -> human authorizes and starts job
  -> initialize app-server
  -> start persistent thread
  -> planning -> implementation -> verification -> independent review
  -> pause only for a typed Codex permission request
  -> persist diff, receipts and reviewer output
  -> accept / request revision / reject
  -> optional reviewed merge handoff
  -> archive thread and remove worktree only after approval
```

Thread and worktree identities remain distinct. A thread may be resumed; a worktree may be retained for review. Neither is deleted merely because a turn completed.
Active jobs recover their persisted thread and resume the appropriate automatic
stage when the Studio reconnects after a local server restart.

## Required API surface

- `GET /api/studios/codex/status`: executable, version, process, authentication and transport state.
- `POST /api/studios/codex/sessions`: start from one approved proposal id.
- `GET /api/studios/codex/sessions`: list retained Studio sessions.
- `GET /api/studios/codex/sessions/{id}`: thread, turns, instruction sources and receipts.
- `POST /api/studios/codex/sessions/{id}/turns`: send a reviewed follow-up.
- `POST /api/studios/codex/sessions/{id}/interrupt`: interrupt the active turn.
- `POST /api/studios/codex/sessions/{id}/review`: request a read-only diff review.
- `DELETE /api/studios/codex/sessions/{id}`: archive the thread; worktree deletion remains a separate confirmed action.

The frontend shows live events but cannot fabricate an `active`, `completed` or `verified` state. Those states come only from app-server notifications and retained verification receipts.

## Object-building skills

Each Studio uses a narrow skill that teaches Codex how to reuse canonical definitions, model the object, add only its lifecycle/apply capabilities, produce fixtures, register a candidate and return a handoff. Capability creation first searches the Capability Library and packages. Agent, Workflow, Dashboard, Report and Package proposals remain non-final until their owning Studio validates them.

## Acceptance gate for the transport slice

1. Status distinguishes executable available, process active, authenticated and proposal authorized.
2. One approved synthetic capability proposal starts a persistent thread in an isolated worktree.
3. The UI streams at least agent messages, command events, file changes, approvals and completion.
4. Loaded instruction sources and selected skill are visible.
5. No raw shell command or credential crosses the browser API.
6. Interrupt, resume and review work after a server restart.
7. No merge, worktree removal, external effect or production use occurs automatically.
