"""agentmem — the only real code in AgentScalator-Claude.

Claude Code is the runtime (loop, reasoning, vision); this package supplies the
three things Claude Code does not give for free:

  * a lesson memory (``store`` / ``lesson``) over the same Qdrant the sibling
    ``agentcore`` repo uses, exposed as an MCP server (``mcp_server``);
  * guardrails (``guardrails``) that veto hallucinated URLs and destructive
    commands, invoked from a ``PreToolUse`` hook.

See PLAN.md for the full mapping agentcore -> Claude Code.
"""

from __future__ import annotations

from .lesson import Lesson, LessonOrigin

__all__ = ["Lesson", "LessonOrigin"]
