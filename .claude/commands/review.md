---
description: Review the lessons the agent learned and are awaiting human approval (replaces the old web review panel).
allowed-tools: mcp__memory__lesson_list, mcp__memory__lesson_resolve, mcp__memory__lesson_delete
---

You are running the lesson review queue. The user wants to triage the lessons the agent
learned on its own that are still pending human approval.

1. Call `mcp__memory__lesson_list` with `pending_review: true` to fetch the queue.
2. If empty, say so and stop.
3. Otherwise present each pending lesson compactly: id, title, content, and its
   `reuse` / `failure_count` counters. Number them.
4. Ask the user what to do with each (or in bulk). Then apply their decision:
   - **Approve** → `mcp__memory__lesson_resolve(lesson_id)` (flips pending_review off;
     the lesson becomes trusted, like a human-authored one).
   - **Discard** → `mcp__memory__lesson_delete(lesson_id)`.
   - **Keep pending** → do nothing.
5. Confirm what was approved/deleted.

If the user passed arguments (e.g. an id or "approve all"), act on them directly:
$ARGUMENTS
