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
