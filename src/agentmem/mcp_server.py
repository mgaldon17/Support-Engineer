"""agentmem MCP server — exposes the lesson store as MCP ``lesson_*`` tools.

A stdio MCP server (FastMCP) that wraps ``Mem0LessonStore`` so the lesson memory is
usable from Claude Code AND the degraded Copilot client (tools only, no hooks). Run:

    python -m agentmem.mcp_server          # stdio; wired via .mcp.json

Tools (all persist to the same Qdrant the sibling ``agentcore`` repo uses):
  * ``lesson_search(query, limit)``      — semantic recall of relevant procedures.
  * ``lesson_add(title, content)``       — record a learned procedure (pending_review).
  * ``lesson_inject(title, content)``    — curate a human-authored procedure (trusted).
  * ``lesson_reinforce(lesson_id)``      — a reused lesson actually helped (reuse++).
  * ``lesson_record_failure(lesson_id)`` — a reused lesson did NOT help (failure_count++).
  * ``lesson_list(pending_review?)``     — list lessons, optionally only pending review.
  * ``lesson_resolve(lesson_id)``        — accept a learned lesson (flip pending_review off).
  * ``lesson_delete(lesson_id)``         — remove a lesson.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from mcp.server.fastmcp import FastMCP

from .config import Config, load
from .lesson import Lesson
from .store import Mem0LessonStore, build_store

_log = logging.getLogger("agentmem.mcp_server")

mcp = FastMCP("agentmem")


@lru_cache(maxsize=1)
def _store() -> Mem0LessonStore:
    """Build the store once, lazily — so importing the module (e.g. list_tools)
    doesn't require Qdrant to be up until a tool actually runs."""
    return build_store(load())


def _cfg() -> Config:
    return load()


def _view(lesson: Lesson) -> dict:
    """Compact dict returned to the model (no created_at noise)."""
    return {
        "id": lesson.lesson_id,
        "title": lesson.title,
        "content": lesson.content,
        "origin": str(lesson.origin),
        "reuse": lesson.reuse,
        "failure_count": lesson.failure_count,
        "pending_review": lesson.pending_review,
    }


@mcp.tool()
async def lesson_search(query: str, limit: int = 8) -> list[dict]:
    """Semantically recall the lessons most relevant to ``query`` (by meaning, any
    language). Returns the top matches as {id, title, content, reuse, failure_count}."""
    lessons = await _store().search(query, limit=limit)
    return [_view(l) for l in lessons]


@mcp.tool()
async def lesson_add(title: str, content: str) -> dict:
    """Record a NEW procedure the agent derived from a verified run. Stored as
    ``learned`` (pending_review=True → surfaces in /review)."""
    lesson = Lesson.learned(title=title, content=content)
    await _store().add(lesson)
    return _view(lesson)


@mcp.tool()
async def lesson_inject(title: str, content: str) -> dict:
    """Curate a HUMAN-authored procedure (trusted, no review). Replaces the old
    scripts/seed_lessons.py."""
    lesson = Lesson.human_authored(title=title, content=content)
    await _store().add(lesson)
    return _view(lesson)


@mcp.tool()
async def lesson_reinforce(lesson_id: str) -> dict:
    """A reused lesson actually worked — increment its ``reuse`` counter."""
    await _store().reinforce(lesson_id)
    lesson = await _store().get(lesson_id)
    return _view(lesson) if lesson else {"error": f"lesson '{lesson_id}' not found"}


@mcp.tool()
async def lesson_record_failure(lesson_id: str) -> dict:
    """A reused lesson did NOT work — increment its ``failure_count`` counter."""
    await _store().record_failure(lesson_id)
    lesson = await _store().get(lesson_id)
    return _view(lesson) if lesson else {"error": f"lesson '{lesson_id}' not found"}


@mcp.tool()
async def lesson_list(pending_review: bool | None = None) -> list[dict]:
    """List lessons. Pass ``pending_review=true`` for only those awaiting review."""
    lessons = await _store().list(pending_review=pending_review)
    return [_view(l) for l in lessons]


@mcp.tool()
async def lesson_resolve(lesson_id: str) -> dict:
    """Accept a learned lesson — flip pending_review off (used by /review)."""
    lesson = await _store().resolve(lesson_id)
    return _view(lesson) if lesson else {"error": f"lesson '{lesson_id}' not found"}


@mcp.tool()
async def lesson_delete(lesson_id: str) -> dict:
    """Delete a lesson by id."""
    deleted = await _store().delete(lesson_id)
    return {"deleted": deleted, "id": lesson_id}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    mcp.run()


if __name__ == "__main__":
    main()
