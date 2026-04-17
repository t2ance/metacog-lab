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
