"""Configuration settings."""
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):  # type: ignore[misc]
    """Application settings."""

    database_url: str = "postgresql://jobrag:jobrag_password@postgres:5432/jobrag_db"
    openai_api_key: Optional[str] = None

    # Embedding settings
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536

    # LLM settings
    llm_provider: str = "openai"  # or "anthropic"
    llm_model: str = "gpt-4o-mini"

    # RAG settings
    evidence_chunk_size: int = 50
    evidence_chunk_overlap: int = 10
    top_k_evidence: int = 5
    top_k_style: int = 3

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
