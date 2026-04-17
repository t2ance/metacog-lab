import re
import time

SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

STATE_AWAITING_FOK = "awaiting_FOK"
STATE_AWAITING_JOL = "awaiting_JOL"
STATE_AWAITING_EVAL = "awaiting_EVAL"

DEFAULT_MAX_ATTEMPTS = 4


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, dict] = {}

    def _assert_id(self, sid: str) -> None:
        assert isinstance(sid, str) and SESSION_ID_RE.match(sid), (
            f"invalid session_id: {sid!r}"
        )

    def get(self, sid: str) -> dict | None:
        self._assert_id(sid)
        return self._sessions.get(sid)

    def create(self, sid: str, max_attempts: int = DEFAULT_MAX_ATTEMPTS) -> dict:
        self._assert_id(sid)
        assert sid not in self._sessions, f"session {sid} already exists"
        now = time.time()
        s = {
            "session_id": sid,
            "state": STATE_AWAITING_FOK,
            "status": "running",
            "attempts": [],
            "pending": None,
            "max_attempts": max_attempts,
            "created_at": now,
            "last_activity": now,
        }
        self._sessions[sid] = s
        return s

    def close(self, sid: str, reason: str) -> dict:
        s = self.get(sid)
        assert s is not None, f"session {sid} does not exist"
        assert s["status"] == "running", f"session {sid} already {s['status']}"
        s["status"] = "closed"
        s["closed_at"] = time.time()
        s["close_reason"] = reason if reason else "未说明"
        return s


# module-level singleton used by the MCP tool layer
STATE_STORE = SessionStore()
