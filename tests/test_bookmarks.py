"""Tests for job bookmarks CRUD."""
import pytest
from sqlalchemy import text

from src.database import get_db
from src.database import init_db
from src.database import engine
from src import bookmarks


@pytest.fixture
def db_session():
    """Provide a DB session and ensure tables exist; truncate job_bookmarks for isolation."""
    init_db()
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE job_bookmarks CASCADE"))
        conn.commit()
    gen = get_db()
    db = next(gen)
    try:
        yield db
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_create_and_get_by_id(db_session) -> None:
    b = bookmarks.create(
        db_session,
        "https://example.com/job/1",
        "LinkedIn",
        title="Senior Engineer",
        company="Acme Inc",
        status="saved",
    )
    assert b.id is not None
    assert b.url == "https://example.com/job/1"
    assert b.source_board_name == "LinkedIn"
    assert b.title == "Senior Engineer"
    assert b.company == "Acme Inc"
    assert b.status == "saved"
    assert b.created_at is not None

    got = bookmarks.get_by_id(db_session, b.id)
    assert got is not None
    assert got.url == b.url


def test_get_by_url(db_session) -> None:
    bookmarks.create(db_session, "https://boards.greenhouse.io/co/jobs/123", "Greenhouse", title="Backend")
    b = bookmarks.get_by_url(db_session, "https://boards.greenhouse.io/co/jobs/123")
    assert b is not None
    assert b.source_board_name == "Greenhouse"
    assert b.title == "Backend"


def test_get_all_and_filter_by_status(db_session) -> None:
    bookmarks.create(db_session, "https://a.com/1", "Indeed", status="saved")
    bookmarks.create(db_session, "https://a.com/2", "Indeed", status="applied")
    bookmarks.create(db_session, "https://a.com/3", "LinkedIn", status="saved")
    all_b = bookmarks.get_all(db_session)
    assert len(all_b) >= 3
    saved = bookmarks.get_all(db_session, status="saved")
    assert len(saved) >= 2
    applied = bookmarks.get_all(db_session, status="applied")
    assert len(applied) >= 1


def test_update(db_session) -> None:
    b = bookmarks.create(db_session, "https://b.com/1", "Indeed", title="Old", status="saved")
    updated = bookmarks.update(db_session, b.id, title="New Title", status="applied")
    assert updated is not None
    assert updated.title == "New Title"
    assert updated.status == "applied"
    got = bookmarks.get_by_id(db_session, b.id)
    assert got.title == "New Title"


def test_delete(db_session) -> None:
    b = bookmarks.create(db_session, "https://c.com/1", "LinkedIn")
    ok = bookmarks.delete(db_session, b.id)
    assert ok is True
    assert bookmarks.get_by_id(db_session, b.id) is None
    assert bookmarks.delete(db_session, 99999) is False


def test_to_dict(db_session) -> None:
    b = bookmarks.create(db_session, "https://d.com/1", "Indeed", title="T", company="C", status="saved")
    d = b.to_dict()
    assert d["url"] == "https://d.com/1"
    assert d["source_board_name"] == "Indeed"
    assert d["title"] == "T"
    assert d["company"] == "C"
    assert d["status"] == "saved"
    assert "created_at" in d
    assert "updated_at" in d
