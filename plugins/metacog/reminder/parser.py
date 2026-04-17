"""Pure transcript parser for metacog reminder hook.

Reads Claude Code session JSONL transcript lines (reverse chronological
scan), reports counters used by the reminder hook:
  - turns_since_mcp: assistant turns since the most recent metacog.* tool_use
  - turns_since_reminder: assistant turns since the most recent reminder marker
  - open_session_ids: session_ids with a recent metacog.* call and no later close_session,
    within the window walked before both anchors (mcp + reminder) were found.
    Early-break at line-bottom means sessions opened BEFORE the most recent anchor
    may not be listed. This is intentional: reminders fire on recent activity, not
    on stale history.
  - malformed_line_count: count of JSONL lines that failed to parse. A non-zero
    value is a visible signal that some transcript content was silently skipped.

Transcript envelope (CC format, verified):
    {"type": "assistant"|"user"|..., "message": {"role": ..., "content": [...]}, ...}
Top-level "type" is the role; "message.content" holds the blocks.
"""
import json
from dataclasses import dataclass, field

REMINDER_MARKER = "[metacog_reminder]"
MCP_TOOL_PREFIX = "metacog."


@dataclass
class ParseResult:
    turns_since_mcp: int = 0
    turns_since_reminder: int = 0
    open_session_ids: list[str] = field(default_factory=list)
    malformed_line_count: int = 0


def _extract_text(content_blocks) -> str:
    if not isinstance(content_blocks, list):
        return ""
    out = []
    for block in content_blocks:
        if isinstance(block, dict) and block.get("type") == "text":
            out.append(block.get("text", ""))
    return "".join(out)


def parse_transcript(lines: list[str]) -> ParseResult:
    turns_since_mcp = 0
    turns_since_reminder = 0
    seen_mcp = False
    seen_reminder = False
    closed_ids: set[str] = set()
    # preserve insertion order; we see "most recent" first by reverse walk
    open_sessions: dict[str, None] = {}
    malformed = 0

    for raw in reversed(lines):
        if not raw or not raw.strip():
            continue
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            malformed += 1
            continue

        role = msg.get("type")
        inner = msg.get("message", {})
        content = inner.get("content", []) if isinstance(inner, dict) else []
        if not isinstance(content, list):
            content = [content]

        if role == "assistant":
            has_metacog_call = False
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") != "tool_use":
                    continue
                name = block.get("name", "")
                if not name.startswith(MCP_TOOL_PREFIX):
                    continue
                has_metacog_call = True
                tool_short = name[len(MCP_TOOL_PREFIX):]
                inp = block.get("input") or {}
                sid = inp.get("session_id")
                if not sid:
                    continue
                if tool_short == "close_session":
                    closed_ids.add(sid)
                elif sid not in closed_ids and sid not in open_sessions:
                    open_sessions[sid] = None
            if has_metacog_call and not seen_mcp:
                seen_mcp = True
            if not seen_mcp:
                turns_since_mcp += 1
            if not seen_reminder:
                turns_since_reminder += 1
        elif role == "user":
            text = _extract_text(content)
            if REMINDER_MARKER in text and not seen_reminder:
                seen_reminder = True

        if seen_mcp and seen_reminder:
            break

    # Closed-ids guard at insertion time already prevents closed sessions from entering open_sessions
    # under the reverse-walk order, so no filter needed here.
    return ParseResult(
        turns_since_mcp=turns_since_mcp,
        turns_since_reminder=turns_since_reminder,
        open_session_ids=list(open_sessions),
        malformed_line_count=malformed,
    )
