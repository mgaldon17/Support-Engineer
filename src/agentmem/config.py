"""Configuration — read from a ``config.env`` file, overridable by real env vars.

Replaces the relevant slices of ``agentcore/config.yaml`` (``memory.*`` and
``guardrails``). Resolution order (highest precedence first):

  1. a real environment variable (e.g. ``MEM_COLLECTION=...`` in the shell / Docker),
  2. the ``config.env`` file at the repo root (KEY=VALUE; point elsewhere with
     ``AGENTMEM_CONFIG=/path/to/file``),
  3. the dataclass defaults below.

So a fresh checkout works with zero setup (the shipped ``config.env`` just restates the
defaults), env vars still win for per-deployment overrides, and the file is the single
place to edit settings. No YAML / extra dependency — it's a tiny KEY=VALUE parser.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# config.py is at <repo>/src/agentmem/config.py → the repo root is three levels up.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_ENV_FILE = _REPO_ROOT / "config.env"


def _load_env_file(path: Path) -> None:
    """Populate ``os.environ`` from a KEY=VALUE file WITHOUT overriding existing vars.

    Blank lines and ``#`` comments are skipped; surrounding quotes on the value are
    stripped. Missing file = no-op (defaults apply). ``setdefault`` is what gives real
    env vars precedence over the file."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


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
    # mem0 requires an identity for its filters; all lessons share this namespace.
    mem_user: str = "agentcore"

    # --- Embedder ---
    # Default is a LOCAL, in-process embedder (sentence-transformers via mem0's
    # "huggingface" provider): no server, no API key, fully offline after the model
    # is downloaded once. The multilingual MiniLM handles the Spanish lessons well.
    # To use a remote OpenAI-compatible embedder instead (e.g. LM Studio), set
    # EMBEDDER_PROVIDER=openai (or lmstudio) + EMBEDDER_MODEL/BASE_URL/API_KEY.
    embedder_provider: str = "huggingface"
    embedder_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    embedder_base_url: str = ""   # only for openai/lmstudio/ollama providers
    embedder_api_key: str = ""    # only for openai-compatible providers
    # Vector dimension of the embedder, written into the Qdrant collection. MUST match
    # the model: 384 for paraphrase-multilingual-MiniLM-L12-v2 (default), 768 for nomic,
    # 1536 for OpenAI text-embedding-3. Changing it requires a fresh collection.
    embedder_dims: int = 384

    # --- LLM stub (mem0 constructs one even with infer=False; never used) ---
    llm_model: str = "qwen2.5-7b-instruct-1m"
    llm_base_url: str = "http://localhost:1234/v1"
    llm_api_key: str = "lm-studio"

    # --- Guardrails (guardrails.* in config.yaml) ---
    guard_allow_domains: list[str] = field(default_factory=list)
    guard_check_reachable: bool = True
    # URL-reachability probe (UrlGuardrail._http_probe).
    probe_timeout: float = 5.0
    probe_user_agent: str = "Mozilla/5.0 (agentmem url-guardrail)"

    # --- Retrieval ---
    lesson_search_limit: int = 8       # default top_k for semantic recall
    lesson_list_limit: int = 1000      # top_k cap when enumerating all lessons

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            qdrant_host=os.environ.get("QDRANT_HOST", cls.qdrant_host),
            qdrant_port=int(os.environ.get("QDRANT_PORT", cls.qdrant_port)),
            collection=os.environ.get("MEM_COLLECTION", cls.collection),
            mem_user=os.environ.get("MEM_USER", cls.mem_user),
            embedder_provider=os.environ.get("EMBEDDER_PROVIDER", cls.embedder_provider),
            embedder_model=os.environ.get("EMBEDDER_MODEL", cls.embedder_model),
            embedder_base_url=os.environ.get("EMBEDDER_BASE_URL", cls.embedder_base_url),
            embedder_api_key=os.environ.get("EMBEDDER_API_KEY", cls.embedder_api_key),
            embedder_dims=int(os.environ.get("EMBEDDER_DIMS", cls.embedder_dims)),
            llm_model=os.environ.get("LLM_MODEL", cls.llm_model),
            llm_base_url=os.environ.get("LLM_BASE_URL", cls.llm_base_url),
            llm_api_key=os.environ.get("LLM_API_KEY", cls.llm_api_key),
            guard_allow_domains=_env_list("GUARD_ALLOW_DOMAINS"),
            guard_check_reachable=_env_bool("GUARD_CHECK_REACHABLE", cls.guard_check_reachable),
            probe_timeout=float(os.environ.get("PROBE_TIMEOUT", cls.probe_timeout)),
            probe_user_agent=os.environ.get("PROBE_USER_AGENT", cls.probe_user_agent),
            lesson_search_limit=int(os.environ.get("LESSON_SEARCH_LIMIT", cls.lesson_search_limit)),
            lesson_list_limit=int(os.environ.get("LESSON_LIST_LIMIT", cls.lesson_list_limit)),
        )


def load() -> Config:
    """Load config.env (if present) into the environment, then read Config from env."""
    _load_env_file(Path(os.environ.get("AGENTMEM_CONFIG", _DEFAULT_ENV_FILE)))
    return Config.from_env()
