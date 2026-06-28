"""Feedback-gate unit tests — the Stop-hook policy that enforces flow step 5 (offline)."""

from __future__ import annotations

from agentmem.feedback_gate import decide


def _prompt(text: str = "do the thing") -> dict:
    return {"type": "user", "message": {"role": "user", "content": text}}


def _assistant_tool(name: str, **inp) -> dict:
    return {
        "type": "assistant",
        "message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": name, "input": inp},
        ]},
    }


def _verifier_call() -> dict:
    return _assistant_tool("Task", subagent_type="verifier", description="verify")


def _tool_result() -> dict:
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "content": "ok"},
    ]}}


def test_action_verified_without_feedback_is_blocked():
    events = [_prompt(), _verifier_call(), _tool_result()]
    d = decide(events)
    assert d.block is True
    assert "lesson_reinforce" in d.reason


def test_feedback_persisted_allows_stop():
    events = [_prompt(), _verifier_call(), _assistant_tool("mcp__memory__lesson_reinforce", lesson_id="les_x")]
    assert decide(events).block is False


def test_lesson_add_also_counts_as_feedback():
    events = [_prompt(), _verifier_call(), _assistant_tool("mcp__memory__lesson_add", title="t", content="c")]
    assert decide(events).block is False


def test_info_task_without_verifier_is_never_blocked():
    events = [_prompt(), _assistant_tool("mcp__pw__browser_evaluate", function="() => 1")]
    assert decide(events).block is False


def test_stop_hook_active_never_loops():
    events = [_prompt(), _verifier_call()]
    assert decide(events, stop_hook_active=True).block is False


def test_only_current_turn_counts():
    # Feedback in a PREVIOUS turn must not excuse the current (post-prompt) verifier run.
    events = [
        _prompt("turn 1"),
        _verifier_call(),
        _assistant_tool("mcp__memory__lesson_reinforce", lesson_id="les_old"),
        _prompt("turn 2"),
        _verifier_call(),
    ]
    assert decide(events).block is True


def test_feedback_inside_sidechain_does_not_count():
    # A subagent (sidechain) cannot write feedback; only the main chain counts.
    sidechain_feedback = _assistant_tool("mcp__memory__lesson_reinforce", lesson_id="les_x")
    sidechain_feedback["isSidechain"] = True
    events = [_prompt(), _verifier_call(), sidechain_feedback]
    assert decide(events).block is True
