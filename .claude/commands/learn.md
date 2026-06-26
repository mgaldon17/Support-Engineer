---
description: Manually capture a procedure as a lesson in memory.
allowed-tools: mcp__memory__lesson_add, mcp__memory__lesson_inject
---

The user wants to save a procedure to the lesson memory so it is recalled on future
tasks.

The procedure to capture (may be empty — then ask, or derive it from what we just did
in this conversation):
$ARGUMENTS

1. Turn it into a clear, reusable lesson: a short **title** and a **content** body that
   is a concrete, step-by-step procedure (imperative, tool-aware, no task-specific
   one-off details). Write it the way a future run should follow it.
2. Show the proposed title + content and confirm with the user.
3. Save it:
   - If the user is curating a trusted procedure → `mcp__memory__lesson_inject`
     (human-authored, no review needed).
   - If it is a tentative thing to verify later → `mcp__memory__lesson_add`
     (learned, lands in /review).
   Default to `lesson_inject` for an explicit `/learn`.
4. Report the saved lesson id.
