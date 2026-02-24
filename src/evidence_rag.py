"""Evidence RAG for retrieving proof points."""
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Tuple
from src.database import EvidenceChunk, EvidenceMatch, Requirement
from src.embeddings import EmbeddingGenerator
from src.chunker import Chunker
import json


class EvidenceRAG:
    """Evidence RAG for retrieving matching proof points."""
    
    def __init__(self, db: Session):
        self.db = db
        self.embedding_gen = EmbeddingGenerator()
        self.chunker = Chunker()
    
    def add_evidence(self, text: str, source_id: str, metadata: dict = None, is_resume: bool = False):
        """
        Add evidence text to the store.
        
        Args:
            text: Evidence text (resume bullets, project descriptions, etc.)
            source_id: Identifier for this source (required).
            metadata: Optional additional metadata.
            is_resume: If True, this is the base resume; any existing resume chunks are deleted first.
        """
        if is_resume:
            # Delete existing resume chunks (and their matches) so upload replaces the resume
            resume_chunk_ids = [c.id for c in self.db.query(EvidenceChunk).filter(EvidenceChunk.is_resume == True).all()]
            if resume_chunk_ids:
                self.db.query(EvidenceMatch).filter(EvidenceMatch.evidence_id.in_(resume_chunk_ids)).delete(synchronize_session=False)
                self.db.query(EvidenceChunk).filter(EvidenceChunk.is_resume == True).delete(synchronize_session=False)
            self.db.commit()
        
        # Chunk the text
        chunks = self.chunker.chunk_by_sentences(text, metadata={
            "source_id": source_id,
            **(metadata or {})
        })
        
        # Generate embeddings and store
        for chunk in chunks:
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
    
    def retrieve(self, query_text: str, top_k: int) -> List[Dict]:
        """
        Retrieve top matching evidence chunks.
        
        Args:
            query_text: Query text (requirement text)
            top_k: Number of results to return
            
        Returns:
            List of dicts with 'content', 'source_id', 'similarity_score', 'metadata'
        """
        
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
        
        return results
    
    def match_requirements(self, requirements: List[Requirement], top_k: int = None) -> Dict[int, List[Dict]]:
        """
        Match evidence to requirements.
        
        Args:
            requirements: List of Requirement objects
            top_k: Number of evidence items per requirement
            
        Returns:
            Dict mapping requirement_id -> list of evidence matches
        """
        top_k = top_k or 5
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
        total_reqs = len(requirements)
        if total_reqs == 0:
            return 0.0, []
        
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
        
        return fit_score, gaps
