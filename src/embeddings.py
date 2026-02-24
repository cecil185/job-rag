"""Embedding generation utilities."""
from openai import OpenAI
from typing import List
import json
from src.config import settings


class EmbeddingGenerator:
    """Generate embeddings for text."""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
    
    def generate(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        if not self.client:
            raise ValueError("OpenAI API key not configured")
        
        response = self.client.embeddings.create(
            model=settings.embedding_model,
            input=text
        )
        
        return response.data[0].embedding
    
    def generate_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        if not self.client:
            raise ValueError("OpenAI API key not configured")
        
        response = self.client.embeddings.create(
            model=settings.embedding_model,
            input=texts
        )
        
        return [item.embedding for item in response.data]
    
    def embedding_to_text(self, embedding: List[float]) -> str:
        """Convert embedding list to JSON string for storage."""
        return json.dumps(embedding)
    
    def text_to_embedding(self, text: str) -> List[float]:
        """Convert JSON string back to embedding list."""
        return json.loads(text)
