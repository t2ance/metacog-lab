import pytest
from metacog.state import SessionStore, STATE_AWAITING_FOK


def test_create_new_session_starts_in_awaiting_FOK():
    store = SessionStore()
    s = store.create("sess_1")
    assert s["state"] == STATE_AWAITING_FOK
    assert s["status"] == "running"
    assert s["attempts"] == []
    assert s["pending"] is None
    assert s["max_attempts"] == 4


def test_create_duplicate_raises():
    store = SessionStore()
    store.create("sess_1")
    with pytest.raises(AssertionError):
        store.create("sess_1")


def test_get_returns_none_for_missing():
    store = SessionStore()
    assert store.get("ghost") is None


def test_invalid_session_id_rejected():
    store = SessionStore()
    with pytest.raises(AssertionError):
        store.get("../etc/passwd")
    with pytest.raises(AssertionError):
        store.create("")
    with pytest.raises(AssertionError):
        store.get("has space")


def test_valid_session_id_accepted():
    store = SessionStore()
    store.create("abc_123-XYZ")  # should not raise


def test_close_marks_status_and_reason():
    store = SessionStore()
    store.create("sess_1")
    s = store.close("sess_1", "done")
    assert s["status"] == "closed"
    assert s["close_reason"] == "done"
    assert "closed_at" in s


def test_close_missing_session_raises():
    store = SessionStore()
    with pytest.raises(AssertionError):
        store.close("ghost", "x")


def test_close_already_closed_raises():
    store = SessionStore()
    store.create("sess_1")
    store.close("sess_1", "once")
    with pytest.raises(AssertionError):
        store.close("sess_1", "twice")


def test_close_empty_reason_raises():
    store = SessionStore()
    store.create("sess_1")
    with pytest.raises(AssertionError):
        store.close("sess_1", "")
