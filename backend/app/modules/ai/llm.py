"""OpenAI-compatible chat client (DeepSeek, OpenAI, or any compatible host).

DeepSeek exposes the same /chat/completions contract as OpenAI, so a single
client covers both; the provider only changes the default base URL and model.
"""
import json
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("bridge.ai.llm")


class LLMError(RuntimeError):
    pass


async def chat_json(system: str, user: str, *, max_tokens: int = 800) -> dict[str, Any]:
    """Run one chat completion and parse the reply as a JSON object."""
    if not settings.ai_api_key:
        raise LLMError("AI_API_KEY is not configured")
    payload = {
        "model": settings.ai_chat_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=10.0)) as client:
            resp = await client.post(
                f"{settings.ai_base_url_resolved}/chat/completions",
                headers={"Authorization": f"Bearer {settings.ai_api_key}"},
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise LLMError(f"AI provider unreachable: {exc}") from exc
    if resp.status_code >= 400:
        # Never log the key; the body carries the provider's error message.
        raise LLMError(f"AI provider returned {resp.status_code}: {resp.text[:300]}")
    try:
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except (KeyError, IndexError, ValueError) as exc:
        raise LLMError(f"AI provider returned an unexpected response: {exc}") from exc
