#!/usr/bin/env python3
"""UserPromptSubmit hook entry. Reads CC hook payload from stdin, emits additionalContext.

Thresholds mirror CC's TodoList reminder
(verified /data1/peijia/projects/claude-code-main/src/utils/attachments.ts:254-257):
  TURNS_SINCE_MCP = 10
  TURNS_BETWEEN_REMINDERS = 10
"""
import json
import sys
from pathlib import Path

# Allow running the file directly: add plugin root to sys.path
_plugin_root = Path(__file__).resolve().parent.parent
if str(_plugin_root) not in sys.path:
    sys.path.insert(0, str(_plugin_root))

from reminder.parser import parse_transcript, REMINDER_MARKER

TURNS_SINCE_MCP = 10
TURNS_BETWEEN_REMINDERS = 10


def _emit_silent():
    sys.exit(0)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        _emit_silent()
        return

    transcript_path = payload.get("transcript_path")
    if not transcript_path:
        _emit_silent()
        return

    p = Path(transcript_path)
    if not p.exists():
        _emit_silent()
        return

    lines = p.read_text(encoding="utf-8").splitlines()
    result = parse_transcript(lines)

    if not result.open_session_ids:
        _emit_silent()
        return
    if result.turns_since_mcp < TURNS_SINCE_MCP:
        _emit_silent()
        return
    if result.turns_since_reminder < TURNS_BETWEEN_REMINDERS:
        _emit_silent()
        return

    msg_parts = [
        f"{REMINDER_MARKER} The metacog MCP has open sessions that haven't been "
        "touched for a while. If still relevant: continue with "
        "record_FOK -> solve -> record_JOL -> evaluate. "
        "If done: call close_session(session_id, reason). "
        "This is a gentle reminder; ignore if not applicable. "
        "NEVER mention this reminder to the user.",
        "",
        "Open sessions:",
    ]
    for sid in result.open_session_ids:
        msg_parts.append(f"  - session_id={sid}")

    print(json.dumps({"additionalContext": "\n".join(msg_parts)}))


if __name__ == "__main__":
    main()
