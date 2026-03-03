"""LLM configuration loading.

Config file: ~/.config/vocalinux/config.yaml

Expected schema (example):

llm:
  provider: gemini
  model: gemini-1.5-flash
  api_key_env: GEMINI_API_KEY
  # api_key: "..."  # discouraged
  timeout_seconds: 20
  temperature: 0.2
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional


CONFIG_DIR = os.path.expanduser("~/.config/vocalinux")
CONFIG_YAML_PATH = os.path.join(CONFIG_DIR, "config.yaml")


@dataclass(frozen=True)
class LlmConfig:
    provider: str
    model: str
    api_key: str
    timeout_seconds: float = 20.0
    temperature: float = 0.2


def _get_nested(dct: Dict[str, Any], path: str, default: Any = None) -> Any:
    cur: Any = dct
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def load_llm_config(path: str = CONFIG_YAML_PATH) -> LlmConfig:
    try:
        import yaml  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "PyYAML is required for config.yaml support. Install with: pip install pyyaml"
        ) from e

    if not os.path.exists(path):
        raise RuntimeError(f"LLM config not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    provider = str(_get_nested(raw, "llm.provider", "gemini")).strip().lower()
    model = str(_get_nested(raw, "llm.model", "gemini-1.5-flash")).strip()
    timeout_seconds = float(_get_nested(raw, "llm.timeout_seconds", 20.0))
    temperature = float(_get_nested(raw, "llm.temperature", 0.2))

    api_key: Optional[str] = None
    api_key_env = _get_nested(raw, "llm.api_key_env", None)
    if isinstance(api_key_env, str) and api_key_env.strip():
        api_key = os.environ.get(api_key_env.strip())

    if not api_key:
        api_key_direct = _get_nested(raw, "llm.api_key", None)
        if isinstance(api_key_direct, str) and api_key_direct.strip():
            api_key = api_key_direct.strip()

    if not api_key:
        raise RuntimeError(
            "Missing Gemini API key. Set llm.api_key_env (recommended) or llm.api_key in config.yaml"
        )

    return LlmConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
    )
