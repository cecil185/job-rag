"""Database setup and models."""
import logging
from datetime import datetime
from typing import Any
from typing import Generator

from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import create_engine
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import JSON
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from src.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()


class Job(Base):  # type: ignore[valid-type,misc]
    """Job posting model."""
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    url = Column(String, unique=True, nullable=False)
    raw_text = Column(Text)
    meta_data = Column(JSON)  # Renamed from 'metadata' to avoid SQLAlchemy conflict
    created_at = Column(DateTime, default=datetime.utcnow)

    requirements = relationship("Requirement", back_populates="job")
    edit_packs = relationship("EditPack", back_populates="job")


class Requirement(Base):  # type: ignore[valid-type,misc]
    """Extracted requirement from job posting."""
    __tablename__ = "requirements"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    category = Column(String)  # skills, responsibilities, must_haves, keywords
    text = Column(Text, nullable=False)
    priority = Column(String)  # must_have, nice_to_have
    confidence = Column(Float, nullable=True)  # [0, 1] from extractor
    validated = Column(Boolean, nullable=True)  # True if found in raw_text
    raw_snippet = Column(Text, nullable=True)  # excerpt from raw_text that supports this requirement
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="requirements")
    evidence_matches = relationship("EvidenceMatch", back_populates="requirement")


class EvidenceMatch(Base):  # type: ignore[valid-type,misc]
    """Evidence snippets matched to requirements."""
    __tablename__ = "evidence_matches"

    id = Column(Integer, primary_key=True)
    requirement_id = Column(Integer, ForeignKey("requirements.id"), nullable=False)
    evidence_id = Column(Integer, ForeignKey("evidence_chunks.id"), nullable=False)
    similarity_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    requirement = relationship("Requirement", back_populates="evidence_matches")
    evidence_chunk = relationship("EvidenceChunk", back_populates="matches")


class EvidenceChunk(Base):  # type: ignore[valid-type,misc]
    """Chunked evidence from resume/brag-doc/projects."""
    __tablename__ = "evidence_chunks"

    id = Column(Integer, primary_key=True)
    source_id = Column(String, nullable=False)  # identifier in source
    content = Column(Text, nullable=False)
    embedding = Column(Text)  # JSON array of floats
    meta_data = Column(JSON)  # Renamed from 'metadata' to avoid SQLAlchemy conflict
    is_resume = Column(Boolean, default=False)  # True = on base resume (replace on re-upload)
    created_at = Column(DateTime, default=datetime.utcnow)

    matches = relationship("EvidenceMatch", back_populates="evidence_chunk")


class StyleExample(Base):  # type: ignore[valid-type,misc]
    """Approved edit pack stored as style example."""
    __tablename__ = "style_examples"

    id = Column(Integer, primary_key=True)
    content = Column(Text, nullable=False)
    embedding = Column(Text)  # JSON array of floats
    meta_data = Column(JSON)  # Renamed from 'metadata' to avoid SQLAlchemy conflict
    created_at = Column(DateTime, default=datetime.utcnow)


class EditPack(Base):  # type: ignore[valid-type,misc]
    """Generated resume edit pack."""
    __tablename__ = "edit_packs"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)  # Markdown format
    fit_score = Column(Float)
    gap_list = Column(JSON)
    approved = Column(Integer, default=0)  # 0=pending, 1=approved, -1=rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime)

    job = relationship("Job", back_populates="edit_packs")


class AuditLog(Base):  # type: ignore[valid-type,misc]
    """Audit log for extraction runs, edit pack approval/rejection."""
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    entity_type = Column(String, nullable=False)  # e.g. "job", "edit_pack"
    entity_id = Column(Integer, nullable=False)
    action = Column(String, nullable=False)  # e.g. "extraction_run", "edit_pack_approved", "edit_pack_rejected"
    actor = Column(String, default="system")
    at = Column(DateTime, default=datetime.utcnow)
    payload = Column(JSON, nullable=True)  # optional details


# Database setup
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Initialize database tables and pgvector extension."""
    from sqlalchemy import text

    logger.info("init_db: creating tables")
    # Create tables (including audit_log and new columns for new installs)
    Base.metadata.create_all(bind=engine)

    # Migrations for existing DBs: add Requirement confidence/validation columns if missing
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE jobs DROP COLUMN IF EXISTS title"))
            for col, sql_type in [
                ("confidence", "FLOAT"),
                ("validated", "BOOLEAN"),
                ("raw_snippet", "TEXT"),
            ]:
                conn.execute(text(
                    f"ALTER TABLE requirements ADD COLUMN IF NOT EXISTS {col} {sql_type}"
                ))
            conn.commit()
        except Exception:
            conn.rollback()

    # Ensure ON DELETE CASCADE on FKs from edit_packs and requirements to jobs (so DELETE FROM jobs cascades)
    with engine.connect() as conn:
        try:
            conn.execute(text(
                "ALTER TABLE edit_packs DROP CONSTRAINT IF EXISTS edit_packs_job_id_fkey"
            ))
            conn.execute(text(
                "ALTER TABLE edit_packs ADD CONSTRAINT edit_packs_job_id_fkey "
                "FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE"
            ))
            conn.execute(text(
                "ALTER TABLE requirements DROP CONSTRAINT IF EXISTS requirements_job_id_fkey"
            ))
            conn.execute(text(
                "ALTER TABLE requirements ADD CONSTRAINT requirements_job_id_fkey "
                "FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE"
            ))
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.warning("init_db: could not set CASCADE on job FKs: %s", e)

    # Enable pgvector extension
    logger.info("init_db: enabling pgvector extension")
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    # Create vector indexes (using expression indexes on cast)
    with engine.connect() as conn:
        try:
            # Create expression indexes for vector similarity search
            # These indexes work on the cast expression
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS evidence_chunks_embedding_idx
                ON evidence_chunks USING ivfflat ((embedding::vector(1536)) vector_cosine_ops)
                WITH (lists = 100)
                WHERE embedding IS NOT NULL
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS style_examples_embedding_idx
                ON style_examples USING ivfflat ((embedding::vector(1536)) vector_cosine_ops)
                WITH (lists = 100)
                WHERE embedding IS NOT NULL
            """))
            conn.commit()
            logger.info("init_db: vector indexes created")
        except Exception as e:
            logger.warning("init_db: vector indexes - %s. Queries will still work but may be slower.", e)


def get_db() -> Generator[Session, None, None]:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
