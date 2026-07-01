#!/usr/bin/env python3
"""Stop hook — enforce the verdict→feedback loop (CLAUDE.md step 5).

When the agent tries to stop, this checks the transcript: if the just-finished turn
verified an ACTION (it invoked the ``verifier`` subagent) but persisted NO feedback
(``lesson_reinforce`` / ``lesson_record_failure`` / ``lesson_add``) since the last user
prompt, it BLOCKS the stop and tells the agent to record the signal. The agent — which
knows which lesson it reused — then writes the correct feedback. The policy itself lives
in ``agentmem.feedback_gate`` (pure + tested); this is just the I/O wrapper.

Reads the hook payload as JSON on stdin (``transcript_path`` + ``stop_hook_active``);
on a block emits ``{"decision": "block", "reason": ...}`` on stdout. Fails OPEN: any
error allows the stop (exit 0, no output) so a bug here never wedges the agent.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _read_transcript(path: str) -> list[dict]:
    events: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except (json.JSONDecodeError, ValueError):
                continue  # skip a malformed line, keep the rest
    return events


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return  # nothing usable on stdin

    from agentmem.constants import Decision, HookKey, HookOut

    transcript_path = str(payload.get(HookKey.TRANSCRIPT_PATH, "")).strip()
    if not transcript_path or not os.path.isfile(transcript_path):
        return

    try:
        from agentmem.feedback_gate import decide

        events = _read_transcript(transcript_path)
        decision = decide(events, stop_hook_active=bool(payload.get(HookKey.STOP_HOOK_ACTIVE)))
    except Exception as exc:  # fail open — never wedge the agent on a gate bug
        print(f"[enforce_feedback] skipped: {exc}", file=sys.stderr)
        return

    if not decision.block:
        return

    print(json.dumps({HookOut.DECISION: Decision.BLOCK, HookOut.REASON: decision.reason}))


if __name__ == "__main__":
    main()
