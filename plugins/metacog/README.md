# metacog plugin

Make Claude Code stop, calibrate, and decide before sinking turns into a hard problem.

The plugin gives the agent a metacognitive loop (start → FOK → solve → JOL → evaluate) and
periodically reminds the agent if it forgets to use the loop on a long-running session.

## Install

1. Install the Python SDK the MCP server depends on. **Plugin install does NOT do this for you.**

   ```bash
   pip install mcp
   ```

   Install into the Python that `python3` resolves to in the shell where Claude Code runs
   (`which python3` to confirm). Without `mcp`, the MCP server crashes on launch and the
   tools silently fail to appear.

2. Register the marketplace and install the plugin in Claude Code:

   ```
   /plugin marketplace add https://github.com/t2ance/metacog-lab
   /plugin install metacog@metacog-lab
   /reload-plugins
   ```

Requirements: Python 3.10+.

## Update

When the upstream repo has new commits, pull them in:

    /plugin marketplace update metacog-lab
    /plugin install metacog@metacog-lab
    /reload-plugins

`marketplace update` refreshes the catalog; `install` re-runs and overwrites the old version;
`reload-plugins` activates the new version in the running session.

## How to use

After install, the agent gains 5 tools: `start_session`, `record_FOK`, `record_JOL`,
`evaluate`, `close_session`. Intended call flow per problem:

1. Once per problem: agent calls `start_session(session_id, max_attempts, note)` to
   allocate the attempt budget for this session.
2. Before attempting: agent calls `record_FOK(session_id, FOK)` with confidence in [0, 1]
   that it can solve the problem.
3. Agent solves.
4. After attempting: agent calls `record_JOL(session_id, JOL)` with confidence in [0, 1]
   that the answer is correct.
5. Agent calls `evaluate(session_id)` and reads the advice — stop / retry / abort / ambiguous.
6. When the problem is done (or abandoned), agent calls `close_session(session_id, reason)`.

`session_id` is a free string the agent picks; one per problem. `record_FOK` on a
session that was never started raises an error.

### What you will see

- Tool calls in the agent's transcript named `mcp__plugin_metacog_metacog__record_FOK` etc.
- The agent's reply incorporates the advice text returned by `evaluate`.
- If the agent opens a session and then ignores metacog for ≥10 of your turns, a
  `<system-reminder>` appears listing the open `session_id`(s), nudging the agent to call
  `evaluate` or `close_session`.

### Verify install

Ask the agent to do a non-trivial task and explicitly instruct it to use the metacog loop.
You should see the four tool calls in order. If nothing appears, `pip install mcp` was
either skipped or installed into the wrong Python.

## Tools

- `start_session(session_id, max_attempts=4, note="")` — initialize a session with an
  attempt budget. Required before `record_FOK`. Calling on an existing running session is
  a no-op (original budget kept). Calling on a closed session is rejected.
- `record_FOK(session_id, FOK, note="")` — pre-attempt confidence, FOK in [0, 1].
- `record_JOL(session_id, JOL, note="")` — post-attempt confidence, JOL in [0, 1].
- `evaluate(session_id)` — advice (stop / retry / abort / ambiguous); cycles state back to AWAITING_FOK.
- `close_session(session_id, reason)` — latch session as CLOSED; further calls rejected.

## Tuning

Reminder cadence — `reminder/entry.py`:

    TURNS_SINCE_MCP = 10
    TURNS_BETWEEN_REMINDERS = 10

Evaluator thresholds — `metacog/tools.py`:

    _T_STOP_JOL = 0.80          # JOL >= this => "Advice: stop"
    _T_RETRY_HOPE = 0.25        # (1-JOL)*FOK >= this => "Advice: retry"
    _T_ABORT_MIN_ATTEMPTS = 3   # min attempts before abort eligible
    _T_ABORT_AVG_JOL = 0.55     # avg JOL < this AND last JOL < this => "Advice: abort"

## Limitations

Session state is in memory; it does not survive a Claude Code restart.
