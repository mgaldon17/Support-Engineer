"""Shared string identifiers — one home for the "magic strings" the agent compares.

Tool names, the lesson's metadata keys, mem0's response-envelope keys and the embedder
provider ids all appeared as bare literals scattered across ``guardrails`` /
``feedback_gate`` / ``store`` / ``config`` — several of them duplicated across files,
where a typo in one copy would silently break a guard, a write or a read. Centralising
them as ``StrEnum``s gives a single source of truth and lets call sites read by NAME.

``StrEnum`` members ARE ``str``, so each constant drops into dict keys, ``==`` comparisons,
``.get(...)`` lookups and JSON exactly where the old literal sat — no ``.value`` needed.

Scope (deliberate): prose stays literal — docstrings, log-category names and the human/
model-facing ``reason`` messages are not identifiers and reading them inline is clearer
than dereferencing an enum. Single-use, library-mandated values (mem0's ``"qdrant"``
vector-store id) also stay where they are.
"""

from __future__ import annotations

from enum import StrEnum


class ToolName(StrEnum):
    """Tool identifiers as Claude Code / the MCP servers expose them.

    MCP tools are namespaced ``mcp__<server>__<tool>``; the ``*_FLAT`` aliases are the
    bare names the sibling ``agentcore`` repo used, still policed by the guardrails."""

    # Claude Code core
    BASH = "Bash"
    TASK = "Task"

    # Playwright browser (MCP + flat alias)
    PW_NAVIGATE = "mcp__pw__browser_navigate"
    PW_NAVIGATE_FLAT = "pw_browser_navigate"

    # Desktop Commander process (MCP + flat alias)
    DC_START_PROCESS = "mcp__dc__start_process"
    DC_START_PROCESS_FLAT = "dc_start_process"

    # Memory feedback writes (the loop's step-5 signal)
    LESSON_REINFORCE = "mcp__memory__lesson_reinforce"
    LESSON_RECORD_FAILURE = "mcp__memory__lesson_record_failure"
    LESSON_ADD = "mcp__memory__lesson_add"


class SubagentType(StrEnum):
    """The ``subagent_type`` carried in a ``Task`` tool-use input."""

    VERIFIER = "verifier"


class MetaKey(StrEnum):
    """Keys of the lesson metadata mem0 stores alongside the procedure text."""

    TITLE = "title"
    ORIGIN = "origin"
    REUSE = "reuse"
    FAILURE_COUNT = "failure_count"
    PENDING_REVIEW = "pending_review"


class Mem0Key(StrEnum):
    """Keys of mem0's own response envelope (``add`` / ``get`` / ``search`` / ``get_all``)
    and the identity-filter field its searches take."""

    RESULTS = "results"
    ID = "id"
    MEMORY = "memory"
    METADATA = "metadata"
    USER_ID = "user_id"     # mem0's identity-filter field (filters={"user_id": ...})


class EmbedderProvider(StrEnum):
    """Embedder providers mem0 supports. ``HUGGINGFACE`` / ``FASTEMBED`` embed locally
    in-process; the rest are remote endpoints the store preflights for reachability."""

    HUGGINGFACE = "huggingface"
    FASTEMBED = "fastembed"
    OLLAMA = "ollama"
    OPENAI = "openai"
    LMSTUDIO = "lmstudio"


class LlmProvider(StrEnum):
    """LLM providers (only exercised on the ``infer=True`` write path)."""

    OPENAI = "openai"


# --------------------------------------------------------------------------- #
# Claude Code transcript schema — the jsonl events the Stop hook reads.
# --------------------------------------------------------------------------- #
class EventType(StrEnum):
    """``type`` of a transcript event (only ``user`` is matched on; ``assistant`` events
    are processed by content, not by this discriminator)."""

    USER = "user"


class BlockType(StrEnum):
    """``type`` of a message-content block."""

    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"


class TranscriptKey(StrEnum):
    """Field names on a transcript event / content block."""

    TYPE = "type"
    MESSAGE = "message"
    CONTENT = "content"
    NAME = "name"
    INPUT = "input"
    SUBAGENT_TYPE = "subagent_type"
    IS_SIDECHAIN = "isSidechain"
    IS_META = "isMeta"


# --------------------------------------------------------------------------- #
# Claude Code hook protocol — payload-in / decision-out keys shared by the hooks.
# --------------------------------------------------------------------------- #
class HookEvent(StrEnum):
    """``hookEventName`` echoed back in a hook's structured output."""

    PRE_TOOL_USE = "PreToolUse"
    USER_PROMPT_SUBMIT = "UserPromptSubmit"


class HookKey(StrEnum):
    """Keys read from the hook's stdin payload."""

    TOOL_NAME = "tool_name"
    TOOL_INPUT = "tool_input"
    PROMPT = "prompt"
    TRANSCRIPT_PATH = "transcript_path"
    STOP_HOOK_ACTIVE = "stop_hook_active"


class HookOut(StrEnum):
    """Keys written to the hook's stdout decision."""

    HOOK_SPECIFIC_OUTPUT = "hookSpecificOutput"
    HOOK_EVENT_NAME = "hookEventName"
    PERMISSION_DECISION = "permissionDecision"
    PERMISSION_DECISION_REASON = "permissionDecisionReason"
    ADDITIONAL_CONTEXT = "additionalContext"
    DECISION = "decision"
    REASON = "reason"


class Decision(StrEnum):
    """Decision values a hook can emit."""

    DENY = "deny"       # PreToolUse permissionDecision
    BLOCK = "block"     # Stop decision
