"""`_mem0_config` mapping tests — pure Config→mem0-schema translation (no mem0, no I/O).

This is the unit-testability the ``build_store`` split buys: the config mapping can be
asserted without mem0 installed or Qdrant running.
"""

from __future__ import annotations

from agentmem.config import Config
from agentmem.constants import EmbedderProvider
from agentmem.store import _mem0_config


def test_local_embedder_maps_to_minimal_config():
    cfg = Config()  # defaults: local huggingface embedder
    mem = _mem0_config(cfg)

    assert mem["vector_store"]["provider"] == "qdrant"
    assert mem["vector_store"]["config"]["collection_name"] == cfg.collection
    assert mem["vector_store"]["config"]["embedding_model_dims"] == cfg.embedder_dims
    assert mem["embedder"]["provider"] == EmbedderProvider.HUGGINGFACE
    # a local provider carries only the model name (no base_url / api_key keys)
    assert mem["embedder"]["config"] == {"model": cfg.embedder_model}


def test_remote_embedder_carries_base_url_and_key():
    cfg = Config()
    cfg.embedder_provider = EmbedderProvider.OPENAI
    cfg.embedder_base_url = "https://api.example.com/v1"
    cfg.embedder_api_key = "sk-test"

    embedder = _mem0_config(cfg)["embedder"]["config"]
    assert embedder["openai_base_url"] == "https://api.example.com/v1"
    assert embedder["api_key"] == "sk-test"


def test_llm_block_is_always_present():
    # mem0 requires it even when infer=False; sampling params are passed through verbatim.
    cfg = Config()
    llm = _mem0_config(cfg)["llm"]
    assert llm["provider"] == cfg.llm_provider
    assert llm["config"]["model"] == cfg.llm_model
    assert llm["config"]["temperature"] == cfg.llm_temperature
