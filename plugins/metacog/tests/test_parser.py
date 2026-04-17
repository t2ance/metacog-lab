import json
import pytest
from reminder.parser import parse_transcript, REMINDER_MARKER, MCP_TOOL_PREFIX


def _assistant_msg(tool_name: str, tool_input: dict) -> str:
    return json.dumps({
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "tool_use", "name": tool_name, "input": tool_input}],
        },
    })


def _user_text(text: str) -> str:
    return json.dumps({
        "type": "user",
        "message": {
            "role": "user",
            "content": [{"type": "text", "text": text}],
        },
    })


def _assistant_plain(text: str) -> str:
    return json.dumps({
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": text}],
        },
    })


def test_empty_transcript_has_no_open_sessions():
    r = parse_transcript([])
    assert r.open_session_ids == []
    assert r.turns_since_mcp == 0
    assert r.turns_since_reminder == 0
    assert r.malformed_line_count == 0


def test_detects_open_session_from_record_FOK():
    lines = [_assistant_msg("metacog.record_FOK", {"session_id": "s1", "FOK": 0.5})]
    r = parse_transcript(lines)
    assert r.open_session_ids == ["s1"]
    assert r.turns_since_mcp == 0


def test_excludes_closed_sessions():
    lines = [
        _assistant_msg("metacog.record_FOK", {"session_id": "s1", "FOK": 0.5}),
        _assistant_msg("metacog.close_session", {"session_id": "s1", "reason": "done"}),
    ]
    r = parse_transcript(lines)
    assert r.open_session_ids == []


def test_counts_assistant_turns_since_mcp():
    lines = [
        _assistant_msg("metacog.record_FOK", {"session_id": "s1", "FOK": 0.5}),
        _assistant_plain("text turn 1"),
        _assistant_plain("text turn 2"),
        _assistant_plain("text turn 3"),
    ]
    r = parse_transcript(lines)
    assert r.turns_since_mcp == 3


def test_reminder_marker_sets_turns_since_reminder():
    lines = [
        _assistant_msg("metacog.record_FOK", {"session_id": "s1", "FOK": 0.5}),
        _user_text(f"{REMINDER_MARKER} ping"),
        _assistant_plain("turn after reminder"),
        _assistant_plain("another turn"),
    ]
    r = parse_transcript(lines)
    assert r.turns_since_reminder == 2


def test_malformed_jsonl_line_skipped_and_counted():
    lines = [
        "not json at all",
        _assistant_msg("metacog.record_FOK", {"session_id": "s1", "FOK": 0.5}),
        "",
    ]
    r = parse_transcript(lines)
    assert r.open_session_ids == ["s1"]
    assert r.malformed_line_count == 1


def test_non_metacog_tool_use_ignored():
    lines = [
        _assistant_msg("Read", {"file_path": "/etc/hosts"}),
        _assistant_plain("turn"),
    ]
    r = parse_transcript(lines)
    assert r.open_session_ids == []
    assert r.turns_since_mcp == 2
