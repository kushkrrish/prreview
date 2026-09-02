"""backend/services/embedding_strategies.py"""

import asyncio
import logging
from abc import ABC, abstractmethod

from google import genai
from openai import AsyncOpenAI

from backend.settings import settings

logger = logging.getLogger(__name__)


class EmbeddingStrategy(ABC):
    """Abstract Strategy interface for vector embedding generation."""

    @abstractmethod
    async def generate_embedding(self, text: str) -> list[float]:
        """Generates a 768-dimensional embedding vector for the provided text."""


class GoogleEmbeddingStrategy(EmbeddingStrategy):
    """Primary Strategy: Google Gemini text-embedding-004 (Native 768-dim)."""

    def __init__(self) -> None:
        # Created once, reused across every call -- not per-request.
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    async def generate_embedding(self, text: str) -> list[float]:
        # google-genai's embed_content is synchronous. Running it directly
        # inside this async function would block the entire event loop
        # while waiting on the network -- every other concurrent job would
        # stall. asyncio.to_thread runs it on a worker thread instead,
        # keeping the event loop free.
        response = await asyncio.to_thread(
            self._client.models.embed_content,
            model="text-embedding-004",
            contents=text,
        )
        return response.embedding.values


class OpenAIEmbeddingStrategy(EmbeddingStrategy):
    """Fallback Strategy: OpenAI text-embedding-3-small (Matryoshka 768-dim truncation)."""

    def __init__(self) -> None:
        # AsyncOpenAI is natively async -- no thread wrapping needed here.
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def generate_embedding(self, text: str) -> list[float]:
        response = await self._client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
            dimensions=768,  # Truncates native 1536 -> 768 dims
        )
        return response.data[0].embedding


class ResilientEmbeddingService:
    """Wraps a primary and fallback strategy, failing over automatically."""

    def __init__(self, primary: EmbeddingStrategy, fallback: EmbeddingStrategy) -> None:
        self.primary = primary
        self.fallback = fallback

    async def get_embedding(self, text: str) -> list[float]:
        try:
            return await self.primary.generate_embedding(text)
        except Exception as exc:
            logger.warning("Primary embedding strategy failed (%s). Trying fallback...", exc)
            try:
                return await self.fallback.generate_embedding(text)
            except Exception as fallback_exc:
                logger.error("Fallback embedding strategy also failed: %s", fallback_exc)
                raise


# Module-level singleton: both underlying clients are created exactly once,
# on first import, and reused for the lifetime of the worker process.
embedding_service = ResilientEmbeddingService(
    primary=GoogleEmbeddingStrategy(),
    fallback=OpenAIEmbeddingStrategy(),
)