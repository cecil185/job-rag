"""Text chunking utilities."""
from typing import List
from src.config import settings
import tiktoken


class Chunker:
    """Chunk text into smaller pieces for embedding."""
    
    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        self.chunk_size = chunk_size or settings.evidence_chunk_size
        self.chunk_overlap = chunk_overlap or settings.evidence_chunk_overlap
        self.encoding = tiktoken.get_encoding("cl100k_base")
    
    def chunk_text(self, text: str, metadata: dict = None) -> List[dict]:
        """
        Chunk text into overlapping chunks.
        
        Args:
            text: Text to chunk
            metadata: Optional metadata to attach to each chunk
            
        Returns:
            List of dicts with 'content' and 'metadata' keys
        """
        # Tokenize
        tokens = self.encoding.encode(text)
        
        chunks = []
        start = 0
        
        while start < len(tokens):
            end = start + self.chunk_size
            chunk_tokens = tokens[start:end]
            chunk_text = self.encoding.decode(chunk_tokens)
            
            chunk_meta = {
                **(metadata or {}),
                "chunk_index": len(chunks),
                "start_token": start,
                "end_token": end
            }
            
            chunks.append({
                "content": chunk_text,
                "metadata": chunk_meta
            })
            
            # Move forward with overlap
            start += self.chunk_size - self.chunk_overlap
            
            # Avoid infinite loop
            if start >= len(tokens):
                break
        
        return chunks
    
    def _token_chunk(self, text: str, metadata: dict, chunk_index_start: int = 0) -> List[dict]:
        """Split text into token-sized chunks with overlap (same logic as chunk_text)."""
        tokens = self.encoding.encode(text)
        result = []
        start = 0
        while start < len(tokens):
            end = min(start + self.chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            content = self.encoding.decode(chunk_tokens)
            result.append({
                "content": content,
                "metadata": {
                    **metadata,
                    "chunk_index": chunk_index_start + len(result),
                    "start_token": start,
                    "end_token": end,
                },
            })
            start += self.chunk_size - self.chunk_overlap
            if start >= len(tokens):
                break
        return result

    def chunk_by_sentences(self, text: str, metadata: dict = None) -> List[dict]:
        """
        Chunk text by sentences, respecting chunk_size.
        When a segment has no periods or exceeds chunk_size, token-splits it like chunk_text.
        """
        meta = metadata or {}
        sentences = text.split('. ')
        chunks = []
        current_chunk = []
        current_size = 0

        for sentence in sentences:
            sentence_tokens = len(self.encoding.encode(sentence))

            if sentence_tokens > self.chunk_size:
                # Flush accumulated sentence chunks first
                if current_chunk:
                    chunk_content = '. '.join(current_chunk) + '.'
                    chunks.append({
                        "content": chunk_content,
                        "metadata": {**meta, "chunk_index": len(chunks)},
                    })
                    current_chunk = []
                    current_size = 0
                # Token-split this long segment (no periods or very long sentence)
                chunks.extend(self._token_chunk(sentence, meta, chunk_index_start=len(chunks)))
                continue

            if current_size + sentence_tokens > self.chunk_size and current_chunk:
                chunk_content = '. '.join(current_chunk) + '.'
                chunks.append({
                    "content": chunk_content,
                    "metadata": {**meta, "chunk_index": len(chunks)},
                })
                current_chunk = []
                current_size = 0

            current_chunk.append(sentence)
            current_size += sentence_tokens

        if current_chunk:
            chunk_content = '. '.join(current_chunk) + '.'
            chunks.append({
                "content": chunk_content,
                "metadata": {**meta, "chunk_index": len(chunks)},
            })

        return chunks
