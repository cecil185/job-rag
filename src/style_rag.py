"""Style RAG for learning and applying writing style."""
import logging
import time
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict
from src.database import StyleExample
from src.embeddings import EmbeddingGenerator
import json

logger = logging.getLogger(__name__)


class StyleRAG:
    """Style RAG for learning and applying writing style."""
    
    def __init__(self, db: Session):
        self.db = db
        self.embedding_gen = EmbeddingGenerator()
    
    def add_style_example(self, content: str, metadata: dict = None):
        """
        Add approved edit pack as style example.
        
        Args:
            content: Approved edit pack content
            metadata: Optional metadata (job url, etc.)
        """
        t0 = time.perf_counter()
        logger.info("add_style_example: generating embedding")
        embedding = self.embedding_gen.generate(content)

        style_example = StyleExample(
            content=content,
            embedding=self.embedding_gen.embedding_to_text(embedding),
            meta_data=metadata or {}
        )
        
        self.db.add(style_example)
        self.db.commit()
        logger.info("add_style_example: done in %.2fs", time.perf_counter() - t0)

    def retrieve_style_examples(self, query_text: str, top_k: int = None) -> List[Dict]:
        """
        Retrieve similar style examples.
        
        Args:
            query_text: Query text (job requirements or context)
            top_k: Number of examples to return
            
        Returns:
            List of dicts with 'content', 'similarity_score', 'metadata'
        """
        top_k = top_k or 3
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
