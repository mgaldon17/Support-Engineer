"""Feedback gate — enforce that the verdict→feedback loop (flow step 5) actually runs.

CLAUDE.md step 5 tells the agent to fold a verified action's outcome back into memory:
``lesson_reinforce`` / ``lesson_record_failure`` for a REUSED lesson, or ``lesson_add``
for a new verified path. Nothing in code forced it, so that signal depended on prompt
discipline alone. This module is the policy the ``Stop`` hook applies: if the agent just
finished an ACTION task (it invoked the ``verifier`` subagent) but persisted NO feedback
since the last user prompt, the hook BLOCKS the stop and tells the agent to do it. The
agent — which knows WHICH lesson it actually reused — writes the correct signal; the hook
only guarantees the step happens (it never guesses attribution itself).

Pure + deterministic: ``decide`` takes the parsed transcript events and returns a
``FeedbackGateDecision``. The hook (``hooks/enforce_feedback.py``) does all the I/O.
"""

from __future__ import annotations

from pydantic import BaseModel

from .constants import BlockType, EventType, SubagentType, ToolName, TranscriptKey

# The three memory writes that count as "feedback persisted" for the finished task.
_FEEDBACK_TOOLS = {
    ToolName.LESSON_REINFORCE,
    ToolName.LESSON_RECORD_FAILURE,
    ToolName.LESSON_ADD,
}

_REASON = (
    "You invoked the verifier (an ACTION task) but have not persisted its outcome to "
    "memory since the last prompt. Per CLAUDE.md step 5, fold the result back NOW: call "
    "mcp__memory__lesson_reinforce(lesson_id) if you reused a lesson that worked, "
    "mcp__memory__lesson_record_failure(lesson_id) if a reused lesson failed, or "
    "mcp__memory__lesson_add(title, content) for a new verified procedure. Then stop."
)


class FeedbackGateDecision(BaseModel):
    block: bool = False
    reason: str = ""


def _content_blocks(event: dict) -> list[dict]:
    """The message content blocks of an event, normalised to a list of dicts."""
    content = (event.get(TranscriptKey.MESSAGE) or {}).get(TranscriptKey.CONTENT)
    if isinstance(content, list):
        return [b for b in content if isinstance(b, dict)]
    return []


def _is_user_prompt(event: dict) -> bool:
    """A GENUINE user prompt — not a tool_result, a subagent turn or a meta event.

    Tool results also arrive as ``type == "user"`` (content is a list of ``tool_result``
    blocks), so a string content — or text blocks with no tool_result — marks the real
    prompt that opened the current turn."""
    if (
        event.get(TranscriptKey.TYPE) != EventType.USER
        or event.get(TranscriptKey.IS_SIDECHAIN)
        or event.get(TranscriptKey.IS_META)
    ):
        return False
    content = (event.get(TranscriptKey.MESSAGE) or {}).get(TranscriptKey.CONTENT)
    if isinstance(content, str):
        return bool(content.strip())
    blocks = _content_blocks(event)
    return bool(blocks) and not any(
        b.get(TranscriptKey.TYPE) == BlockType.TOOL_RESULT for b in blocks
    )


def _current_turn(events: list[dict]) -> list[dict]:
    """Events from the last genuine user prompt onward (the turn that is stopping)."""
    last = -1
    for i, ev in enumerate(events):
        if _is_user_prompt(ev):
            last = i
    return events[last:] if last >= 0 else list(events)


def _tool_uses(events: list[dict]) -> list[dict]:
    """``tool_use`` blocks from the MAIN chain only (ignore subagent internals)."""
    uses: list[dict] = []
    for ev in events:
        if ev.get(TranscriptKey.IS_SIDECHAIN):
            continue
        for block in _content_blocks(ev):
            if block.get(TranscriptKey.TYPE) == BlockType.TOOL_USE:
                uses.append(block)
    return uses


def decide(events: list[dict], *, stop_hook_active: bool = False) -> FeedbackGateDecision:
    """Block the stop iff the current turn verified an action but logged no feedback.

    ``stop_hook_active`` is True when Claude is already continuing because of a previous
    Stop block: nudge AT MOST once per turn — never loop — so on the second pass we allow
    the stop regardless."""
    if stop_hook_active:
        return FeedbackGateDecision(block=False)

    uses = _tool_uses(_current_turn(events))

    ran_verifier = any(
        u.get(TranscriptKey.NAME) == ToolName.TASK
        and (u.get(TranscriptKey.INPUT) or {}).get(TranscriptKey.SUBAGENT_TYPE)
        == SubagentType.VERIFIER
        for u in uses
    )
    if not ran_verifier:
        return FeedbackGateDecision(block=False)  # info task / no action verified

    if any(u.get(TranscriptKey.NAME) in _FEEDBACK_TOOLS for u in uses):
        return FeedbackGateDecision(block=False)  # feedback already persisted

    return FeedbackGateDecision(block=True, reason=_REASON)
