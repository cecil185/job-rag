"""CRUD for job bookmarks (kanban/status features)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.database import JobBookmark


def create(
    db: Session,
    url: str,
    source_board_name: str,
    *,
    title: Optional[str] = None,
    company: Optional[str] = None,
    status: str = "saved",
) -> JobBookmark:
    """Create a job bookmark. Raises if url already exists."""
    b = JobBookmark(
        url=url,
        source_board_name=source_board_name,
        title=title,
        company=company,
        status=status,
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


def get_by_id(db: Session, bookmark_id: int) -> Optional[JobBookmark]:
    """Get bookmark by id."""
    return db.query(JobBookmark).filter(JobBookmark.id == bookmark_id).first()


def get_by_url(db: Session, url: str) -> Optional[JobBookmark]:
    """Get bookmark by URL."""
    return db.query(JobBookmark).filter(JobBookmark.url == url).first()


def get_all(db: Session, status: Optional[str] = None) -> list[JobBookmark]:
    """List all bookmarks, optionally filtered by status (for kanban columns)."""
    q = db.query(JobBookmark).order_by(JobBookmark.created_at.desc())
    if status is not None:
        q = q.filter(JobBookmark.status == status)
    return q.all()


def update(
    db: Session,
    bookmark_id: int,
    *,
    title: Optional[str] = None,
    company: Optional[str] = None,
    status: Optional[str] = None,
) -> Optional[JobBookmark]:
    """Update bookmark fields. Returns updated bookmark or None if not found."""
    b = get_by_id(db, bookmark_id)
    if b is None:
        return None
    if title is not None:
        b.title = title
    if company is not None:
        b.company = company
    if status is not None:
        b.status = status
    db.commit()
    db.refresh(b)
    return b


def delete(db: Session, bookmark_id: int) -> bool:
    """Delete bookmark by id. Returns True if deleted, False if not found."""
    b = get_by_id(db, bookmark_id)
    if b is None:
        return False
    db.delete(b)
    db.commit()
    return True
