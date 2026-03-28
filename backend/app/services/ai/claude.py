"""Claude adapter — implements AIProvider using the Anthropic SDK."""
from __future__ import annotations

import logging

import anthropic

from app.services.ai.base import AIProvider, AnalysisResult

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "claude-3-5-haiku-20241022"
_MAX_TOKENS = 1024


class ClaudeAdapter(AIProvider):
    """Adapter that wraps the Anthropic Claude API."""

    async def analyse(
        self,
        api_key: str,
        prompt: str,
        track_list: str,
    ) -> AnalysisResult:
        """Send the prompt and track list to Claude and return the result."""
        logger.debug("Sending request to Claude model %s", _DEFAULT_MODEL)
        client = anthropic.AsyncAnthropic(api_key=api_key)
        message_content = f"{prompt}\n\nRecently played tracks:\n{track_list}"
        response = await client.messages.create(
            model=_DEFAULT_MODEL,
            max_tokens=_MAX_TOKENS,
            messages=[{"role": "user", "content": message_content}],
        )
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text

        logger.info(
            "Claude response received — model: %s, tokens: %d in / %d out",
            response.model,
            response.usage.input_tokens,
            response.usage.output_tokens,
        )
        return AnalysisResult(
            text=text,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
