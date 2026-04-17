# metacog plugin

Metacognitive FOK/JOL loop MCP for Claude Code with periodic reminders for open sessions.

## State machine

    AWAITING_FOK -> record_FOK -> AWAITING_JOL -> record_JOL -> AWAITING_EVAL -> evaluate -> AWAITING_FOK ...

Agent may call `close_session(session_id, reason)` in any running state to terminate. CLOSED is a latch — all further tool calls on that session_id are rejected.

`evaluate()` returns advice text ("建议：停下" / "建议：重试" / "建议：放弃" / "建议：模糊") but never changes the FSM state to terminal — state cycles back to AWAITING_FOK. Agent autonomy decides whether to start a new round.

## Install

Option A — via marketplace (recommended once the repo is published):

    /plugin marketplace add https://github.com/<you>/metacog-lab
    /plugin install metacog@metacog-lab

Option B — local development:

    /plugin marketplace add /data1/peijia/projects/metacog-lab
    /plugin install metacog@metacog-lab

## Requirements

- Python 3.10+
- `mcp` Python SDK (system-wide `pip install mcp`, or rely on a Python environment that already provides it)

## Reminder mechanism

A `UserPromptSubmit` hook fires each user turn. The hook script parses the CC transcript (stdin payload contains `transcript_path`) and counts:

- turns since the most recent `metacog.*` tool_use
- turns since the last reminder the hook itself injected

If BOTH counts are >= 10 AND at least one open (non-closed) session exists, the hook emits a `<system-reminder>` listing open session_ids. Thresholds mirror CC's TodoList reminder (attachments.ts:254-257).

## Tools

- `record_FOK(session_id, FOK, note)` — call before solving. FOK in [0, 1].
- `record_JOL(session_id, JOL, note)` — call after solving. JOL in [0, 1].
- `evaluate(session_id)` — returns human-language advice; state cycles back to AWAITING_FOK.
- `close_session(session_id, reason)` — latch session as CLOSED.

## Tuning

Edit `reminder/entry.py`:

    TURNS_SINCE_MCP = 10
    TURNS_BETWEEN_REMINDERS = 10

Edit `metacog/tools.py`:

    _T_STOP_JOL = 0.80          # JOL >= this => "建议：停下"
    _T_RETRY_HOPE = 0.25        # (1-JOL)*FOK >= this => "建议：重试"
    _T_ABORT_MIN_ATTEMPTS = 3   # min attempts before abort eligible
    _T_ABORT_AVG_JOL = 0.55     # avg JOL < this AND last JOL < this => "建议：放弃"

## Tests

Unit tests cover state machine, tool branches, parser behavior:

    cd plugins/metacog
    pytest -v

Integration smoke (full FSM cycle + parser + hook entry):

    bash tests/smoke_e2e.sh

## Layout

    plugins/metacog/
      .claude-plugin/plugin.json     # CC plugin manifest
      metacog/                       # MCP server package
        state.py                     # SessionStore FSM (pure)
        tools.py                     # 4 tool implementations (pure)
        server.py                    # FastMCP wiring
      reminder/                      # Hook package
        parser.py                    # Transcript scanner (pure)
        entry.py                     # UserPromptSubmit hook adapter
      tests/                         # Unit + smoke tests
      pyproject.toml
      README.md                      # this file

## Known limitations

- Session state is in-memory only; it does not survive a CC restart. This is a deliberate scope cut — add file persistence later if cross-session replay becomes valuable.
- `pip install -e .` for this plugin directory fails due to setuptools auto-discovery ambiguity across three top-level dirs (metacog/reminder/tests). Not needed for normal use since CC plugin loader invokes entry scripts directly via `${CLAUDE_PLUGIN_ROOT}` paths.
