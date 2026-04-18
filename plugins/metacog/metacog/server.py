"""MCP server entry point. Run as: python3 path/to/server.py (stdio MCP)."""
import sys
from pathlib import Path

# Allow running the file directly without install: add plugin root to sys.path
_plugin_root = Path(__file__).resolve().parent.parent
if str(_plugin_root) not in sys.path:
    sys.path.insert(0, str(_plugin_root))

from mcp.server.fastmcp import FastMCP

from metacog import tools

app = FastMCP("metacog")


@app.tool()
def start_session(session_id: str, max_attempts: int = 4, note: str = "") -> str:
    """Open a metacognition session for a non-trivial problem you are about to attempt.

    WHEN TO CALL: Once at the very start of any task you are not certain you can solve
    in one shot — multi-step reasoning, debugging, design, math, code that must compile
    on first try, etc. Skip for trivial Q&A.

    WORKFLOW: This is step 1 of 5. After this, the loop is:
        record_FOK(before each attempt) -> solve -> record_JOL(after) -> evaluate -> repeat or close.

    PARAMS:
        session_id: free string, your choice (e.g., "fix-bug-x", "essay-draft").
            Must be unique per problem; reusing a closed id is rejected.
        max_attempts: budget for solve attempts before evaluate forces a stop. Default 4.
            Use 2 for simple problems, 6-8 for hard ones.
        note: optional free text describing what this session is about. Stored only;
            does not affect any decision.

    Returns confirmation. Calling on an existing running session is a no-op.
    """
    return tools.start_session(session_id, max_attempts, note)


@app.tool()
def record_FOK(session_id: str, FOK: float, note: str = "") -> str:
    """Report your pre-attempt confidence (Feeling of Knowing) before solving this round.

    WHEN TO CALL: Immediately BEFORE each solving attempt. The session must already be
    started via start_session, otherwise this raises an error.

    WORKFLOW: This is step 2 of 5. Next: solve, then call record_JOL.

    PARAMS:
        session_id: the id you passed to start_session.
        FOK: float in [0, 1]. Your honest estimate that you can produce a correct answer.
            0.9 = "I'm confident". 0.3 = "I'll try but I'm shaky". Calibration matters —
            inflated FOK confuses the evaluate step.
        note: optional free text recording what makes you confident or uncertain.

    Returns confirmation + reminder of the next step.
    """
    return tools.record_FOK(session_id, FOK, note)


@app.tool()
def record_JOL(session_id: str, JOL: float, note: str = "") -> str:
    """Report your post-attempt confidence (Judgment of Learning) after producing an answer.

    WHEN TO CALL: Immediately AFTER finishing a solving attempt, before showing the answer
    to the user. Pairs 1:1 with the preceding record_FOK in this round.

    WORKFLOW: This is step 4 of 5 (step 3 was solving). Next: evaluate.

    PARAMS:
        session_id: the id of this session.
        JOL: float in [0, 1]. Your honest estimate that the answer you just produced is
            correct. 0.9 = "this is solid". 0.3 = "this might well be wrong". Compared
            against thresholds in evaluate to recommend stop/retry/abort.
        note: optional free text — what you tried, what you're unsure about.

    Returns confirmation + reminder to call evaluate next.
    """
    return tools.record_JOL(session_id, JOL, note)


@app.tool()
def evaluate(session_id: str) -> str:
    """Read the advice for the just-completed round: stop, retry, abort, or ambiguous.

    WHEN TO CALL: Right after record_JOL, before deciding what to tell the user.

    WORKFLOW: This is step 5 of 5. The returned advice is one of:
        - "Advice: stop"      -> deliver the answer; then close_session.
        - "Advice: retry"     -> try a fresh attempt; loop back to record_FOK.
        - "Advice: abort"     -> tell the user you cannot complete; then close_session.
        - "Advice: ambiguous" -> deliver with caveats OR pivot to a different approach.

    State always cycles back to AWAITING_FOK regardless of the advice — the agent decides
    whether to actually start a new round or close.

    PARAMS:
        session_id: the id of this session.

    Returns the advice string. Read it, do not ignore it.
    """
    return tools.evaluate(session_id)


@app.tool()
def close_session(session_id: str, reason: str = "") -> str:
    """Terminate the session. Use when the problem is delivered, abandoned, or aborted.

    WHEN TO CALL: After delivering the final answer (reason='done'), giving up
    (reason='abort: ...'), or whenever the problem is concluded. Stops the periodic
    open-session reminders for this id.

    WORKFLOW: Final step. Once closed, all further calls on this session_id are rejected
    (it's a latch — you must use a fresh session_id for the next problem).

    PARAMS:
        session_id: the id of the session to close.
        reason: short free text — 'done', 'user cancelled', 'abort: low JOL', etc.

    Returns confirmation that the session is closed.
    """
    return tools.close_session(session_id, reason)


if __name__ == "__main__":
    app.run()
