"""Evidence RAG for retrieving proof points."""
import json
import logging
import time
from typing import Any
from typing import List
from typing import Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.chunker import Chunker
from src.config import settings
from src.database import EvidenceChunk
from src.database import EvidenceMatch
from src.database import Requirement
from src.embeddings import EmbeddingGenerator

logger = logging.getLogger(__name__)


class EvidenceRAG:
    """Evidence RAG for retrieving matching proof points."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.embedding_gen = EmbeddingGenerator()
        self.chunker = Chunker()

    def add_evidence(
        self,
        text: str,
        source_id: str,
        metadata: dict[str, Any] | None = None,
        is_resume: bool = False,
    ) -> None:
        """
        Add evidence text to the store.

        Args:
            text: Evidence text (resume bullets, project descriptions, etc.)
            source_id: Identifier for this source (required).
            metadata: Optional additional metadata.
            is_resume: If True, this is the base resume; any existing resume chunks are deleted first.
        """
        t0 = time.perf_counter()
        logger.info("add_evidence: source_id=%s is_resume=%s start", source_id, is_resume)
        if is_resume:
            # Delete existing resume chunks (and their matches) so upload replaces the resume
            resume_chunk_ids = [c.id for c in self.db.query(EvidenceChunk).filter(EvidenceChunk.is_resume == True).all()]
            if resume_chunk_ids:
                self.db.query(EvidenceMatch).filter(EvidenceMatch.evidence_id.in_(resume_chunk_ids)).delete(synchronize_session=False)
                self.db.query(EvidenceChunk).filter(EvidenceChunk.is_resume == True).delete(synchronize_session=False)
            self.db.commit()

        # Chunk the text
        t_chunk = time.perf_counter()
        chunks = self.chunker.chunk_by_sentences(text, metadata={
            "source_id": source_id,
            **(metadata or {})
        })
        logger.info("add_evidence: chunked into %d chunks in %.2fs", len(chunks), time.perf_counter() - t_chunk)

        # Generate embeddings and store
        for i, chunk in enumerate(chunks):
            if i == 0 or (i + 1) % 5 == 0 or i == len(chunks) - 1:
                logger.info("add_evidence: embedding chunk %d/%d", i + 1, len(chunks))
            embedding = self.embedding_gen.generate(chunk["content"])

            evidence_chunk = EvidenceChunk(
                source_id=source_id,
                content=chunk["content"],
                embedding=self.embedding_gen.embedding_to_text(embedding),
                meta_data=chunk["metadata"],
                is_resume=is_resume
            )

            self.db.add(evidence_chunk)

        self.db.commit()
        logger.info("add_evidence: source_id=%s done in %.2fs (%d chunks)", source_id, time.perf_counter() - t0, len(chunks))

    def retrieve(self, query_text: str, top_k: int) -> List[dict[str, Any]]:
        """
        Retrieve top matching evidence chunks.

        Args:
            query_text: Query text (requirement text)
            top_k: Number of results to return

        Returns:
            List of dicts with 'content', 'source_id', 'similarity_score', 'metadata'
        """
        t0 = time.perf_counter()
        # Generate query embedding
        query_embedding = self.embedding_gen.generate(query_text)
        embedding_json = json.dumps(query_embedding)

        # Vector similarity search using pgvector
        query = text("""
            SELECT
                id,
                source_id,
                content,
                meta_data,
                COALESCE(is_resume, FALSE) as is_resume,
                1 - (embedding::vector <=> CAST(:query_embedding AS vector)) as similarity_score
            FROM evidence_chunks
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
                "source_id": row.source_id,
                "similarity_score": float(row.similarity_score),
                "metadata": row.meta_data or {},
                "is_resume": bool(row.is_resume)
            })

        logger.info("retrieve: top_k=%d done in %.2fs", top_k, time.perf_counter() - t0)
        return results

    def match_requirements(
        self,
        requirements: List[Requirement],
        top_k: int | None = None,
    ) -> dict[int, List[dict[str, Any]]]:
        """
        Match evidence to requirements.

        Args:
            requirements: List of Requirement objects
            top_k: Number of evidence items per requirement

        Returns:
            Dict mapping requirement_id -> list of evidence matches
        """
        top_k = top_k or settings.top_k_evidence
        t0 = time.perf_counter()
        logger.info("match_requirements: %d requirements top_k=%d start", len(requirements), top_k)
        evidence_map = {}

        for req in requirements:
            # Retrieve evidence
            evidence = self.retrieve(req.text, top_k=top_k)

            # Store matches in database
            for ev in evidence:
                match = EvidenceMatch(
                    requirement_id=req.id,
                    evidence_id=ev["id"],
                    similarity_score=ev["similarity_score"]
                )
                self.db.add(match)

            evidence_map[req.id] = evidence

        self.db.commit()
        logger.info("match_requirements: done in %.2fs", time.perf_counter() - t0)
        return evidence_map

    def calculate_fit_score(
        self,
        requirements: List[Requirement],
        threshold: float = 0.40,
        top_k_for_keyword: int = 10,
    ) -> Tuple[float, List[str]]:
        """
        Calculate fit score and identify gaps.

        A requirement is considered matched if either:
        - the top evidence chunk has similarity_score >= threshold, or
        - the requirement text appears (case-insensitive) in any of the top_k evidence chunks.
        The keyword check avoids marking skills like "Python" as gaps when they appear
        in resume chunks but embedding similarity for short queries is below threshold.

        Args:
            requirements: List of Requirement objects
            threshold: Minimum similarity score to count as match
            top_k_for_keyword: Number of evidence chunks to check for keyword presence

        Returns:
            Tuple of (fit_score, gap_list)
        """
        t0 = time.perf_counter()
        total_reqs = len(requirements)
        if total_reqs == 0:
            return 0.0, []

        logger.info("calculate_fit_score: %d requirements", total_reqs)
        matched_reqs = 0
        gaps = []

        for req in requirements:
            evidence = self.retrieve(req.text, top_k=top_k_for_keyword)
            if not evidence:
                gaps.append(req.text)
                continue
            best_score = evidence[0]["similarity_score"]
            # Match if similarity is above threshold, or requirement text appears in any chunk
            keyword_in_evidence = any(
                req.text.lower() in (ev.get("content") or "").lower()
                for ev in evidence
            )
            if best_score >= threshold or keyword_in_evidence:
                matched_reqs += 1
            else:
                gaps.append(req.text)

        fit_score = matched_reqs / total_reqs if total_reqs > 0 else 0.0
        logger.info("calculate_fit_score: done in %.2fs score=%.2f gaps=%d", time.perf_counter() - t0, fit_score, len(gaps))
        return fit_score, gaps
