from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

try:
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider
except Exception:  # pragma: no cover
    OpenAIChatModel = None
    OpenAIProvider = None


@dataclass
class ModelConfig:
    base_url: str
    api_key: str
    model: str


def model_from_env(prefix: str = "LLM_") -> ModelConfig:
    """
    LLM_BASE_URL=http://127.0.0.1:8000/v1
    LLM_API_KEY=local
    LLM_MODEL=gpt-oss-120b
    """
    return ModelConfig(
        base_url=os.environ.get(prefix + "BASE_URL", "http://127.0.0.1:8000/v1"),
        api_key=os.environ.get(prefix + "API_KEY", "local"),
        model=os.environ.get(prefix + "MODEL", "gpt-oss-120b"),
    )


def build_openai_chat_model(cfg: ModelConfig) -> Any:
    """
    Returns OpenAIChatModel(model_name, provider=OpenAIProvider(base_url=..., api_key=...))
    """
    if OpenAIChatModel is None or OpenAIProvider is None:
        raise RuntimeError("pydantic-ai not installed. Install agent-patterns[agent] or pydantic-ai.")
    provider = OpenAIProvider(base_url=cfg.base_url, api_key=cfg.api_key)
    return OpenAIChatModel(cfg.model, provider=provider)
