"""backend/services/embedding_strategies.py"""

import asyncio
import logging
from abc import ABC, abstractmethod

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover - handled at runtime when Google provider is unavailable.
    genai = None
    types = None

from openai import AsyncOpenAI

from backend.settings import settings

logger = logging.getLogger(__name__)


class EmbeddingStrategy(ABC):
    """Abstract Strategy interface for vector embedding generation."""

    @abstractmethod
    async def generate_embedding(self, text: str) -> list[float]:
        """Generates a 768-dimensional embedding vector for the provided text."""


class GoogleEmbeddingStrategy(EmbeddingStrategy):
    """Primary strategy: Gemini Embedding 2, truncated to the DB vector size."""

    def __init__(self) -> None:
        if genai is None or types is None:
            raise RuntimeError(
                "google-genai is not installed. Install it with 'pip install google-genai' "
                "or configure the OpenAI fallback before using the Google embedding provider."
            )
        # Created once, reused across every call -- not per-request.
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    async def generate_embedding(self, text: str) -> list[float]:
        if genai is None or types is None:
            raise RuntimeError("Google embedding support is unavailable because google-genai is not installed.")
        # google-genai's embed_content is synchronous. Running it directly
        # inside this async function would block the entire event loop
        # while waiting on the network -- every other concurrent job would
        # stall. asyncio.to_thread runs it on a worker thread instead,
        # keeping the event loop free.
        response = await asyncio.to_thread(
            self._client.models.embed_content,
            model="gemini-embedding-2",
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=settings.OPENAI_EMBEDDING_DIMENSIONS,
            ),
        )
        return response.embeddings[0].values


class OpenAIEmbeddingStrategy(EmbeddingStrategy):
    """Fallback strategy: configured OpenAI embedding model at the DB vector size."""

    def __init__(self) -> None:
        # Create this only if failover is actually needed. Otherwise a broken
        # optional OpenAI environment must not prevent Gemini from starting.
        self._client: AsyncOpenAI | None = None

    async def generate_embedding(self, text: str) -> list[float]:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        response = await self._client.embeddings.create(
            model=settings.OPENAI_EMBEDDING_MODEL,
            input=text,
            dimensions=settings.OPENAI_EMBEDDING_DIMENSIONS,
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
# If Google support is unavailable in the current environment, fall back to
# the OpenAI strategy instead of crashing the whole service at import time.
primary_strategy = GoogleEmbeddingStrategy() if genai is not None and types is not None else OpenAIEmbeddingStrategy()
embedding_service = ResilientEmbeddingService(
    primary=primary_strategy,
    fallback=OpenAIEmbeddingStrategy(),
)
