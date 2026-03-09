"""Audit log helpers for extraction runs and edit pack approval/rejection."""
from datetime import datetime
from typing import Any
from typing import Optional

from sqlalchemy.orm import Session

from src.database import AuditLog


def write_audit_event(
    db: Session,
    entity_type: str,
    entity_id: int,
    action: str,
    actor: str = "system",
    payload: Optional[dict[str, Any]] = None,
    at: Optional[datetime] = None,
) -> None:
    """Append an audit log entry. at defaults to UTC now."""
    entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor=actor,
        at=at or datetime.utcnow(),
        payload=payload,
    )
    db.add(entry)
