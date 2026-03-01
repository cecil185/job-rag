"""Embedding generation utilities."""
import json
import logging
import time
from typing import List

from openai import OpenAI

from src.config import settings

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generate embeddings for text."""

    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    def generate(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        if not self.client:
            raise ValueError("OpenAI API key not configured")

        t0 = time.perf_counter()
        response = self.client.embeddings.create(
            model=settings.embedding_model,
            input=text
        )
        logger.debug("embeddings.generate(1): %.2fs", time.perf_counter() - t0)
        return list(response.data[0].embedding)

    def generate_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        if not self.client:
            raise ValueError("OpenAI API key not configured")

        t0 = time.perf_counter()
        response = self.client.embeddings.create(
            model=settings.embedding_model,
            input=texts
        )
        logger.info("embeddings.generate_batch(%d): %.2fs", len(texts), time.perf_counter() - t0)
        return [list(item.embedding) for item in response.data]

    def embedding_to_text(self, embedding: List[float]) -> str:
        """Convert embedding list to JSON string for storage."""
        return json.dumps(embedding)

    def text_to_embedding(self, text: str) -> List[float]:
        """Convert JSON string back to embedding list."""
        return list(json.loads(text))
