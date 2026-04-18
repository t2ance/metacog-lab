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
    """Initialize a session with an attempt budget. Required before record_FOK."""
    return tools.start_session(session_id, max_attempts, note)


@app.tool()
def record_FOK(session_id: str, FOK: float, note: str = "") -> str:
    """Pre-attempt confidence for a round. Session must be started via start_session first."""
    return tools.record_FOK(session_id, FOK, note)


@app.tool()
def record_JOL(session_id: str, JOL: float, note: str = "") -> str:
    """After solving this round: report JOL (post-attempt confidence, [0,1])."""
    return tools.record_JOL(session_id, JOL, note)


@app.tool()
def evaluate(session_id: str) -> str:
    """Decide stop/retry/abort for the just-completed round. Cycles state back to AWAITING_FOK."""
    return tools.evaluate(session_id)


@app.tool()
def close_session(session_id: str, reason: str = "") -> str:
    """Terminate the session. Further calls on this session_id are rejected."""
    return tools.close_session(session_id, reason)


if __name__ == "__main__":
    app.run()
