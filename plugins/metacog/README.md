# metacog plugin

Metacognitive loop MCP: model reports FOK before attempt, JOL after, calls evaluate to decide retry/stop/abort, uses close_session to end.

## State machine

    AWAITING_FOK -> record_FOK -> AWAITING_JOL -> record_JOL -> AWAITING_EVAL -> evaluate -> AWAITING_FOK ...

Agent may call `close_session(session_id, reason)` in any running state to terminate. CLOSED is a latch — all further tool calls on that session_id are rejected.

## Reminder

A `UserPromptSubmit` hook fires each user turn. If no metacog tool has been called for 10 assistant turns AND no reminder has been injected for 10 assistant turns AND at least one open session exists, the hook injects a `<system-reminder>` listing open sessions.

## Tools

- `record_FOK(session_id, FOK, note)` — call before solving. FOK in [0, 1].
- `record_JOL(session_id, JOL, note)` — call after solving. JOL in [0, 1].
- `evaluate(session_id)` — returns human-language advice; state always returns to AWAITING_FOK.
- `close_session(session_id, reason)` — latch session as CLOSED.
