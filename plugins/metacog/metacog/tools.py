import time

from metacog.state import (
    STATE_STORE,
    STATE_AWAITING_FOK,
    STATE_AWAITING_JOL,
    STATE_AWAITING_EVAL,
)

_HUMAN_STATE = {
    STATE_AWAITING_FOK: "(start of new round; nothing recorded yet)",
    STATE_AWAITING_JOL: "record_FOK (pre-attempt confidence recorded)",
    STATE_AWAITING_EVAL: "record_JOL (post-attempt confidence recorded)",
}
_EXPECTED_NEXT = {
    STATE_AWAITING_FOK: "record_FOK (pre-attempt confidence for the new round)",
    STATE_AWAITING_JOL: "record_JOL (post-attempt confidence after solving)",
    STATE_AWAITING_EVAL: "evaluate (decide continue/stop/abort)",
}
_CALL_DESC = {
    "record_FOK": "record_FOK (pre-attempt confidence)",
    "record_JOL": "record_JOL (post-attempt confidence)",
    "evaluate": "evaluate (read next-step advice)",
    "close_session": "close_session (end the session)",
}

_NO_SESSION_HINT = (
    "session {sid} does not exist; call start_session(session_id, max_attempts) first"
)


def _reject(current_call: str, state: str) -> str:
    return (
        "Call order violates the metacognitive flow.\n"
        f"  Your last step: {_HUMAN_STATE[state]}\n"
        f"  Next step should be: {_EXPECTED_NEXT[state]}\n"
        f"  But you called: {_CALL_DESC[current_call]}\n"
        "Call order must be: start_session -> FOK -> solve -> JOL -> evaluate."
    )


def _closed_msg(sid: str, s: dict) -> str:
    return (
        f"Session {sid} is closed (reason: {s['close_reason']}). "
        "Open a new session with a fresh session_id."
    )


def start_session(session_id: str, max_attempts: int = 4, note: str = "") -> str:
    """Initialize a session with an attempt budget. Required before record_FOK."""
    assert max_attempts >= 1, f"max_attempts must be >= 1, got {max_attempts}"
    s = STATE_STORE.get(session_id)
    if s is not None:
        if s["status"] == "closed":
            return _closed_msg(session_id, s)
        return (
            f"Session {session_id} already exists "
            f"(max_attempts={s['max_attempts']}, state={s['state']}). "
            "No change made; call record_FOK to start a round."
        )
    STATE_STORE.create(session_id, max_attempts=max_attempts, note=note)
    note_part = f", note: {note}" if note else ""
    return (
        f"Session {session_id} started (max_attempts={max_attempts}{note_part}).\n"
        "Next step: call record_FOK(session_id, FOK, note) to report pre-attempt confidence."
    )


def record_FOK(session_id: str, FOK: float, note: str = "") -> str:
    """Pre-attempt confidence for a round. Session must be started via start_session first."""
    assert 0.0 <= FOK <= 1.0, f"FOK out of range: {FOK}"
    s = STATE_STORE.get(session_id)
    assert s is not None, _NO_SESSION_HINT.format(sid=session_id)
    if s["status"] == "closed":
        return _closed_msg(session_id, s)
    if s["state"] != STATE_AWAITING_FOK:
        return _reject("record_FOK", s["state"])
    s["pending"] = {"FOK": FOK, "note_fok": note, "fok_ts": time.time()}
    s["state"] = STATE_AWAITING_JOL
    s["last_activity"] = time.time()
    return (
        "Recorded FOK for this round.\n"
        "Next step: solve the problem. When done, call "
        "record_JOL(session_id, JOL, note) to report post-attempt confidence."
    )


def record_JOL(session_id: str, JOL: float, note: str = "") -> str:
    """Attempt done. Report JOL (post-attempt confidence) in [0, 1]."""
    assert 0.0 <= JOL <= 1.0, f"JOL out of range: {JOL}"
    s = STATE_STORE.get(session_id)
    assert s is not None, _NO_SESSION_HINT.format(sid=session_id)
    if s["status"] == "closed":
        return _closed_msg(session_id, s)
    if s["state"] != STATE_AWAITING_JOL:
        return _reject("record_JOL", s["state"])
    p = s["pending"]
    s["attempts"].append(
        {
            "attempt_id": len(s["attempts"]) + 1,
            "FOK": p["FOK"],
            "JOL": JOL,
            "note_fok": p["note_fok"],
            "note_jol": note,
            "fok_ts": p["fok_ts"],
            "jol_ts": time.time(),
        }
    )
    s["pending"] = None
    s["state"] = STATE_AWAITING_EVAL
    s["last_activity"] = time.time()
    return (
        "Recorded JOL for this round.\n"
        "Next step: call evaluate(session_id) to see whether to stop, retry, or abort."
    )


_T_STOP_JOL = 0.80
_T_RETRY_HOPE = 0.25
_T_ABORT_MIN_ATTEMPTS = 3
_T_ABORT_AVG_JOL = 0.55


def evaluate(session_id: str) -> str:
    """Compute advice for the just-finished attempt. Always cycles state back to AWAITING_FOK."""
    s = STATE_STORE.get(session_id)
    assert s is not None, _NO_SESSION_HINT.format(sid=session_id)
    if s["status"] == "closed":
        return _closed_msg(session_id, s)
    if s["state"] != STATE_AWAITING_EVAL:
        return _reject("evaluate", s["state"])

    attempts = s["attempts"]
    last = attempts[-1]
    FOK, JOL, n = last["FOK"], last["JOL"], len(attempts)
    avg_JOL = sum(a["JOL"] for a in attempts) / n
    s["state"] = STATE_AWAITING_FOK
    s["last_activity"] = time.time()

    if n >= _T_ABORT_MIN_ATTEMPTS and avg_JOL < _T_ABORT_AVG_JOL and JOL < _T_ABORT_AVG_JOL:
        return (
            f"Advice: abort. After {n} attempts, confidence has not improved meaningfully "
            f"(avg JOL~={avg_JOL:.2f}). Tell the user you cannot complete this for now, "
            "then call close_session(session_id, 'abort: low JOL across rounds') to end the session."
        )
    if JOL >= _T_STOP_JOL:
        return (
            f"Advice: stop. Confidence is high enough (JOL={JOL:.2f}); deliver the answer "
            f"to the user. {n} attempts total. After delivery, call "
            "close_session(session_id, 'done') to end the session."
        )
    if n >= s["max_attempts"]:
        return (
            f"Advice: stop (budget exhausted, used {s['max_attempts']} attempts). "
            "Deliver the best version so far with a note on its limitations, then call close_session."
        )
    if (1 - JOL) * FOK >= _T_RETRY_HOPE:
        return (
            f"Advice: retry. Confidence is low but improvement is plausible (JOL={JOL:.2f}). "
            f"{n} attempts so far, {s['max_attempts'] - n} attempts remaining.\n"
            "Next step: call record_FOK(session_id, FOK, note) to start a new round."
        )
    return (
        f"Advice: ambiguous. Confidence is low and another attempt may not help (JOL={JOL:.2f}). "
        "Either deliver the current version with a note on limitations, or try a completely "
        "different approach. After delivery, call close_session."
    )


def close_session(session_id: str, reason: str = "") -> str:
    """Terminate session. All subsequent tool calls on this session_id will be rejected."""
    s = STATE_STORE.get(session_id)
    assert s is not None, _NO_SESSION_HINT.format(sid=session_id)
    if s["status"] == "closed":
        return f"Session {session_id} is already closed (reason: {s['close_reason']})."
    effective_reason = reason if reason else "unspecified"
    STATE_STORE.close(session_id, effective_reason)
    return (
        f"Session {session_id} closed (reason: {effective_reason}). Reminders will stop."
    )
