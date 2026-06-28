"""Mem0LessonStore — the lesson store backed by mem0 over Qdrant (semantic memory).

Ported from ``agentcore/infrastructure/mem0_store.py``. Stores each lesson as a mem0
memory: the procedure text is the memory body and the metadata carries
title/origin/reuse/failure_count/pending_review. With ``infer=False`` (the default,
configurable) mem0 keeps the procedure verbatim (no LLM fact-extraction) and only its
embedder/vector store are exercised; ``infer=True`` lets mem0's single LLM call rewrite/
reconcile the text on write. mem0's sync API is run in a thread so the store stays async.

``mem0ai`` + ``qdrant-client`` are required (see pyproject); imported lazily so unit
tests that monkeypatch the store don't need them.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from .config import Config
from .constants import EmbedderProvider, Mem0Key, MetaKey
from .lesson import Lesson, LessonOrigin
from .ports import LessonStore

_log = logging.getLogger("agentmem.store")

# Remote embedder providers and where to probe them. The local in-process providers
# (huggingface / fastembed) are absent here — they need no network and are never checked.
_REMOTE_EMBEDDERS = {
    EmbedderProvider.OLLAMA: "http://localhost:11434",  # default when base_url is empty
    EmbedderProvider.OPENAI: "https://api.openai.com/v1",
    EmbedderProvider.LMSTUDIO: "http://localhost:1234/v1",
}

# Default namespace / list cap when the store is built without a Config (e.g. tests).
# Production values come from Config (mem_user / lesson_list_limit) via build_store.
_USER = "agentcore"
_LIST_LIMIT = 1000


def _to_lesson(item: dict) -> Lesson:
    md = item.get(Mem0Key.METADATA) or {}
    try:
        origin = LessonOrigin(str(md.get(MetaKey.ORIGIN, LessonOrigin.LEARNED)))
    except ValueError:
        origin = LessonOrigin.LEARNED
    return Lesson(
        lesson_id=str(item.get(Mem0Key.ID, "")),
        title=str(md.get(MetaKey.TITLE, "")),
        content=str(item.get(Mem0Key.MEMORY, "")),
        origin=origin,
        reuse=int(md.get(MetaKey.REUSE, 0) or 0),
        failure_count=int(md.get(MetaKey.FAILURE_COUNT, 0) or 0),
        pending_review=bool(md.get(MetaKey.PENDING_REVIEW, False)),
    )


def _metadata(lesson: Lesson) -> dict:
    return {
        MetaKey.TITLE: lesson.title,
        MetaKey.ORIGIN: str(lesson.origin),
        MetaKey.REUSE: lesson.reuse,
        MetaKey.FAILURE_COUNT: lesson.failure_count,
        MetaKey.PENDING_REVIEW: lesson.pending_review,
    }


class Mem0LessonStore:
    def __init__(
        self, memory, *, user: str = _USER, list_limit: int = _LIST_LIMIT, infer: bool = False
    ) -> None:
        self._mem = memory          # a mem0.Memory instance
        self._user = user           # namespace for mem0's identity filters
        self._list_limit = list_limit
        self._infer = infer         # True => mem0's LLM rewrites/reconciles text on add()

    async def add(self, lesson: Lesson) -> None:
        res = await asyncio.to_thread(
            self._mem.add, lesson.content,
            user_id=self._user, metadata=_metadata(lesson), infer=self._infer,
        )
        items = (res or {}).get(Mem0Key.RESULTS) or []
        if items:  # adopt mem0's id so get/update/delete address the same record
            lesson.lesson_id = str(items[0].get(Mem0Key.ID, lesson.lesson_id))

    async def get(self, lesson_id: str) -> Lesson | None:
        item = await asyncio.to_thread(self._mem.get, lesson_id)
        return _to_lesson(item) if item else None

    async def update(self, lesson: Lesson) -> None:
        await asyncio.to_thread(
            self._mem.update, lesson.lesson_id, lesson.content, metadata=_metadata(lesson)
        )

    async def delete(self, lesson_id: str) -> bool:
        if await self.get(lesson_id) is None:
            return False
        await asyncio.to_thread(self._mem.delete, lesson_id)
        return True

    async def search(self, query: str, *, limit: int = 8) -> list[Lesson]:
        res = await asyncio.to_thread(
            self._mem.search, query, top_k=limit, filters={Mem0Key.USER_ID: self._user}
        )
        return [_to_lesson(it) for it in (res or {}).get(Mem0Key.RESULTS, [])]

    async def list(self, *, pending_review: bool | None = None) -> list[Lesson]:
        res = await asyncio.to_thread(
            self._mem.get_all, filters={Mem0Key.USER_ID: self._user}, top_k=self._list_limit
        )
        lessons = [_to_lesson(it) for it in (res or {}).get(Mem0Key.RESULTS, [])]
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


def _embedder_config(cfg: Config) -> dict:
    """mem0 embedder config for the configured provider.

    Local (no server): ``huggingface`` (sentence-transformers) / ``fastembed`` only
    need a model name. Remote/OpenAI-compatible (``openai``/``lmstudio``) take a base
    URL + key; ``ollama`` takes its own base URL. The model name is always passed."""
    provider = cfg.embedder_provider.lower()
    embedder_cfg: dict = {"model": cfg.embedder_model}
    if provider in (EmbedderProvider.HUGGINGFACE, EmbedderProvider.FASTEMBED):
        return embedder_cfg
    if provider == EmbedderProvider.OLLAMA:
        if cfg.embedder_base_url:
            embedder_cfg["ollama_base_url"] = cfg.embedder_base_url
        return embedder_cfg
    # openai / lmstudio / azure_openai and other OpenAI-compatible providers
    if cfg.embedder_base_url:
        embedder_cfg["openai_base_url"] = cfg.embedder_base_url
    if cfg.embedder_api_key:
        embedder_cfg["api_key"] = cfg.embedder_api_key
    return embedder_cfg


def _check_embedder_reachable(cfg: Config) -> None:
    """Preflight a REMOTE embedder so we never write empty/garbage vectors to Qdrant.

    Local providers (huggingface/fastembed) embed in-process → skipped. For a remote
    provider we probe the endpoint; for ollama we additionally confirm the model is
    actually pulled (an up-but-modelless ollama would silently fail to embed). Raises a
    clear RuntimeError instead of letting the store build against a dead embedder."""
    provider = cfg.embedder_provider.lower()
    if provider not in _REMOTE_EMBEDDERS:
        return
    base = (cfg.embedder_base_url or _REMOTE_EMBEDDERS[provider]).rstrip("/")
    try:
        if provider == EmbedderProvider.OLLAMA:
            resp = httpx.get(f"{base}/api/tags", timeout=cfg.probe_timeout)
            resp.raise_for_status()
            pulled = {m.get("name", "").split(":")[0] for m in resp.json().get("models", [])}
            wanted = cfg.embedder_model.split(":")[0]
            if wanted not in pulled:
                raise RuntimeError(
                    f"ollama is up at {base} but the embedder model '{cfg.embedder_model}' "
                    f"is not pulled — run `ollama pull {cfg.embedder_model}`. Refusing to "
                    f"build the store so no empty vectors are written to Qdrant."
                )
        else:  # openai / lmstudio and other OpenAI-compatible endpoints
            resp = httpx.get(f"{base}/models", timeout=cfg.probe_timeout)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(
            f"embedder '{provider}' not reachable at {base} ({exc}). Start it (e.g. "
            f"`ollama serve`) or fix embedder.base_url. Set embedder.check_reachable: false "
            f"to skip this preflight. Refusing to build the store so no empty vectors are "
            f"written to Qdrant."
        ) from exc


def _mem0_config(cfg: Config) -> dict:
    """Translate our ``Config`` into mem0's nested config schema (vector_store + embedder
    + llm). Pure — no mem0 import, no I/O — so the mapping is unit-testable on its own.

    The ``llm`` block is built unconditionally because mem0 requires it, but it is only
    CALLED when ``cfg.infer=True`` (mem0's single add()-time fact-extraction call); its
    sampling params apply to that call and never to retrieval."""
    return {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "host": cfg.qdrant_host,
                "port": cfg.qdrant_port,
                "collection_name": cfg.collection,
                # mem0's vector store does NOT derive this from the embedder; it must
                # match the model's output dim or Qdrant rejects the vectors.
                "embedding_model_dims": cfg.embedder_dims,
            },
        },
        "embedder": {"provider": cfg.embedder_provider, "config": _embedder_config(cfg)},
        "llm": {
            "provider": cfg.llm_provider,
            "config": {
                "model": cfg.llm_model,
                "openai_base_url": cfg.llm_base_url,
                "api_key": cfg.llm_api_key,
                "temperature": cfg.llm_temperature,
                "top_p": cfg.llm_top_p,
                "max_tokens": cfg.llm_max_tokens,
            },
        },
    }


def build_store(cfg: Config) -> LessonStore:
    """Construct a mem0-backed store from an already-loaded ``Config`` (callers inject it
    via ``build_store(load())`` — config loading stays out of here). Preflights the
    embedder, maps the config (``_mem0_config``), then wraps mem0's ``Memory`` in a
    ``Mem0LessonStore``."""
    try:
        from mem0 import Memory
    except ImportError as exc:  # pragma: no cover - optional extra
        raise RuntimeError(
            "agentmem needs the 'mem0ai' package: pip install -e '.'"
        ) from exc

    if cfg.embedder_check_reachable:
        _check_embedder_reachable(cfg)

    _log.info(
        "building mem0 store (host=%s:%s, collection=%s, infer=%s)",
        cfg.qdrant_host, cfg.qdrant_port, cfg.collection, cfg.infer,
    )
    return Mem0LessonStore(
        Memory.from_config(_mem0_config(cfg)),
        user=cfg.mem_user,
        list_limit=cfg.lesson_list_limit,
        infer=cfg.infer,
    )
