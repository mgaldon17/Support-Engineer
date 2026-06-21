"""Lesson entity + LessonOrigin — a unit of reusable knowledge (a verbal procedure).

Ported verbatim from ``agentcore/domain/lesson.py`` and the ``LessonOrigin`` enum of
``agentcore/domain/enums.py``. A lesson is ``title`` + ``content`` (the procedure /
knowledge body) plus two counters the agent folds back: ``reuse`` (++ when a retrieved
lesson actually helped) and ``failure_count`` (++ when it didn't). Origin tells
``learned`` Ha(derived by the agent, pending human review) from ``human_authored``
(entered/curated by a human). Relevance and ranking live in the store (semantic
retrieval) — the lesson stays a plain value object.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field


class LessonOrigin(StrEnum):
    """Where a lesson came from.

      * LEARNED        — derived by the agent while resolving a task (pending review).
      * HUMAN_AUTHORED — entered directly by a human; trusted, no review needed.
    """

    LEARNED = "learned"
    HUMAN_AUTHORED = "human_authored"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return f"les_{uuid.uuid4().hex[:12]}"


class Lesson(BaseModel):
    lesson_id: str = Field(default_factory=_new_id)
    title: str = ""
    content: str = ""                       # the verbal procedure / knowledge body

    origin: LessonOrigin = LessonOrigin.LEARNED
    reuse: int = 0                          # ++ when a reuse actually helped
    failure_count: int = 0                  # ++ when a reuse did NOT help
    pending_review: bool = False            # surfaced in /review
    created_at: datetime = Field(default_factory=_utcnow)

    # ------------------------------------------------------------------ #
    # Pure domain operations (no I/O). The store drives persistence.
    # ------------------------------------------------------------------ #
    def reinforce(self) -> None:
        self.reuse += 1

    def record_failure(self) -> None:
        self.failure_count += 1

    @classmethod
    def learned(cls, title: str, content: str) -> "Lesson":
        """A lesson the agent derived from a verified run (awaits human review)."""
        return cls(
            title=title, content=content,
            origin=LessonOrigin.LEARNED, pending_review=True,
        )

    @classmethod
    def human_authored(cls, title: str, content: str) -> "Lesson":
        """A procedure a human authored / curated — trusted, no review needed."""
        return cls(
            title=title, content=content,
            origin=LessonOrigin.HUMAN_AUTHORED, pending_review=False,
        )
