"""Style RAG for learning and applying writing style."""
import json
import logging
import re
import time
from typing import Any
from typing import List

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config import settings
from src.database import StyleExample
from src.embeddings import EmbeddingGenerator

logger = logging.getLogger(__name__)


def chunk_by_paragraphs(text: str) -> List[str]:
    """Split text into paragraphs (double newline)."""
    if not (text or text.strip()):
        return []
    parts = [p.strip() for p in text.strip().split("\n\n") if p.strip()]
    return parts


def chunk_by_sections(text: str) -> List[str]:
    """Split markdown by ## or ### headers; each section (header + body) is one chunk."""
    if not (text or text.strip()):
        return []
    # Split on lines that are ## or ### headers
    pattern = re.compile(r"^(#{2,3}\s+.+)$", re.MULTILINE)
    sections = pattern.split(text.strip())
    # sections[0] = intro; then [header1, body1, header2, body2, ...]
    chunks = []
    if sections[0].strip():
        chunks.append(sections[0].strip())
    for i in range(1, len(sections) - 1, 2):
        chunk = sections[i].strip()
        if i + 1 < len(sections) and sections[i + 1].strip():
            chunk = chunk + "\n\n" + sections[i + 1].strip()
        if chunk:
            chunks.append(chunk)
    return chunks


class StyleRAG:
    """Style RAG for learning and applying writing style."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.embedding_gen = EmbeddingGenerator()

    def _chunk_content(self, content: str, chunk_type: str) -> List[str]:
        """
        Chunk content for storage: one chunk per paragraph or per section (project).
        - cover_letter / application_answer: one chunk per paragraph (split on \\n\\n).
        - resume-edit-pack: one chunk per markdown ##/### section.
        """
        if not (content or content.strip()):
            return []
        if chunk_type in ("cover_letter", "application_answer"):
            return chunk_by_paragraphs(content)
        if chunk_type == "resume-edit-pack":
            chunks = chunk_by_sections(content)
            return chunks if chunks else chunk_by_paragraphs(content)
        return [content.strip()]

    def add_style_example_chunked(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        chunk_type: str = "cover_letter",
    ) -> None:
        """
        Chunk content and add each chunk as a separate style example row.
        - cover_letter / application_answer: one row per paragraph.
        - resume-edit-pack: one row per ##/### section (e.g. per project/section).
        """
        chunks = self._chunk_content(content, chunk_type)
        if not chunks:
            return
        t0 = time.perf_counter()
        logger.info("add_style_example_chunked: %d chunks (type=%s)", len(chunks), chunk_type)
        base_meta = dict(metadata or {})
        for i, chunk in enumerate(chunks):
            chunk_meta = {**base_meta, "chunk_index": i, "chunk_total": len(chunks)}
            embedding = self.embedding_gen.generate(chunk)
            self.db.add(StyleExample(
                content=chunk,
                embedding=self.embedding_gen.embedding_to_text(embedding),
                meta_data=chunk_meta
            ))
        self.db.commit()
        logger.info("add_style_example_chunked: done in %.2fs", time.perf_counter() - t0)

    def retrieve_style_examples(
        self, query_text: str, top_k: int | None = None
    ) -> List[dict[str, Any]]:
        """
        Retrieve similar style examples.

        Args:
            query_text: Query text (job requirements or context)
            top_k: Number of examples to return

        Returns:
            List of dicts with 'content', 'similarity_score', 'metadata'
        """
        top_k = top_k or settings.top_k_style
        t0 = time.perf_counter()
        # Generate query embedding
        query_embedding = self.embedding_gen.generate(query_text)
        embedding_json = json.dumps(query_embedding)

        # Vector similarity search
        query = text("""
            SELECT
                id,
                content,
                meta_data,
                1 - (embedding::vector <=> CAST(:query_embedding AS vector)) as similarity_score
            FROM style_examples
            WHERE embedding IS NOT NULL
            ORDER BY embedding::vector <=> CAST(:query_embedding AS vector)
            LIMIT :top_k
        """)

        result = self.db.execute(
            query,
            {
                "query_embedding": embedding_json,
                "top_k": top_k
            }
        )

        results = []
        for row in result:
            results.append({
                "id": row.id,
                "content": row.content,
                "similarity_score": float(row.similarity_score),
                "metadata": row.meta_data or {}
            })

        logger.info("retrieve_style_examples: top_k=%d done in %.2fs", top_k, time.perf_counter() - t0)
        return results
