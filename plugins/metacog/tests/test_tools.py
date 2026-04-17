import pytest
from metacog.state import SessionStore, STATE_AWAITING_JOL, STATE_AWAITING_FOK
from metacog import tools


@pytest.fixture
def store(monkeypatch):
    fresh = SessionStore()
    monkeypatch.setattr(tools, "STATE_STORE", fresh)
    return fresh


def test_record_FOK_creates_session_on_first_call(store):
    result = tools.record_FOK("sess_1", 0.7, "some note")
    assert "已记录本轮 FOK" in result
    s = store.get("sess_1")
    assert s is not None
    assert s["state"] == STATE_AWAITING_JOL
    assert s["pending"]["FOK"] == 0.7
    assert s["pending"]["note_fok"] == "some note"


def test_record_FOK_out_of_range_raises(store):
    with pytest.raises(AssertionError):
        tools.record_FOK("sess_1", 1.5, "")
    with pytest.raises(AssertionError):
        tools.record_FOK("sess_2", -0.01, "")


def test_record_FOK_twice_in_a_row_returns_reject(store):
    tools.record_FOK("sess_1", 0.5, "")
    result = tools.record_FOK("sess_1", 0.6, "")
    assert "顺序不符合" in result
    assert "record_FOK" in result


def test_record_FOK_on_closed_session_returns_closed_msg(store):
    store.create("sess_1")
    store.close("sess_1", "done")
    result = tools.record_FOK("sess_1", 0.5, "")
    assert "已关闭" in result


def test_record_JOL_records_attempt(store):
    tools.record_FOK("sess_1", 0.7, "fok note")
    result = tools.record_JOL("sess_1", 0.5, "jol note")
    assert "已记录本轮 JOL" in result
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
    tools.record_FOK("sess_1", 0.5, "")
    with pytest.raises(AssertionError):
        tools.record_JOL("sess_1", 1.5, "")


def test_record_JOL_without_FOK_returns_reject(store):
    store.create("sess_1")  # direct create, leaves in AWAITING_FOK
    result = tools.record_JOL("sess_1", 0.5, "")
    assert "顺序不符合" in result


def test_record_JOL_on_missing_session_raises(store):
    with pytest.raises(AssertionError):
        tools.record_JOL("ghost", 0.5, "")


def test_record_JOL_on_closed_session_returns_closed_msg(store):
    tools.record_FOK("sess_1", 0.5, "")
    store.close("sess_1", "done")
    result = tools.record_JOL("sess_1", 0.5, "")
    assert "已关闭" in result


def test_evaluate_stop_when_high_JOL(store):
    tools.record_FOK("sess_1", 0.5, "")
    tools.record_JOL("sess_1", 0.9, "")
    result = tools.evaluate("sess_1")
    assert "建议：停下" in result
    assert store.get("sess_1")["state"] == "awaiting_FOK"


def test_evaluate_retry_when_FOK_high_JOL_low(store):
    tools.record_FOK("sess_1", 0.8, "")
    tools.record_JOL("sess_1", 0.3, "")
    result = tools.evaluate("sess_1")
    assert "建议：重试" in result


def test_evaluate_abort_after_3_low_JOL_rounds(store):
    for _ in range(3):
        tools.record_FOK("sess_1", 0.4, "")
        tools.record_JOL("sess_1", 0.3, "")
        r = tools.evaluate("sess_1")
    assert "建议：放弃" in r


def test_evaluate_budget_exhausted_suggests_stop(store):
    for _ in range(4):
        tools.record_FOK("sess_1", 0.7, "")
        tools.record_JOL("sess_1", 0.6, "")
        r = tools.evaluate("sess_1")
    assert "建议：停下" in r


def test_evaluate_without_attempt_rejected(store):
    store.create("sess_1")
    result = tools.evaluate("sess_1")
    assert "顺序不符合" in result


def test_evaluate_always_returns_to_AWAITING_FOK(store):
    tools.record_FOK("sess_1", 0.5, "")
    tools.record_JOL("sess_1", 0.4, "")
    tools.evaluate("sess_1")
    assert store.get("sess_1")["state"] == "awaiting_FOK"
