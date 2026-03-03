"""Gemini API client."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeminiRequest:
    model: str
    api_key: str
    prompt: str
    temperature: float = 0.2
    timeout_seconds: float = 20.0


@dataclass(frozen=True)
class GeminiUsage:
    """Token usage metadata returned by the Gemini API."""

    prompt_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None


@dataclass(frozen=True)
class GeminiResult:
    """Gemini text result with optional usage metadata."""

    text: str
    usage: GeminiUsage | None


class GeminiClient:
    """Lightweight client for the Gemini generateContent API."""

    def __init__(self, session: Optional[requests.Session] = None):
        self._session = session or requests.Session()

    def generate_text(self, req: GeminiRequest) -> str:
        """Return only the generated text (no usage metadata)."""

        result = self.generate_text_with_usage(req)
        return result.text

    def generate_text_with_usage(self, req: GeminiRequest) -> GeminiResult:
        """Return generated text plus any usage metadata from the API."""

        if not req.api_key:
            raise RuntimeError("Gemini API key is missing")

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{req.model}:generateContent?key={req.api_key}"
        )

        payload = {
            "contents": [{"role": "user", "parts": [{"text": req.prompt}]}],
            "generationConfig": {
                "temperature": req.temperature,
            },
        }

        try:
            resp = self._session.post(url, json=payload, timeout=req.timeout_seconds)
        except requests.RequestException as e:
            raise RuntimeError(f"Gemini request failed: {e}") from e

        if resp.status_code >= 400:
            # Avoid logging secrets; response body can still be helpful.
            raise RuntimeError(f"Gemini HTTP {resp.status_code}: {resp.text[:500]}")

        try:
            data = resp.json()
        except Exception as e:
            raise RuntimeError("Gemini returned non-JSON response") from e

        try:
            candidates = data.get("candidates") or []
            if not candidates:
                raise KeyError("candidates")
            content = candidates[0].get("content") or {}
            parts = content.get("parts") or []
            if not parts:
                raise KeyError("content.parts")
            text = parts[0].get("text")
            if not isinstance(text, str):
                raise KeyError("content.parts[0].text")
            return GeminiResult(text=text.strip(), usage=_parse_usage(data))
        except Exception as e:
            logger.debug(f"Unexpected Gemini response shape: {data}")
            raise RuntimeError("Gemini returned an unexpected response") from e


def _parse_usage(data: dict) -> GeminiUsage | None:
    """Parse usageMetadata from the Gemini API response."""

    usage = data.get("usageMetadata")
    if not isinstance(usage, dict):
        return None

    def _as_int(value: object) -> int | None:
        return value if isinstance(value, int) else None

    return GeminiUsage(
        prompt_tokens=_as_int(usage.get("promptTokenCount")),
        output_tokens=_as_int(usage.get("candidatesTokenCount")),
        total_tokens=_as_int(usage.get("totalTokenCount")),
    )
