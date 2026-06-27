"""Configuration — read from a ``config.yaml`` file, overridable by real env vars.

Replaces the relevant slices of ``agentcore/config.yaml`` (``memory.*`` and
``guardrails``). Resolution order (highest precedence first):

  1. a real environment variable (e.g. ``MEM_COLLECTION=...`` in the shell / Docker),
  2. the ``config.yaml`` file at the repo root (nested by section; point elsewhere with
     ``AGENTMEM_CONFIG=/path/to/file``),
  3. the dataclass defaults below.

So a fresh checkout works with zero setup (the shipped ``config.yaml`` just restates the
defaults), env vars still win for per-deployment overrides, and the file is the single
readable place to edit settings. The YAML is nested for legibility; ``_FIELD_MAP`` is the
single source of truth that flattens each ``section.key`` to the flat ENV name used both
for env-var overrides and by the control dashboard (``dashboard/configfile.py``).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from ruamel.yaml import YAML

# config.py is at <repo>/src/agentmem/config.py → the repo root is three levels up.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CONFIG_FILE = _REPO_ROOT / "config.yaml"
# Secrets (API keys) live ONLY here, never in config.yaml — which references them as
# ${EMBEDDER_API_KEY} / ${LLM_API_KEY}. The .env is gitignored; .env.example is the
# committed template. Point elsewhere with AGENTMEM_DOTENV=/path/to/.env.
_DEFAULT_DOTENV_FILE = _REPO_ROOT / ".env"

# ${VAR} references inside YAML string values, expanded from the environment (which the
# .env populates). Lets config.yaml read secrets without ever storing them.
_ENV_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

# Single source of truth mapping each flat ENV name to its (section, key) path in the
# nested YAML. config.py uses it to flatten the file into os.environ; the dashboard uses
# it to write the nested file from the flat updates its UI produces. Keep them in sync by
# importing from here — never re-declare the mapping elsewhere.
_FIELD_MAP: dict[str, tuple[str, str]] = {
    # memory
    "QDRANT_HOST": ("memory", "qdrant_host"),
    "QDRANT_PORT": ("memory", "qdrant_port"),
    "MEM_COLLECTION": ("memory", "collection"),
    "MEM_USER": ("memory", "mem_user"),
    # embedder
    "EMBEDDER_PROVIDER": ("embedder", "provider"),
    "EMBEDDER_MODEL": ("embedder", "model"),
    "EMBEDDER_BASE_URL": ("embedder", "base_url"),
    "EMBEDDER_API_KEY": ("embedder", "api_key"),
    "EMBEDDER_DIMS": ("embedder", "dims"),
    "EMBEDDER_CHECK_REACHABLE": ("embedder", "check_reachable"),
    # llm (only exercised when infer is true; see store.build_store)
    "INFER": ("llm", "infer"),
    "LLM_PROVIDER": ("llm", "provider"),
    "LLM_MODEL": ("llm", "model"),
    "LLM_BASE_URL": ("llm", "base_url"),
    "LLM_API_KEY": ("llm", "api_key"),
    "LLM_TEMPERATURE": ("llm", "temperature"),
    "LLM_TOP_P": ("llm", "top_p"),
    "LLM_MAX_TOKENS": ("llm", "max_tokens"),
    # guardrails
    "GUARD_URL_ENABLED": ("guardrails", "url_enabled"),
    "GUARD_DESTRUCTIVE_ENABLED": ("guardrails", "destructive_enabled"),
    "GUARD_ALLOW_DOMAINS": ("guardrails", "allow_domains"),
    "GUARD_CHECK_REACHABLE": ("guardrails", "check_reachable"),
    "GUARD_DISABLED_PATTERNS": ("guardrails", "disabled_patterns"),
    "GUARD_CUSTOM_RULES_FILE": ("guardrails", "custom_rules_file"),
    "PROBE_TIMEOUT": ("guardrails", "probe_timeout"),
    "PROBE_USER_AGENT": ("guardrails", "probe_user_agent"),
    # retrieval
    "LESSON_SEARCH_LIMIT": ("retrieval", "search_limit"),
    "LESSON_LIST_LIMIT": ("retrieval", "list_limit"),
}

_yaml = YAML()  # round-trip loader (preserves types; comments matter only on write)


def _flatten(value: object) -> str | None:
    """Render a YAML scalar as the string an env var would hold. ``None`` (a YAML key
    present but empty) maps to the empty string; an absent key returns ``None`` upstream
    so the dataclass default applies."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def _load_dotenv(path: Path) -> None:
    """Populate ``os.environ`` from a KEY=VALUE ``.env`` (secrets) WITHOUT overriding
    existing vars. Loaded BEFORE the YAML so config.yaml's ${VAR} references resolve to
    these values. Blank/``#`` lines skipped; surrounding quotes stripped; missing = no-op."""
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


def _load_config_file(path: Path) -> None:
    """Populate ``os.environ`` from the nested YAML WITHOUT overriding existing vars.

    Each ``section.key`` present in the file is flattened to its flat ENV name (via
    ``_FIELD_MAP``), has any ``${VAR}`` reference expanded from the environment, and is
    applied with ``setdefault`` — which is what gives real env vars precedence over the
    file. A value that is ONLY an unresolved ``${VAR}`` (e.g. a secret whose .env is
    absent) is skipped so the dataclass default applies. Missing file / unreadable /
    non-mapping = no-op (defaults apply)."""
    try:
        data = _yaml.load(path.read_text(encoding="utf-8"))
    except OSError:
        return
    if not isinstance(data, dict):
        return
    for env_name, (section, key) in _FIELD_MAP.items():
        sect = data.get(section)
        if not isinstance(sect, dict) or key not in sect:
            continue
        rendered = _flatten(sect[key])
        if rendered is None:
            continue
        expanded = _ENV_REF.sub(lambda m: os.environ.get(m.group(1), ""), rendered)
        if _ENV_REF.search(rendered) and not expanded:
            continue  # unresolved ${VAR} (secret not in .env) → let the default apply
        os.environ.setdefault(env_name, expanded)


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
    # For a REMOTE embedder (ollama / openai / lmstudio), preflight that the endpoint is
    # reachable (and, for ollama, that the model is pulled) before building the store —
    # so a down embedder fails loudly instead of writing empty/garbage vectors to Qdrant.
    # No-op for the local in-process providers (huggingface / fastembed).
    embedder_check_reachable: bool = True

    # --- LLM ---
    # mem0 constructs an LLM object even when we never infer. With infer=False (default)
    # it is built but NEVER called: add() stores the lesson verbatim (embedder only) and
    # search() is pure vector similarity. Set infer=true to let mem0 use the LLM below to
    # extract/reconcile facts on write (changes what gets stored — see store.add). The
    # sampling params only take effect in that infer=true write path; they do NOT affect
    # retrieval, which never invokes an LLM.
    infer: bool = False
    llm_provider: str = "openai"
    llm_model: str = "qwen2.5-7b-instruct-1m"
    llm_base_url: str = "http://localhost:1234/v1"
    llm_api_key: str = "lm-studio"
    llm_temperature: float = 0.1
    llm_top_p: float = 1.0
    llm_max_tokens: int = 2000

    # --- Guardrails (guardrails.* in config.yaml) ---
    # Master switches for each guard, plus a per-pattern off-list for the destructive
    # blocklist. These are what the control dashboard toggles (dashboard/server.py).
    guard_url_enabled: bool = True
    guard_destructive_enabled: bool = True
    guard_allow_domains: list[str] = field(default_factory=list)
    guard_check_reachable: bool = True
    # Keys (see guardrails._DESTRUCTIVE_PATTERNS) of destructive patterns to DISABLE.
    guard_disabled_patterns: list[str] = field(default_factory=list)
    # JSON file holding user-defined (custom) destructive rules. Empty => the default
    # <repo>/custom_guardrails.json (resolved in rules_store).
    guard_custom_rules_file: str = ""
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
            embedder_check_reachable=_env_bool("EMBEDDER_CHECK_REACHABLE", cls.embedder_check_reachable),
            infer=_env_bool("INFER", cls.infer),
            llm_provider=os.environ.get("LLM_PROVIDER", cls.llm_provider),
            llm_model=os.environ.get("LLM_MODEL", cls.llm_model),
            llm_base_url=os.environ.get("LLM_BASE_URL", cls.llm_base_url),
            llm_api_key=os.environ.get("LLM_API_KEY", cls.llm_api_key),
            llm_temperature=float(os.environ.get("LLM_TEMPERATURE", cls.llm_temperature)),
            llm_top_p=float(os.environ.get("LLM_TOP_P", cls.llm_top_p)),
            llm_max_tokens=int(os.environ.get("LLM_MAX_TOKENS", cls.llm_max_tokens)),
            guard_url_enabled=_env_bool("GUARD_URL_ENABLED", cls.guard_url_enabled),
            guard_destructive_enabled=_env_bool("GUARD_DESTRUCTIVE_ENABLED", cls.guard_destructive_enabled),
            guard_allow_domains=_env_list("GUARD_ALLOW_DOMAINS"),
            guard_check_reachable=_env_bool("GUARD_CHECK_REACHABLE", cls.guard_check_reachable),
            guard_disabled_patterns=_env_list("GUARD_DISABLED_PATTERNS"),
            guard_custom_rules_file=os.environ.get("GUARD_CUSTOM_RULES_FILE", cls.guard_custom_rules_file),
            probe_timeout=float(os.environ.get("PROBE_TIMEOUT", cls.probe_timeout)),
            probe_user_agent=os.environ.get("PROBE_USER_AGENT", cls.probe_user_agent),
            lesson_search_limit=int(os.environ.get("LESSON_SEARCH_LIMIT", cls.lesson_search_limit)),
            lesson_list_limit=int(os.environ.get("LESSON_LIST_LIMIT", cls.lesson_list_limit)),
        )


def custom_rules_path(cfg: Config) -> Path:
    """Resolve the custom-rules JSON file (config value, or the repo-root default)."""
    return Path(cfg.guard_custom_rules_file) if cfg.guard_custom_rules_file \
        else _REPO_ROOT / "custom_guardrails.json"


def load() -> Config:
    """Load the .env secrets and config.yaml (if present) into the environment, then read
    Config from env. The .env is loaded first so config.yaml's ${VAR} secret references
    resolve against it."""
    _load_dotenv(Path(os.environ.get("AGENTMEM_DOTENV", _DEFAULT_DOTENV_FILE)))
    _load_config_file(Path(os.environ.get("AGENTMEM_CONFIG", _DEFAULT_CONFIG_FILE)))
    return Config.from_env()
