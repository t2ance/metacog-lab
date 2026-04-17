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
        f"会话 {sid} 已关闭（原因：{s['close_reason']}）。"
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


def record_JOL(session_id: str, JOL: float, note: str = "") -> str:
    """Attempt done. Report JOL (post-attempt confidence) in [0, 1]."""
    assert 0.0 <= JOL <= 1.0, f"JOL 越界: {JOL}"
    s = STATE_STORE.get(session_id)
    assert s is not None, f"session {session_id} 不存在"
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
        "已记录本轮 JOL。\n"
        "下一步：调用 evaluate(session_id) 查看本轮应当停下、继续还是放弃。"
    )


_T_STOP_JOL = 0.80
_T_RETRY_HOPE = 0.25
_T_ABORT_MIN_ATTEMPTS = 3
_T_ABORT_AVG_JOL = 0.55


def evaluate(session_id: str) -> str:
    """Compute advice for the just-finished attempt. Always cycles state back to AWAITING_FOK."""
    s = STATE_STORE.get(session_id)
    assert s is not None, f"session {session_id} 不存在"
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
            f"建议：放弃。你已尝试 {n} 次，把握始终没有显著提升"
            f"（平均 JOL≈{avg_JOL:.2f}）。考虑告诉用户你暂时无法完成，"
            "并调 close_session(session_id, '放弃：多轮低 JOL') 结束会话。"
        )
    if JOL >= _T_STOP_JOL:
        return (
            f"建议：停下。这次答案的把握已经足够（JOL={JOL:.2f}），"
            f"可以交给用户。本次共 {n} 次尝试。"
            "交付后调 close_session(session_id, '完成') 结束会话。"
        )
    if n >= s["max_attempts"]:
        return (
            f"建议：停下（预算耗尽，已用完 {s['max_attempts']} 次）。"
            "把当前最好一版交给用户并说明局限，然后 close_session 结束。"
        )
    if (1 - JOL) * FOK >= _T_RETRY_HOPE:
        return (
            f"建议：重试。当前把握不够但仍有希望（JOL={JOL:.2f}）。"
            f"已尝试 {n} 次，还可再试 {s['max_attempts'] - n} 次。\n"
            "下一步：调 record_FOK(session_id, FOK, note) 开始新一轮。"
        )
    return (
        f"建议：模糊。当前把握不高，再试也未必显著改进（JOL={JOL:.2f}）。"
        "可以选择交付当前版并说明局限，或换一条完全不同的思路。"
        "交付后用 close_session 结束。"
    )


def close_session(session_id: str, reason: str = "") -> str:
    """Terminate session. All subsequent tool calls on this session_id will be rejected."""
    s = STATE_STORE.get(session_id)
    assert s is not None, f"session {session_id} 不存在"
    if s["status"] == "closed":
        return f"会话 {session_id} 已经是关闭状态（原因：{s['close_reason']}）。"
    effective_reason = reason if reason else "未说明"
    STATE_STORE.close(session_id, effective_reason)
    return (
        f"会话 {session_id} 已关闭（原因：{effective_reason}）。"
        "提醒将停止。"
    )
