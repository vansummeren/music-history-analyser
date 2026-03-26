"""Abstract base class for AI provider adapters.

To add a new AI provider, subclass AIProvider and implement all abstract methods.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AnalysisResult:
    """Result returned by an AI provider."""

    text: str
    model: str
    input_tokens: int
    output_tokens: int


class AIProvider(ABC):
    """Abstract interface that every AI provider adapter must implement."""

    @abstractmethod
    async def analyse(
        self,
        api_key: str,
        prompt: str,
        track_list: str,
    ) -> AnalysisResult:
        """Send the prompt and track list to the AI and return the result."""
