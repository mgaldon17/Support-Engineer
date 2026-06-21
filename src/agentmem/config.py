"""Configuration — read from environment variables (no YAML).

Replaces the relevant slices of ``agentcore/config.yaml`` (``memory.*`` and
``guardrails``). Defaults are the values from that file, so a fresh checkout with a
local Qdrant + LM Studio embedder works with zero env set.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_list(name: str) -> list[str]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return []
    return [d.strip().lower() for d in raw.split(",") if d.strip()]


@dataclass
class Config:
    # --- Qdrant / mem0 (memory.* in config.yaml) ---
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    collection: str = "agentcore_lessons"

    # --- Embedder (memory.embedder_* in config.yaml) ---
    embedder_provider: str = "openai"
    embedder_model: str = "text-embedding-nomic-embed-text-v1.5"
    embedder_base_url: str = "http://localhost:1234/v1"   # "" -> hosted default
    embedder_api_key: str = "lm-studio"

    # --- LLM stub (mem0 constructs one even with infer=False; never used) ---
    llm_model: str = "qwen2.5-7b-instruct-1m"
    llm_base_url: str = "http://localhost:1234/v1"
    llm_api_key: str = "lm-studio"

    # --- Guardrails (guardrails.* in config.yaml) ---
    guard_allow_domains: list[str] = field(default_factory=list)
    guard_check_reachable: bool = True

    # --- Retrieval ---
    lesson_search_limit: int = 8

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            qdrant_host=os.environ.get("QDRANT_HOST", cls.qdrant_host),
            qdrant_port=int(os.environ.get("QDRANT_PORT", cls.qdrant_port)),
            collection=os.environ.get("MEM_COLLECTION", cls.collection),
            embedder_provider=os.environ.get("EMBEDDER_PROVIDER", cls.embedder_provider),
            embedder_model=os.environ.get("EMBEDDER_MODEL", cls.embedder_model),
            embedder_base_url=os.environ.get("EMBEDDER_BASE_URL", cls.embedder_base_url),
            embedder_api_key=os.environ.get("EMBEDDER_API_KEY", cls.embedder_api_key),
            llm_model=os.environ.get("LLM_MODEL", cls.llm_model),
            llm_base_url=os.environ.get("LLM_BASE_URL", cls.llm_base_url),
            llm_api_key=os.environ.get("LLM_API_KEY", cls.llm_api_key),
            guard_allow_domains=_env_list("GUARD_ALLOW_DOMAINS"),
            guard_check_reachable=_env_bool("GUARD_CHECK_REACHABLE", cls.guard_check_reachable),
            lesson_search_limit=int(os.environ.get("LESSON_SEARCH_LIMIT", cls.lesson_search_limit)),
        )


def load() -> Config:
    return Config.from_env()
