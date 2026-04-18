import pytest
from metacog.state import SessionStore, STATE_AWAITING_JOL, STATE_AWAITING_FOK
from metacog import tools


@pytest.fixture
def store(monkeypatch):
    fresh = SessionStore()
    monkeypatch.setattr(tools, "STATE_STORE", fresh)
    return fresh


def test_start_session_creates_with_defaults(store):
    result = tools.start_session("sess_1")
    assert "started" in result
    assert "max_attempts=4" in result
    s = store.get("sess_1")
    assert s is not None
    assert s["state"] == STATE_AWAITING_FOK
    assert s["max_attempts"] == 4
    assert s["note"] == ""


def test_start_session_with_custom_max_attempts(store):
    tools.start_session("sess_1", max_attempts=8, note="hard problem")
    s = store.get("sess_1")
    assert s["max_attempts"] == 8
    assert s["note"] == "hard problem"


def test_start_session_invalid_max_attempts_raises(store):
    with pytest.raises(AssertionError):
        tools.start_session("sess_1", max_attempts=0)


def test_start_session_on_existing_running_session_no_op(store):
    tools.start_session("sess_1", max_attempts=8)
    result = tools.start_session("sess_1", max_attempts=2)
    assert "already exists" in result
    assert store.get("sess_1")["max_attempts"] == 8


def test_start_session_on_closed_session_returns_closed_msg(store):
    tools.start_session("sess_1")
    tools.close_session("sess_1", "done")
    result = tools.start_session("sess_1")
    assert "is closed" in result


def test_record_FOK_records(store):
    tools.start_session("sess_1")
    result = tools.record_FOK("sess_1", 0.7, "some note")
    assert "Recorded FOK" in result
    s = store.get("sess_1")
    assert s["state"] == STATE_AWAITING_JOL
    assert s["pending"]["FOK"] == 0.7
    assert s["pending"]["note_fok"] == "some note"


def test_record_FOK_without_start_session_raises(store):
    with pytest.raises(AssertionError):
        tools.record_FOK("sess_ghost", 0.5, "")


def test_record_FOK_out_of_range_raises(store):
    tools.start_session("sess_1")
    with pytest.raises(AssertionError):
        tools.record_FOK("sess_1", 1.5, "")
    with pytest.raises(AssertionError):
        tools.record_FOK("sess_1", -0.01, "")


def test_record_FOK_twice_in_a_row_returns_reject(store):
    tools.start_session("sess_1")
    tools.record_FOK("sess_1", 0.5, "")
    result = tools.record_FOK("sess_1", 0.6, "")
    assert "Call order violates" in result
    assert "record_FOK" in result


def test_record_FOK_on_closed_session_returns_closed_msg(store):
    tools.start_session("sess_1")
    tools.close_session("sess_1", "done")
    result = tools.record_FOK("sess_1", 0.5, "")
    assert "is closed" in result


def test_record_JOL_records_attempt(store):
    tools.start_session("sess_1")
    tools.record_FOK("sess_1", 0.7, "fok note")
    result = tools.record_JOL("sess_1", 0.5, "jol note")
    assert "Recorded JOL" in result
    s = store.get("sess_1")
    assert len(s["attempts"]) == 1
    a = s["attempts"][0]
    assert a["attempt_id"] == 1
    assert a["FOK"] == 0.7
    assert a["JOL"] == 0.5
    assert a["note_fok"] == "fok note"
    assert a["note_jol"] == "jol note"
    assert s["pending"] is None
    assert s["state"] == "awaiting_EVAL"


def test_record_JOL_out_of_range_raises(store):
    tools.start_session("sess_1")
    tools.record_FOK("sess_1", 0.5, "")
    with pytest.raises(AssertionError):
        tools.record_JOL("sess_1", 1.5, "")


def test_record_JOL_without_FOK_returns_reject(store):
    tools.start_session("sess_1")
    result = tools.record_JOL("sess_1", 0.5, "")
    assert "Call order violates" in result


def test_record_JOL_on_missing_session_raises(store):
    with pytest.raises(AssertionError):
        tools.record_JOL("ghost", 0.5, "")


def test_record_JOL_on_closed_session_returns_closed_msg(store):
    tools.start_session("sess_1")
    tools.record_FOK("sess_1", 0.5, "")
    tools.close_session("sess_1", "done")
    result = tools.record_JOL("sess_1", 0.5, "")
    assert "is closed" in result


def test_evaluate_stop_when_high_JOL(store):
    tools.start_session("sess_1")
    tools.record_FOK("sess_1", 0.5, "")
    tools.record_JOL("sess_1", 0.9, "")
    result = tools.evaluate("sess_1")
    assert "Advice: stop" in result
    assert store.get("sess_1")["state"] == "awaiting_FOK"


def test_evaluate_retry_when_FOK_high_JOL_low(store):
    tools.start_session("sess_1")
    tools.record_FOK("sess_1", 0.8, "")
    tools.record_JOL("sess_1", 0.3, "")
    result = tools.evaluate("sess_1")
    assert "Advice: retry" in result


def test_evaluate_abort_after_3_low_JOL_rounds(store):
    tools.start_session("sess_1")
    for _ in range(3):
        tools.record_FOK("sess_1", 0.4, "")
        tools.record_JOL("sess_1", 0.3, "")
        r = tools.evaluate("sess_1")
    assert "Advice: abort" in r


def test_evaluate_budget_exhausted_suggests_stop(store):
    tools.start_session("sess_1")
    for _ in range(4):
        tools.record_FOK("sess_1", 0.7, "")
        tools.record_JOL("sess_1", 0.6, "")
        r = tools.evaluate("sess_1")
    assert "Advice: stop" in r


def test_evaluate_custom_max_attempts_changes_remaining(store):
    tools.start_session("sess_1", max_attempts=2)
    tools.record_FOK("sess_1", 0.8, "")
    tools.record_JOL("sess_1", 0.3, "")
    result = tools.evaluate("sess_1")
    assert "1 attempts remaining" in result


def test_evaluate_without_attempt_rejected(store):
    tools.start_session("sess_1")
    result = tools.evaluate("sess_1")
    assert "Call order violates" in result


def test_evaluate_always_returns_to_AWAITING_FOK(store):
    tools.start_session("sess_1")
    tools.record_FOK("sess_1", 0.5, "")
    tools.record_JOL("sess_1", 0.4, "")
    tools.evaluate("sess_1")
    assert store.get("sess_1")["state"] == "awaiting_FOK"


def test_evaluate_ambiguous_when_low_FOK_low_JOL_early_round(store):
    tools.start_session("sess_1")
    tools.record_FOK("sess_1", 0.2, "")
    tools.record_JOL("sess_1", 0.4, "")
    result = tools.evaluate("sess_1")
    assert "Advice: ambiguous" in result


def test_close_session_latches_status(store):
    tools.start_session("sess_1")
    tools.record_FOK("sess_1", 0.5, "")
    result = tools.close_session("sess_1", "user done")
    assert "closed" in result
    assert store.get("sess_1")["status"] == "closed"
    assert store.get("sess_1")["close_reason"] == "user done"


def test_close_session_already_closed_returns_note(store):
    tools.start_session("sess_1")
    tools.close_session("sess_1", "once")
    result = tools.close_session("sess_1", "twice")
    assert "already closed" in result


def test_close_session_missing_raises(store):
    with pytest.raises(AssertionError):
        tools.close_session("ghost", "x")


def test_all_tools_reject_closed_session(store):
    tools.start_session("sess_1")
    tools.record_FOK("sess_1", 0.5, "")
    tools.close_session("sess_1", "done")
    assert "is closed" in tools.record_FOK("sess_1", 0.5, "")
    assert "is closed" in tools.record_JOL("sess_1", 0.5, "")
    assert "is closed" in tools.evaluate("sess_1")
