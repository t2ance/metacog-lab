# Metacognition MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a Claude Code plugin (`metacog`) that exposes a metacognition MCP with FOK/JOL/evaluate/close_session tools and an `UserPromptSubmit` hook that periodically reminds the model to touch or close open sessions.

**Architecture:** Three-state in-memory FSM (AWAITING_FOK → AWAITING_JOL → AWAITING_EVAL → loop) with a CLOSED latch. State lives in the MCP server process only. A separate hook script parses the CC transcript (stdin-JSON protocol), does turn-count gating identical to CC's TodoList mechanism (10/10 thresholds), and emits `additionalContext` with open-session snapshot. Distribution: monorepo marketplace with one plugin per MCP.

**Tech Stack:** Python 3.10+, `mcp` SDK (FastMCP), `pytest`. No external state (no disk, no db).

---

## Architectural Assumptions (verify with user before/during execution)

| # | Assumption | Source | How to flip |
|---|---|---|---|
| A1 | Many future metacog-style MCPs expected | User: "我们可能会做很多类似的 MCP" | If only ever one MCP, collapse to single-plugin repo (drop marketplace wrapper) |
| A2 | MCP must be bundled with CC plugin (not standalone pip package) | Reminder requires CC hook = CC-specific | If cross-host support wanted later, split MCP into pip package, keep CC plugin as hook-only wrapper |
| A3 | `${CLAUDE_PLUGIN_ROOT}` variable available in plugin.json command/args strings | [inferred, not verified in source] | If unsupported, replace with absolute path at install time via README instructions |
| A4 | Thresholds 10/10 good default | Mirrors `TODO_REMINDER_CONFIG` [verified src/utils/attachments.ts:254-257] | Edit constants in `reminder/entry.py` |

---

## Verified Facts Grounding This Plan

- **plugin.json `mcpServers` field** [verified src/utils/plugins/schemas.ts:543-570] — inline dict accepted: `{"server-name": {command, args, env?}}`
- **Stdio MCP server config** [verified src/services/mcp/types.ts:28-35] — `{type?: "stdio", command, args[], env?}`
- **Hook stdin input** [verified src/entrypoints/sdk/coreSchemas.ts:387-411] — hook receives JSON via stdin with `session_id`, `transcript_path`, `cwd`, `permission_mode?`, `agent_id?`, `agent_type?`
- **Hook stdout output** [verified src/entrypoints/sdk/coreSchemas.ts:812] — `{additionalContext: string}` wraps into `<system-reminder>` by CC core
- **Reminder thresholds convention** [verified src/utils/attachments.ts:254-257] — CC uses `TURNS_SINCE_WRITE=10`, `TURNS_BETWEEN_REMINDERS=10` for TodoList
- **Reminder template structure** [verified src/utils/messages.ts:3680-3699] — preamble + "NEVER mention to user" + dynamic snapshot
- **Marketplace structure** [verified marketplace_repo_correct_format memory] — `.claude-plugin/` contains ONLY `marketplace.json`; plugin code under `plugins/<name>/`

---

## File Structure

```
metacog-lab/                              ← repo root
  .claude-plugin/
    marketplace.json                      ← marketplace index, references ./plugins/metacog
  plugins/
    metacog/
      .claude-plugin/
        plugin.json                       ← declares mcpServers + hooks
      metacog/                            ← Python package for MCP server
        __init__.py
        state.py                          ← SessionStore (pure, no MCP dep)
        tools.py                          ← 4 tool impls (pure, no MCP dep)
        server.py                         ← FastMCP wiring, entry point
      reminder/                           ← Python package for hook
        __init__.py
        parser.py                         ← transcript parser (pure)
        entry.py                          ← hook entry (stdin/stdout adapter)
      tests/
        __init__.py
        test_state.py
        test_tools.py
        test_parser.py
      pyproject.toml                      ← deps: mcp, pytest (dev)
      README.md                           ← install + usage
  docs/superpowers/plans/
    2026-04-17-metacog-mcp.md             ← this plan
  README.md                               ← marketplace-level readme
  .gitignore
```

File responsibility one-liners:
- `state.py`: in-memory session store, FSM state constants, session_id validation. No external deps.
- `tools.py`: 4 pure functions implementing tool logic; returns human-language strings.
- `server.py`: imports pure logic + FastMCP; registers tools; runs stdio server.
- `parser.py`: JSONL transcript scanner; counts turns and collects open sessions. Pure.
- `entry.py`: reads stdin JSON, invokes parser, emits additionalContext stdout.

---

## Task 0: Repo Skeleton

**Files:**
- Create: `/data1/peijia/projects/metacog-lab/README.md`
- Create: `/data1/peijia/projects/metacog-lab/.gitignore`
- Create: `/data1/peijia/projects/metacog-lab/.claude-plugin/marketplace.json`
- Create: `/data1/peijia/projects/metacog-lab/plugins/metacog/pyproject.toml`
- Create: `/data1/peijia/projects/metacog-lab/plugins/metacog/README.md`
- Create: `/data1/peijia/projects/metacog-lab/plugins/metacog/metacog/__init__.py` (empty)
- Create: `/data1/peijia/projects/metacog-lab/plugins/metacog/reminder/__init__.py` (empty)
- Create: `/data1/peijia/projects/metacog-lab/plugins/metacog/tests/__init__.py` (empty)

- [ ] **Step 1: Create directory tree**

```bash
mkdir -p /data1/peijia/projects/metacog-lab/.claude-plugin
mkdir -p /data1/peijia/projects/metacog-lab/plugins/metacog/.claude-plugin
mkdir -p /data1/peijia/projects/metacog-lab/plugins/metacog/metacog
mkdir -p /data1/peijia/projects/metacog-lab/plugins/metacog/reminder
mkdir -p /data1/peijia/projects/metacog-lab/plugins/metacog/tests
```

- [ ] **Step 2: Write top-level `.gitignore`**

```
__pycache__/
*.pyc
.pytest_cache/
.venv/
.mypy_cache/
*.egg-info/
dist/
build/
```

- [ ] **Step 3: Write top-level `README.md`**

```markdown
# metacog-lab

Claude Code marketplace for metacognition-style MCP plugins.

## Plugins

- [metacog](plugins/metacog/) — FOK/JOL metacognitive loop with periodic reminders.

## Install

Add this repo to Claude Code as a marketplace:

    /plugin marketplace add <this-repo-url>
    /plugin install metacog@metacog-lab
```

- [ ] **Step 4: Write `.claude-plugin/marketplace.json`**

```json
{
  "name": "metacog-lab",
  "owner": {"name": "peijia"},
  "plugins": [
    {
      "name": "metacog",
      "source": "./plugins/metacog",
      "description": "Metacognitive FOK/JOL loop MCP with periodic open-session reminders."
    }
  ]
}
```

- [ ] **Step 5: Write `plugins/metacog/pyproject.toml`**

```toml
[project]
name = "metacog"
version = "0.1.0"
description = "FOK/JOL metacognitive loop MCP"
requires-python = ">=3.10"
dependencies = [
  "mcp>=1.0"
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 6: Write `plugins/metacog/README.md`**

```markdown
# metacog plugin

Metacognitive loop MCP: model reports FOK before attempt, JOL after, calls evaluate to decide retry/stop/abort, uses close_session to end.

## State machine

    AWAITING_FOK -> record_FOK -> AWAITING_JOL -> record_JOL -> AWAITING_EVAL -> evaluate -> AWAITING_FOK ...

Agent may call `close_session(session_id, reason)` in any running state to terminate. CLOSED is a latch — all further tool calls on that session_id are rejected.

## Reminder

A `UserPromptSubmit` hook fires each user turn. If no metacog tool has been called for 10 assistant turns AND no reminder has been injected for 10 assistant turns AND at least one open session exists, the hook injects a `<system-reminder>` listing open sessions.

## Tools

- `record_FOK(session_id, FOK, note)` — call before solving. FOK in [0, 1].
- `record_JOL(session_id, JOL, note)` — call after solving. JOL in [0, 1].
- `evaluate(session_id)` — returns human-language advice; state always returns to AWAITING_FOK.
- `close_session(session_id, reason)` — latch session as CLOSED.
```

- [ ] **Step 7: Touch empty `__init__.py` files**

```bash
touch /data1/peijia/projects/metacog-lab/plugins/metacog/metacog/__init__.py
touch /data1/peijia/projects/metacog-lab/plugins/metacog/reminder/__init__.py
touch /data1/peijia/projects/metacog-lab/plugins/metacog/tests/__init__.py
```

- [ ] **Step 8: Commit**

```bash
cd /data1/peijia/projects/metacog-lab
git init
git add -A
git commit -m "chore: bootstrap metacog-lab marketplace skeleton"
```

---

## Task 1: SessionStore (pure FSM core, TDD)

**Files:**
- Create: `plugins/metacog/metacog/state.py`
- Test: `plugins/metacog/tests/test_state.py`

- [ ] **Step 1: Write the failing tests**

Create `plugins/metacog/tests/test_state.py`:

```python
import pytest
from metacog.state import (
    SessionStore,
    STATE_AWAITING_FOK,
    STATE_AWAITING_JOL,
    STATE_AWAITING_EVAL,
)


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


def test_close_with_empty_reason_defaults():
    store = SessionStore()
    store.create("sess_1")
    s = store.close("sess_1", "")
    assert s["close_reason"] == "未说明"
```

- [ ] **Step 2: Run tests, confirm all fail**

```bash
cd /data1/peijia/projects/metacog-lab/plugins/metacog
pytest tests/test_state.py -v
```

Expected: `ModuleNotFoundError: No module named 'metacog.state'` or all tests fail.

- [ ] **Step 3: Write `metacog/state.py`**

```python
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
```

- [ ] **Step 4: Run tests, confirm all pass**

```bash
pytest tests/test_state.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add plugins/metacog/metacog/state.py plugins/metacog/tests/test_state.py
git commit -m "feat(metacog): add SessionStore pure FSM core with session_id validation"
```

---

## Task 2: record_FOK tool (TDD)

**Files:**
- Create: `plugins/metacog/metacog/tools.py`
- Extend: `plugins/metacog/tests/test_tools.py`

- [ ] **Step 1: Write failing tests for record_FOK**

Create `plugins/metacog/tests/test_tools.py`:

```python
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
```

- [ ] **Step 2: Run tests, confirm fail**

```bash
pytest tests/test_tools.py::test_record_FOK_creates_session_on_first_call -v
```

Expected: import error (tools module not yet created).

- [ ] **Step 3: Write `metacog/tools.py` (record_FOK only)**

```python
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
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
pytest tests/test_tools.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add plugins/metacog/metacog/tools.py plugins/metacog/tests/test_tools.py
git commit -m "feat(metacog): add record_FOK tool with state-machine and range validation"
```

---

## Task 3: record_JOL tool (TDD)

**Files:**
- Modify: `plugins/metacog/metacog/tools.py`
- Extend: `plugins/metacog/tests/test_tools.py`

- [ ] **Step 1: Append failing tests for record_JOL**

Append to `plugins/metacog/tests/test_tools.py`:

```python
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
```

- [ ] **Step 2: Run tests, confirm fail**

```bash
pytest tests/test_tools.py::test_record_JOL_records_attempt -v
```

Expected: `AttributeError: module 'metacog.tools' has no attribute 'record_JOL'`.

- [ ] **Step 3: Append record_JOL to `metacog/tools.py`**

```python
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
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
pytest tests/test_tools.py -v
```

Expected: 9 passed total.

- [ ] **Step 5: Commit**

```bash
git add plugins/metacog/metacog/tools.py plugins/metacog/tests/test_tools.py
git commit -m "feat(metacog): add record_JOL tool"
```

---

## Task 4: evaluate tool (TDD)

**Files:**
- Modify: `plugins/metacog/metacog/tools.py`
- Extend: `plugins/metacog/tests/test_tools.py`

- [ ] **Step 1: Append failing tests for evaluate**

Append to `plugins/metacog/tests/test_tools.py`:

```python
def test_evaluate_stop_when_high_JOL(store):
    tools.record_FOK("sess_1", 0.5, "")
    tools.record_JOL("sess_1", 0.9, "")  # JOL >= 0.8 => stop
    result = tools.evaluate("sess_1")
    assert "建议：停下" in result
    assert store.get("sess_1")["state"] == "awaiting_FOK"  # always cycles back


def test_evaluate_retry_when_FOK_high_JOL_low(store):
    tools.record_FOK("sess_1", 0.8, "")
    tools.record_JOL("sess_1", 0.3, "")  # (1-0.3)*0.8 = 0.56 >= 0.25 => retry
    result = tools.evaluate("sess_1")
    assert "建议：重试" in result


def test_evaluate_abort_after_3_low_JOL_rounds(store):
    for _ in range(3):
        tools.record_FOK("sess_1", 0.4, "")
        tools.record_JOL("sess_1", 0.3, "")
        r = tools.evaluate("sess_1")
    assert "建议：放弃" in r


def test_evaluate_budget_exhausted_suggests_stop(store):
    # max_attempts default is 4, fill 4 non-stop-not-abort rounds
    for _ in range(4):
        tools.record_FOK("sess_1", 0.7, "")
        tools.record_JOL("sess_1", 0.6, "")  # JOL<0.8, not abort (avg>0.55)
        r = tools.evaluate("sess_1")
    assert "建议：停下" in r  # budget_exhausted path


def test_evaluate_without_attempt_rejected(store):
    store.create("sess_1")
    result = tools.evaluate("sess_1")
    assert "顺序不符合" in result


def test_evaluate_always_returns_to_AWAITING_FOK(store):
    tools.record_FOK("sess_1", 0.5, "")
    tools.record_JOL("sess_1", 0.4, "")
    tools.evaluate("sess_1")
    assert store.get("sess_1")["state"] == "awaiting_FOK"
```

- [ ] **Step 2: Run tests, confirm fail**

```bash
pytest tests/test_tools.py::test_evaluate_stop_when_high_JOL -v
```

Expected: `AttributeError` for evaluate.

- [ ] **Step 3: Append evaluate to `metacog/tools.py`**

```python
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
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
pytest tests/test_tools.py -v
```

Expected: 15 passed total.

- [ ] **Step 5: Commit**

```bash
git add plugins/metacog/metacog/tools.py plugins/metacog/tests/test_tools.py
git commit -m "feat(metacog): add evaluate tool with stop/retry/abort/budget branches"
```

---

## Task 5: close_session tool (TDD)

**Files:**
- Modify: `plugins/metacog/metacog/tools.py`
- Extend: `plugins/metacog/tests/test_tools.py`

- [ ] **Step 1: Append failing tests**

Append to `plugins/metacog/tests/test_tools.py`:

```python
def test_close_session_latches_status(store):
    tools.record_FOK("sess_1", 0.5, "")
    result = tools.close_session("sess_1", "user done")
    assert "已关闭" in result
    assert store.get("sess_1")["status"] == "closed"
    assert store.get("sess_1")["close_reason"] == "user done"


def test_close_session_already_closed_returns_note(store):
    tools.record_FOK("sess_1", 0.5, "")
    tools.close_session("sess_1", "once")
    result = tools.close_session("sess_1", "twice")
    assert "已经是关闭状态" in result


def test_close_session_missing_raises(store):
    with pytest.raises(AssertionError):
        tools.close_session("ghost", "x")


def test_all_tools_reject_closed_session(store):
    tools.record_FOK("sess_1", 0.5, "")
    tools.close_session("sess_1", "done")
    assert "已关闭" in tools.record_FOK("sess_1", 0.5, "")
    assert "已关闭" in tools.record_JOL("sess_1", 0.5, "")
    assert "已关闭" in tools.evaluate("sess_1")
```

- [ ] **Step 2: Run tests, confirm fail**

```bash
pytest tests/test_tools.py::test_close_session_latches_status -v
```

Expected: `AttributeError` for close_session.

- [ ] **Step 3: Append close_session to `metacog/tools.py`**

```python
def close_session(session_id: str, reason: str = "") -> str:
    """Terminate session. All subsequent tool calls on this session_id will be rejected."""
    s = STATE_STORE.get(session_id)
    assert s is not None, f"session {session_id} 不存在"
    if s["status"] == "closed":
        return f"会话 {session_id} 已经是关闭状态（原因：{s.get('close_reason', '未说明')}）。"
    STATE_STORE.close(session_id, reason)
    return (
        f"会话 {session_id} 已关闭（原因：{reason or '未说明'}）。"
        "提醒将停止。"
    )
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
pytest tests/test_tools.py -v
```

Expected: 19 passed total.

- [ ] **Step 5: Commit**

```bash
git add plugins/metacog/metacog/tools.py plugins/metacog/tests/test_tools.py
git commit -m "feat(metacog): add close_session tool and latch-on-closed check"
```

---

## Task 6: MCP server entry (FastMCP wiring)

**Files:**
- Create: `plugins/metacog/metacog/server.py`

No unit test — smoke test in Task 10.

- [ ] **Step 1: Write `metacog/server.py`**

```python
"""MCP server entry point. Run as: python3 path/to/server.py (stdio MCP)."""
import sys
from pathlib import Path

# Allow running the file directly without install: add plugin root to sys.path
_plugin_root = Path(__file__).resolve().parent.parent
if str(_plugin_root) not in sys.path:
    sys.path.insert(0, str(_plugin_root))

from mcp.server.fastmcp import FastMCP

from metacog import tools

app = FastMCP("metacog")


@app.tool()
def record_FOK(session_id: str, FOK: float, note: str = "") -> str:
    """Before solving this round: report FOK (pre-attempt confidence, [0,1])."""
    return tools.record_FOK(session_id, FOK, note)


@app.tool()
def record_JOL(session_id: str, JOL: float, note: str = "") -> str:
    """After solving this round: report JOL (post-attempt confidence, [0,1])."""
    return tools.record_JOL(session_id, JOL, note)


@app.tool()
def evaluate(session_id: str) -> str:
    """Decide stop/retry/abort for the just-completed round. Cycles state back to AWAITING_FOK."""
    return tools.evaluate(session_id)


@app.tool()
def close_session(session_id: str, reason: str = "") -> str:
    """Terminate the session. Further calls on this session_id are rejected."""
    return tools.close_session(session_id, reason)


if __name__ == "__main__":
    app.run()
```

- [ ] **Step 2: Import-check the module**

```bash
cd /data1/peijia/projects/metacog-lab/plugins/metacog
python3 -c "from metacog import server; print('ok', [t for t in dir(server) if not t.startswith('_')])"
```

Expected: `ok [...]` with no ImportError.

- [ ] **Step 3: Dry-run the server binary (no input, exits immediately or blocks on stdin)**

```bash
timeout 2 python3 metacog/server.py < /dev/null ; echo "exit=$?"
```

Expected: exits within 2 seconds (124 from timeout or 0) with no traceback on stderr.

- [ ] **Step 4: Commit**

```bash
git add plugins/metacog/metacog/server.py
git commit -m "feat(metacog): wire FastMCP server entry with 4 tools"
```

---

## Task 7: Transcript parser (TDD)

**Files:**
- Create: `plugins/metacog/reminder/parser.py`
- Create: `plugins/metacog/tests/test_parser.py`

- [ ] **Step 1: Write failing tests**

Create `plugins/metacog/tests/test_parser.py`:

```python
import json
import pytest
from reminder.parser import parse_transcript, REMINDER_MARKER, MCP_TOOL_PREFIX


def _assistant_msg(tool_name: str, tool_input: dict) -> str:
    return json.dumps({
        "role": "assistant",
        "content": [{"type": "tool_use", "name": tool_name, "input": tool_input}],
    })


def _user_text(text: str) -> str:
    return json.dumps({
        "role": "user",
        "content": [{"type": "text", "text": text}],
    })


def _assistant_plain(text: str) -> str:
    return json.dumps({
        "role": "assistant",
        "content": [{"type": "text", "text": text}],
    })


def test_empty_transcript_has_no_open_sessions():
    r = parse_transcript([])
    assert r.open_session_ids == []
    assert r.turns_since_mcp == 0
    assert r.turns_since_reminder == 0


def test_detects_open_session_from_record_FOK():
    lines = [_assistant_msg("metacog.record_FOK", {"session_id": "s1", "FOK": 0.5})]
    r = parse_transcript(lines)
    assert r.open_session_ids == ["s1"]
    assert r.turns_since_mcp == 0  # current turn has the call


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


def test_malformed_jsonl_line_skipped():
    lines = [
        "not json at all",
        _assistant_msg("metacog.record_FOK", {"session_id": "s1", "FOK": 0.5}),
        "",
    ]
    r = parse_transcript(lines)
    assert r.open_session_ids == ["s1"]


def test_non_metacog_tool_use_ignored():
    lines = [
        _assistant_msg("Read", {"file_path": "/etc/hosts"}),
        _assistant_plain("turn"),
    ]
    r = parse_transcript(lines)
    assert r.open_session_ids == []
    assert r.turns_since_mcp == 2  # both assistant turns count
```

- [ ] **Step 2: Run tests, confirm fail**

```bash
pytest tests/test_parser.py -v
```

Expected: `ModuleNotFoundError: No module named 'reminder.parser'`.

- [ ] **Step 3: Write `reminder/parser.py`**

```python
"""Pure transcript parser for metacog reminder hook.

Reads Claude Code session JSONL transcript lines (reverse chronological
scan), reports:
  - turns_since_mcp: assistant turns since the most recent metacog.* tool_use
  - turns_since_reminder: assistant turns since the most recent reminder marker
  - open_session_ids: session_ids with a recent metacog.* call and no later close_session
"""
import json
from dataclasses import dataclass, field

REMINDER_MARKER = "[metacog_reminder]"
MCP_TOOL_PREFIX = "metacog."


@dataclass
class ParseResult:
    turns_since_mcp: int = 0
    turns_since_reminder: int = 0
    open_session_ids: list[str] = field(default_factory=list)


def _extract_text(content_blocks) -> str:
    if not isinstance(content_blocks, list):
        return ""
    out = []
    for block in content_blocks:
        if isinstance(block, dict) and block.get("type") == "text":
            out.append(block.get("text", ""))
        elif isinstance(block, str):
            out.append(block)
    return "".join(out)


def parse_transcript(lines: list[str]) -> ParseResult:
    turns_since_mcp = 0
    turns_since_reminder = 0
    seen_mcp = False
    seen_reminder = False
    closed_ids: set[str] = set()
    # preserve insertion order; we see "most recent" first by reverse walk
    open_sessions: dict[str, None] = {}

    for raw in reversed(lines):
        if not raw or not raw.strip():
            continue
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue

        role = msg.get("role") or msg.get("type")
        content = msg.get("content", [])
        if not isinstance(content, list):
            content = [content]

        if role == "assistant":
            has_metacog_call = False
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") != "tool_use":
                    continue
                name = block.get("name", "")
                if not name.startswith(MCP_TOOL_PREFIX):
                    continue
                has_metacog_call = True
                tool_short = name[len(MCP_TOOL_PREFIX):]
                inp = block.get("input") or {}
                sid = inp.get("session_id")
                if not sid:
                    continue
                if tool_short == "close_session":
                    closed_ids.add(sid)
                elif sid not in closed_ids and sid not in open_sessions:
                    open_sessions[sid] = None
            if has_metacog_call and not seen_mcp:
                seen_mcp = True
            if not seen_mcp:
                turns_since_mcp += 1
            if not seen_reminder:
                turns_since_reminder += 1
        elif role == "user":
            text = _extract_text(content)
            if REMINDER_MARKER in text and not seen_reminder:
                seen_reminder = True

        if seen_mcp and seen_reminder:
            break

    open_ids = [sid for sid in open_sessions if sid not in closed_ids]
    return ParseResult(
        turns_since_mcp=turns_since_mcp,
        turns_since_reminder=turns_since_reminder,
        open_session_ids=open_ids,
    )
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
pytest tests/test_parser.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add plugins/metacog/reminder/parser.py plugins/metacog/tests/test_parser.py
git commit -m "feat(reminder): pure transcript parser with turn-count + open-session tracking"
```

---

## Task 8: Hook entry (stdin/stdout adapter)

**Files:**
- Create: `plugins/metacog/reminder/entry.py`

No unit test; exercised in Task 10 smoke.

- [ ] **Step 1: Write `reminder/entry.py`**

```python
#!/usr/bin/env python3
"""UserPromptSubmit hook entry. Reads CC hook payload from stdin, emits additionalContext.

Thresholds mirror CC's TodoList reminder (verified attachments.ts:254-257):
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

    lines = p.read_text().splitlines()
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
```

- [ ] **Step 2: Verify import**

```bash
cd /data1/peijia/projects/metacog-lab/plugins/metacog
python3 -c "from reminder import entry; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Simulate a no-op stdin payload (no transcript_path)**

```bash
echo '{"session_id":"x","transcript_path":"","cwd":"/tmp"}' | python3 reminder/entry.py
echo "exit=$?"
```

Expected: no stdout output, exit=0.

- [ ] **Step 4: Commit**

```bash
git add plugins/metacog/reminder/entry.py
git commit -m "feat(reminder): stdin/stdout hook entry with 10/10 threshold gating"
```

---

## Task 9: plugin.json + integration with CC plugin system

**Files:**
- Create: `plugins/metacog/.claude-plugin/plugin.json`

- [ ] **Step 1: Write `plugin.json`**

```json
{
  "name": "metacog",
  "version": "0.1.0",
  "description": "Metacognitive FOK/JOL loop MCP with periodic open-session reminder.",
  "mcpServers": {
    "metacog": {
      "command": "python3",
      "args": ["${CLAUDE_PLUGIN_ROOT}/metacog/server.py"]
    }
  },
  "hooks": {
    "UserPromptSubmit": [
      {
        "matchers": [],
        "commands": ["python3 ${CLAUDE_PLUGIN_ROOT}/reminder/entry.py"]
      }
    ]
  }
}
```

- [ ] **Step 2: Verify plugin.json JSON validity**

```bash
python3 -c "import json; json.load(open('/data1/peijia/projects/metacog-lab/plugins/metacog/.claude-plugin/plugin.json')); print('valid')"
```

Expected: `valid`.

- [ ] **Step 3: Verify `${CLAUDE_PLUGIN_ROOT}` substitution assumption**

Run a CC source grep to confirm support:

```bash
cd /data1/peijia/projects/claude-code-main
grep -rn "CLAUDE_PLUGIN_ROOT" src/ | head -20
```

If `CLAUDE_PLUGIN_ROOT` is found, move on. If NOT found, replace with relative paths and document that hook/mcp must be invoked from plugin root — OR require absolute paths in install docs.

- [ ] **Step 4: Commit**

```bash
git add plugins/metacog/.claude-plugin/plugin.json
git commit -m "feat(plugin): declare metacog MCP server + UserPromptSubmit hook in plugin.json"
```

---

## Task 10: End-to-end smoke test

**Files:**
- Create: `plugins/metacog/tests/smoke_e2e.sh`

- [ ] **Step 1: Write smoke script**

```bash
#!/usr/bin/env bash
# Smoke test: drive the MCP through a full FOK->JOL->evaluate->close cycle
# using the pure tools module directly (no MCP protocol overhead).
set -euo pipefail

cd "$(dirname "$0")/.."

python3 <<'PY'
from metacog import tools

print("1. record_FOK:")
print(tools.record_FOK("smoke_1", 0.7, "fok note"))
print()

print("2. record_JOL:")
print(tools.record_JOL("smoke_1", 0.9, "jol note"))
print()

print("3. evaluate:")
print(tools.evaluate("smoke_1"))
print()

print("4. close_session:")
print(tools.close_session("smoke_1", "完成"))
print()

print("5. attempt after close (should be rejected):")
print(tools.record_FOK("smoke_1", 0.5, ""))
PY
```

- [ ] **Step 2: Make executable and run**

```bash
chmod +x /data1/peijia/projects/metacog-lab/plugins/metacog/tests/smoke_e2e.sh
/data1/peijia/projects/metacog-lab/plugins/metacog/tests/smoke_e2e.sh
```

Expected output contains: `已记录本轮 FOK`, `已记录本轮 JOL`, `建议：停下`, `已关闭`, `已关闭` (final rejection).

- [ ] **Step 3: Run the reminder parser against a synthetic transcript**

```bash
cat > /tmp/fake_transcript.jsonl <<'EOF'
{"role":"assistant","content":[{"type":"tool_use","name":"metacog.record_FOK","input":{"session_id":"s1","FOK":0.7}}]}
{"role":"assistant","content":[{"type":"text","text":"turn 1"}]}
{"role":"assistant","content":[{"type":"text","text":"turn 2"}]}
EOF

cd /data1/peijia/projects/metacog-lab/plugins/metacog
python3 -c "
from reminder.parser import parse_transcript
with open('/tmp/fake_transcript.jsonl') as f:
    r = parse_transcript(f.read().splitlines())
print(r)
"
```

Expected: `ParseResult(turns_since_mcp=2, turns_since_reminder=3, open_session_ids=['s1'])`.

- [ ] **Step 4: Run full pytest suite**

```bash
cd /data1/peijia/projects/metacog-lab/plugins/metacog
pytest -v
```

Expected: all 26 tests pass (9 state + 12 tools + 5 parser — numbers may adjust based on earlier additions).

- [ ] **Step 5: Commit**

```bash
git add plugins/metacog/tests/smoke_e2e.sh
git commit -m "test(metacog): add end-to-end smoke covering full FSM cycle"
```

---

## Task 11: Distribution README and installation guide

**Files:**
- Modify: `plugins/metacog/README.md`
- Modify: `README.md` (repo root)

- [ ] **Step 1: Overwrite `plugins/metacog/README.md` with install instructions**

```markdown
# metacog plugin

Metacognitive FOK/JOL loop MCP for Claude Code with periodic reminders for open sessions.

## Install

Option A — via marketplace (recommended once the repo is published):

    /plugin marketplace add https://github.com/<you>/metacog-lab
    /plugin install metacog@metacog-lab

Option B — local development:

    cd /data1/peijia/projects/metacog-lab
    /plugin marketplace add $(pwd)
    /plugin install metacog@metacog-lab

## Requirements

- Python 3.10+
- `mcp` Python SDK (`pip install mcp`)

## Usage

After install, four tools become available in Claude Code as `metacog.*`:

- `metacog.record_FOK(session_id, FOK, note)` — before solving each round
- `metacog.record_JOL(session_id, JOL, note)` — after solving each round
- `metacog.evaluate(session_id)` — get stop/retry/abort advice
- `metacog.close_session(session_id, reason)` — terminate session

The `UserPromptSubmit` hook periodically reminds the agent about open (non-closed) sessions that haven't been touched in 10 assistant turns.

## Thresholds

Edit `reminder/entry.py`:

    TURNS_SINCE_MCP = 10
    TURNS_BETWEEN_REMINDERS = 10

Edit `metacog/tools.py`:

    _T_STOP_JOL = 0.80
    _T_RETRY_HOPE = 0.25
    _T_ABORT_MIN_ATTEMPTS = 3
    _T_ABORT_AVG_JOL = 0.55

## Tests

    cd plugins/metacog
    pip install -e ".[dev]"
    pytest -v
```

- [ ] **Step 2: Commit**

```bash
git add plugins/metacog/README.md README.md
git commit -m "docs: install + usage + threshold tuning instructions"
```

---

## Self-Review (performed after writing the plan)

**Spec coverage:**

- 3-state loop FSM → Task 1 (state.py), Tasks 2-4 (tools)
- In-memory only → Task 1 (no file I/O)
- 4 tools (record_FOK / record_JOL / evaluate / close_session) → Tasks 2-5
- CLOSED latch (not a FSM state) → Task 5 (close_session sets `status`, not `state`)
- Out-of-order rejection with 4-section message → Task 2+ (`_reject` helper, tested)
- Range assertion on FOK/JOL → Task 2, 3 (tested)
- session_id validation (no path traversal) → Task 1 (tested)
- Hook with 10/10 thresholds → Task 7 (parser) + Task 8 (entry)
- plugin.json bundling MCP + hook → Task 9
- Marketplace monorepo structure → Task 0

**Placeholder scan:** All tasks have exact code blocks; no "TBD" / "similar to Task N" / "add error handling" placeholders.

**Type consistency:** All tool names match (`record_FOK`, `record_JOL`, `evaluate`, `close_session`). State constants use `STATE_AWAITING_FOK` / `STATE_AWAITING_JOL` / `STATE_AWAITING_EVAL` consistently. Parser uses `MCP_TOOL_PREFIX = "metacog."`, tool names in transcript match that prefix after MCP registration.

**Known unverified assumptions (flagged in plan):**
- A3: `${CLAUDE_PLUGIN_ROOT}` substitution — Task 9 Step 3 verifies during execution.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-17-metacog-mcp.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
