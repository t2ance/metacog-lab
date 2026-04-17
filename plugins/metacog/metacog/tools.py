import time

from metacog.state import (
    STATE_STORE,
    STATE_AWAITING_FOK,
    STATE_AWAITING_JOL,
    STATE_AWAITING_EVAL,
)

_HUMAN_STATE = {
    STATE_AWAITING_FOK: "（新一轮起点，尚无本轮记录）",
    STATE_AWAITING_JOL: "record_FOK（本轮事前评估已记录）",
    STATE_AWAITING_EVAL: "record_JOL（本轮事后评估已记录）",
}
_EXPECTED_NEXT = {
    STATE_AWAITING_FOK: "record_FOK（本轮开始前的事前把握评估）",
    STATE_AWAITING_JOL: "record_JOL（做完题后上报事后评估）",
    STATE_AWAITING_EVAL: "evaluate（查看是否继续/停下/放弃）",
}
_CALL_DESC = {
    "record_FOK": "record_FOK（事前把握评估）",
    "record_JOL": "record_JOL（事后把握评估）",
    "evaluate": "evaluate（查看下一步建议）",
    "close_session": "close_session（结束会话）",
}


def _reject(current_call: str, state: str) -> str:
    return (
        "调用顺序不符合元认知流程。\n"
        f"  你上一步：{_HUMAN_STATE[state]}\n"
        f"  下一步应该是：{_EXPECTED_NEXT[state]}\n"
        f"  而你现在调用的是：{_CALL_DESC[current_call]}\n"
        "请按 FOK → 解题 → JOL → evaluate 的顺序调用。"
    )


def _closed_msg(sid: str, s: dict) -> str:
    return (
        f"会话 {sid} 已关闭（原因：{s.get('close_reason', '未说明')}）。"
        "请使用新的 session_id 开启新会话。"
    )


def record_FOK(session_id: str, FOK: float, note: str = "") -> str:
    """New round begins. Report FOK (pre-attempt confidence) in [0, 1]."""
    assert 0.0 <= FOK <= 1.0, f"FOK 越界: {FOK}"
    s = STATE_STORE.get(session_id)
    if s is None:
        s = STATE_STORE.create(session_id)
    if s["status"] == "closed":
        return _closed_msg(session_id, s)
    if s["state"] != STATE_AWAITING_FOK:
        return _reject("record_FOK", s["state"])
    s["pending"] = {"FOK": FOK, "note_fok": note, "fok_ts": time.time()}
    s["state"] = STATE_AWAITING_JOL
    s["last_activity"] = time.time()
    return (
        "已记录本轮 FOK。\n"
        "下一步：开始解题。完成后调用 record_JOL(session_id, JOL, note) "
        "上报对这版答案的事后把握。"
    )
