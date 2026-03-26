"""Perplexity adapter — implements AIProvider using the OpenAI-compatible REST API."""
from __future__ import annotations

import httpx

from app.services.ai.base import AIProvider, AnalysisResult

_PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
_DEFAULT_MODEL = "llama-3.1-sonar-small-128k-online"


class PerplexityAdapter(AIProvider):
    """Adapter that wraps the Perplexity AI API (OpenAI-compatible REST)."""

    async def analyse(
        self,
        api_key: str,
        prompt: str,
        track_list: str,
    ) -> AnalysisResult:
        """Send the prompt and track list to Perplexity and return the result."""
        message_content = f"{prompt}\n\nRecently played tracks:\n{track_list}"
        payload = {
            "model": _DEFAULT_MODEL,
            "messages": [{"role": "user", "content": message_content}],
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                _PERPLEXITY_API_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        text: str = choice["message"]["content"]
        usage = data.get("usage", {})
        model: str = data.get("model", _DEFAULT_MODEL)

        return AnalysisResult(
            text=text,
            model=model,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )
