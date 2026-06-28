#!/usr/bin/env python3
"""PreToolUse hook — apply the code guardrails before a tool call runs.

Vetoes hallucinated/unreachable URLs (browser navigation) and destructive shell
commands (Bash, Desktop Commander). Reads the hook payload as JSON on stdin
(``tool_name`` + ``tool_input``), runs ``agentmem.guardrails.check`` and, on a veto,
emits a ``deny`` permission decision so Claude Code blocks the call and tells the
model why.

Fails OPEN: any internal error allows the call (exit 0, no output) so a guardrail bug
or a missing dep never wedges the agent.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


async def _decide(tool_name: str, tool_input: dict):
    from agentmem.guardrails import check

    return await check(tool_name, tool_input)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return

    from agentmem.constants import Decision, HookEvent, HookKey, HookOut

    tool_name = str(payload.get(HookKey.TOOL_NAME, ""))
    tool_input = payload.get(HookKey.TOOL_INPUT) or {}
    if not isinstance(tool_input, dict):
        return

    try:
        decision = asyncio.run(_decide(tool_name, tool_input))
    except Exception as exc:  # fail open — a guardrail error must not block real work
        print(f"[guardrail_check] skipped: {exc}", file=sys.stderr)
        return

    if decision.allow:
        return

    out = {
        HookOut.HOOK_SPECIFIC_OUTPUT: {
            HookOut.HOOK_EVENT_NAME: HookEvent.PRE_TOOL_USE,
            HookOut.PERMISSION_DECISION: Decision.DENY,
            HookOut.PERMISSION_DECISION_REASON: decision.reason,
        }
    }
    print(json.dumps(out))


if __name__ == "__main__":
    main()
