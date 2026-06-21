"""Mem0LessonStore — the lesson store backed by mem0 over Qdrant (semantic memory).

Ported from ``agentcore/infrastructure/mem0_store.py``. Stores each lesson as a mem0
memory: the procedure text is the memory body and the metadata carries
title/origin/reuse/failure_count/pending_review. ``infer=False`` so mem0 keeps the
procedure verbatim (no LLM fact-extraction) and only its embedder/vector store are
exercised. mem0's sync API is run in a thread so the store stays async.

``mem0ai`` + ``qdrant-client`` are required (see pyproject); imported lazily so unit
tests that monkeypatch the store don't need them.
"""

from __future__ import annotations

import asyncio
import logging

from .config import Config
from .lesson import Lesson, LessonOrigin

_log = logging.getLogger("agentmem.store")

# Single namespace for all lessons (mem0 requires an identity in its filters).
_USER = "agentcore"


def _to_lesson(item: dict) -> Lesson:
    md = item.get("metadata") or {}
    try:
        origin = LessonOrigin(str(md.get("origin", "learned")))
    except ValueError:
        origin = LessonOrigin.LEARNED
    return Lesson(
        lesson_id=str(item.get("id", "")),
        title=str(md.get("title", "")),
        content=str(item.get("memory", "")),
        origin=origin,
        reuse=int(md.get("reuse", 0) or 0),
        failure_count=int(md.get("failure_count", 0) or 0),
        pending_review=bool(md.get("pending_review", False)),
    )


def _metadata(lesson: Lesson) -> dict:
    return {
        "title": lesson.title,
        "origin": str(lesson.origin),
        "reuse": lesson.reuse,
        "failure_count": lesson.failure_count,
        "pending_review": lesson.pending_review,
    }


class Mem0LessonStore:
    def __init__(self, memory) -> None:
        self._mem = memory   # a mem0.Memory instance

    async def add(self, lesson: Lesson) -> None:
        res = await asyncio.to_thread(
            self._mem.add, lesson.content,
            user_id=_USER, metadata=_metadata(lesson), infer=False,
        )
        items = (res or {}).get("results") or []
        if items:  # adopt mem0's id so get/update/delete address the same record
            lesson.lesson_id = str(items[0].get("id", lesson.lesson_id))

    async def get(self, lesson_id: str) -> Lesson | None:
        item = await asyncio.to_thread(self._mem.get, lesson_id)
        return _to_lesson(item) if item else None

    async def update(self, lesson: Lesson) -> None:
        await asyncio.to_thread(
            self._mem.update, lesson.lesson_id, lesson.content, _metadata(lesson)
        )

    async def delete(self, lesson_id: str) -> bool:
        if await self.get(lesson_id) is None:
            return False
        await asyncio.to_thread(self._mem.delete, lesson_id)
        return True

    async def search(self, query: str, *, limit: int = 8) -> list[Lesson]:
        res = await asyncio.to_thread(
            self._mem.search, query, top_k=limit, filters={"user_id": _USER}
        )
        return [_to_lesson(it) for it in (res or {}).get("results", [])]

    async def list(self, *, pending_review: bool | None = None) -> list[Lesson]:
        res = await asyncio.to_thread(
            self._mem.get_all, filters={"user_id": _USER}, top_k=1000
        )
        lessons = [_to_lesson(it) for it in (res or {}).get("results", [])]
        if pending_review is not None:
            lessons = [l for l in lessons if l.pending_review == pending_review]
        return lessons

    async def reinforce(self, lesson_id: str) -> None:
        lesson = await self.get(lesson_id)
        if lesson is not None:
            lesson.reinforce()
            await self.update(lesson)

    async def record_failure(self, lesson_id: str) -> None:
        lesson = await self.get(lesson_id)
        if lesson is not None:
            lesson.record_failure()
            await self.update(lesson)

    async def resolve(self, lesson_id: str) -> Lesson | None:
        """Flip pending_review off (a human accepted a learned lesson)."""
        lesson = await self.get(lesson_id)
        if lesson is None:
            return None
        lesson.pending_review = False
        await self.update(lesson)
        return lesson


def build_store(cfg: Config) -> Mem0LessonStore:
    """Construct a mem0-backed store: Qdrant (Docker, persistent) + the configured
    embedder. mem0 also requires an LLM object even when we never infer; we point it
    at the configured endpoint so construction needs no hosted key."""
    try:
        from mem0 import Memory
    except ImportError as exc:  # pragma: no cover - optional extra
        raise RuntimeError(
            "agentmem needs the 'mem0ai' package: pip install -e '.'"
        ) from exc

    embedder_cfg: dict = {"model": cfg.embedder_model}
    if cfg.embedder_base_url:
        embedder_cfg["openai_base_url"] = cfg.embedder_base_url
    if cfg.embedder_api_key:
        embedder_cfg["api_key"] = cfg.embedder_api_key

    config = {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "host": cfg.qdrant_host,
                "port": cfg.qdrant_port,
                "collection_name": cfg.collection,
            },
        },
        "embedder": {"provider": cfg.embedder_provider, "config": embedder_cfg},
        # Unused with infer=False, but mem0 constructs it — keep it local (no key).
        "llm": {
            "provider": "openai",
            "config": {
                "model": cfg.llm_model,
                "openai_base_url": cfg.llm_base_url,
                "api_key": cfg.llm_api_key,
            },
        },
    }
    _log.info(
        "building mem0 store (host=%s:%s, collection=%s)",
        cfg.qdrant_host, cfg.qdrant_port, cfg.collection,
    )
    return Mem0LessonStore(Memory.from_config(config))
