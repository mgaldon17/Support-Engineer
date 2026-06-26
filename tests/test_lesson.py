"""Lesson domain unit tests — factories + counters (offline, no Qdrant)."""

from __future__ import annotations

from agentmem.lesson import Lesson, LessonOrigin


def test_learned_factory_is_pending_review():
    l = Lesson.learned("title", "do X then Y")
    assert l.origin is LessonOrigin.LEARNED
    assert l.pending_review is True
    assert l.reuse == 0 and l.failure_count == 0
    assert l.lesson_id.startswith("les_")


def test_human_authored_is_trusted():
    l = Lesson.human_authored("title", "curated procedure")
    assert l.origin is LessonOrigin.HUMAN_AUTHORED
    assert l.pending_review is False


def test_reinforce_and_record_failure_counters():
    l = Lesson.learned("t", "c")
    l.reinforce()
    l.reinforce()
    l.record_failure()
    assert l.reuse == 2 and l.failure_count == 1
